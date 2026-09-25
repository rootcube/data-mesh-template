"""Snowflake key-pair authentication for the platform.

    just setup                 everything: `just init`, then this wizard, which asks whether the account is
                               fresh (-> bootstrap), already provisioned (-> setup) or provisioned from
                               another checkout (-> bootstrap, syncing or wiping what exists)
    just sf bootstrap          fresh account, as ACCOUNTADMIN: account settings and Terraform service user
                                      (init.sql), provisioning (terraform apply), your own key pair and .env,
                                      in one go; objects that already exist are synced into the state (and
                                      handed to their SYSADMIN/SECURITYADMIN/USERADMIN owner) or wiped
                                      (--existing ask|sync|wipe)
    just sf setup              one-time: log in interactively, create + register a key pair, write .env
    just sf context            pick the project you work in (from the roles granted to you) and write
                                      role, warehouse, database and schema prefix to .env; no login needed
    just sf check              connect with the key pair from .env and print who you are
    just sf query "SELECT 1"   run one statement with the key pair from .env
    just sf keygen <name>      create a key pair only (for service users such as the Terraform user)

`setup` needs exactly one interactive login: your browser (SSO or the Snowflake login page,
the default) or your password plus MFA (`--auth password`). It then generates an RSA key
pair under ~/.snowflake/keys/, registers the public key on your own user with
ALTER USER ... SET RSA_PUBLIC_KEY, verifies that key-pair login works, and writes the
connection settings to .env for dbt, dlt and Dagster.

A person's SNOWFLAKE_ROLE is their engineer role in the project (RL_<PROJECT>_DEV__ENG),
SNOWFLAKE_DATABASE the development database (DB_<PROJECT>_DEV) and SNOWFLAKE_SCHEMA the prefix
of their personal schemas (DBT_<USERNAME>); see terraform/README.md for how those are provisioned.
Both `setup` and `context` derive those from the project roles granted to the user.
"""

from __future__ import annotations

import argparse
import dataclasses
import getpass
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from dotenv import dotenv_values

from orchestrator.resources.snowflake import APPLICATION, SnowflakeSettings
from orchestrator.utils.dotenv import update_env_file

ROOT = Path(__file__).resolve().parents[1]
# RL_<PROJECT>_<ENV>__<PURPOSE>, the project roles Terraform creates (terraform/config/roles).
PROJECT_ROLE = re.compile(r"^RL_(?P<project>[A-Z0-9_]+)_(?P<env>DEV|TST|ACC|PRD)__(?P<purpose>[A-Z]+)$")
ENVIRONMENT_ORDER = ("DEV", "TST", "ACC", "PRD")
PURPOSE_ORDER = ("ENG", "ANL", "TFM", "ING")
# Schema prefixes .env.example ships: a placeholder, never someone's personal prefix.
PLACEHOLDER_SCHEMAS = ("DBT", "DBT_USERNAME")
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"
KEY_DIR = Path.home() / ".snowflake" / "keys"
TF_DIR = ROOT / "terraform"
INIT_SQL = TF_DIR / "modules" / "snowflake" / "init.sql"
TERRAFORM_KEY = "terraform"
# Import blocks for objects an earlier Terraform state created; lives for one `terraform apply`.
ADOPT_FILE = TF_DIR / "adopt_imports.tf"

# --- console helpers ----------------------------------------------------------

# ANSI styling, off when not writing to a terminal or when NO_COLOR is set (FORCE_COLOR overrides).
COLOR = bool(os.environ.get("FORCE_COLOR")) or (sys.stdout.isatty() and not os.environ.get("NO_COLOR"))
BOLD, DIM, CYAN, GREEN, YELLOW = "1", "2", "36", "32", "33"


def style(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if COLOR else text


def step(title: str) -> None:
    rule = style(CYAN, "━" * 78)
    print(f"\n{rule}\n{style(f'{BOLD};{CYAN}', '  ' + title)}\n{rule}")


def ok(message: str) -> None:
    print(style(GREEN, "✔ ") + message)


def warn(message: str) -> None:
    print(style(YELLOW, "! ") + message)


def done(message: str) -> None:
    print(f"\n{style(f'{BOLD};{GREEN}', 'Done.')} {message}")


def ask(label: str, default: str | None = None) -> str:
    suffix = style(DIM, f" [{default}]") if default else ""
    while True:
        value = input(f"{style(YELLOW, '?')} {style(BOLD, label)}{suffix}: ").strip()
        if value:
            return value
        if default:
            return default


def confirm(label: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    value = input(f"{style(YELLOW, '?')} {style(BOLD, label)} {style(DIM, f'[{hint}]')}: ").strip().lower()
    if not value:
        return default
    return value in ("y", "yes")


# --- key pair -----------------------------------------------------------------


def key_paths(name: str) -> tuple[Path, Path]:
    return KEY_DIR / f"{name}.p8", KEY_DIR / f"{name}.pub"


def generate_key_pair(name: str, passphrase: str = "", key_dir: Path = KEY_DIR) -> tuple[Path, Path]:
    """Write <key_dir>/<name>.p8 (PKCS#8 PEM, owner-only permissions) and <name>.pub."""
    private_path, public_path = key_dir / f"{name}.p8", key_dir / f"{name}.pub"
    key_dir.mkdir(parents=True, exist_ok=True)
    key_dir.chmod(stat.S_IRWXU)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    encryption: serialization.KeySerializationEncryption = (
        serialization.BestAvailableEncryption(passphrase.encode()) if passphrase else serialization.NoEncryption()
    )
    private_path.write_bytes(
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, encryption)
    )
    private_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    public_path.write_bytes(
        key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    )
    return private_path, public_path


def public_key_body(public_path: Path) -> str:
    """The base64 body of a PEM public key: what ALTER USER ... SET RSA_PUBLIC_KEY expects."""
    return "".join(line.strip() for line in public_path.read_text().splitlines() if not line.startswith("-----"))


def key_is_encrypted(private_path: Path) -> bool:
    try:
        serialization.load_pem_private_key(private_path.read_bytes(), password=None)
    except TypeError:
        return True
    return False


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9.-]+", "_", value).strip("_").lower()


# --- connections --------------------------------------------------------------


CONTEXT_SQL = "SELECT CURRENT_USER(), CURRENT_ROLE(), CURRENT_WAREHOUSE(), CURRENT_DATABASE()"


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def account_users(conn: Any) -> set[str]:
    """Upper-cased names of the users in the account (SHOW USERS; the bootstrap runs it as ACCOUNTADMIN)."""
    cursor = conn.cursor().execute("SHOW USERS")
    name = [d[0].lower() for d in cursor.description].index("name")
    return {str(row[name]).upper() for row in cursor.fetchall()}


def granted_project_roles(conn: Any, user: str) -> list[str]:
    """The RL_<PROJECT>_<ENV>__<PURPOSE> roles granted to a user (directly)."""
    cursor = conn.cursor().execute(f"SHOW GRANTS TO USER {quote_ident(user)}")
    columns = [d[0].lower() for d in cursor.description]
    roles: set[str] = set()
    for row in cursor.fetchall():
        record = dict(zip(columns, row, strict=False))
        # Older accounts return a `role` column; newer ones `privilege=USAGE granted_on=ROLE name=<role>`.
        name = record.get("role") or (record.get("name") if record.get("granted_on") == "ROLE" else None)
        if isinstance(name, str) and PROJECT_ROLE.match(name):
            roles.add(name)
    return sorted(roles)


def role_sort_key(role: str) -> tuple[int, int, str]:
    match = PROJECT_ROLE.match(role)
    assert match is not None
    env, purpose = match["env"], match["purpose"]
    env_rank = ENVIRONMENT_ORDER.index(env) if env in ENVIRONMENT_ORDER else len(ENVIRONMENT_ORDER)
    purpose_rank = PURPOSE_ORDER.index(purpose) if purpose in PURPOSE_ORDER else len(PURPOSE_ORDER)
    return (env_rank, purpose_rank, role)


def context_for_role(role: str) -> dict[str, str]:
    """Role -> the project database, default warehouse and environment that go with it."""
    match = PROJECT_ROLE.match(role)
    if match is None:
        raise ValueError(f"{role} is not a project role (RL_<PROJECT>_<ENV>__<PURPOSE>)")
    project, env = match["project"], match["env"]
    return {
        "role": role,
        "database": f"DB_{project}_{env}",
        "warehouse": f"WH_{project}_{env}",
        "environment": env.lower(),
    }


def choose_role(roles: list[str], wanted: str | None, interactive: bool) -> str | None:
    """Pick a project role: the requested one, the only one, or the engineer role of the lowest environment."""
    if not roles:
        return None
    if wanted:
        if wanted.upper() not in roles:
            sys.exit(f"{wanted} is not granted to you; granted project roles: {', '.join(roles)}")
        return wanted.upper()
    ordered = sorted(roles, key=role_sort_key)
    if len(ordered) == 1 or not interactive:
        return ordered[0]
    print("Project roles granted to you:")
    for index, role in enumerate(ordered, 1):
        print(f"  {index}. {role}")
    return ordered[int(ask(f"Pick one [1-{len(ordered)}]", "1")) - 1]


def discover_context(
    conn: Any, settings: SnowflakeSettings, wanted_role: str | None, interactive: bool
) -> SnowflakeSettings:
    """Fill role, warehouse, database and environment from the project roles granted to the user."""
    roles = granted_project_roles(conn, settings.user)
    role = choose_role(roles, wanted_role, interactive)
    if role is None:
        print("No project role (RL_<PROJECT>_<ENV>__<PURPOSE>) is granted to you yet; keeping the current values.")
        return settings
    found = context_for_role(role)
    print(f"Project role {role}: database {found['database']}, warehouse {found['warehouse']}")
    return dataclasses.replace(
        settings,
        role=found["role"],
        warehouse=found["warehouse"],
        database=found["database"],
        environment=found["environment"],
        schema=resolve_prefix(settings.schema, settings.user),
    )


def interactive_connect(account: str, user: str, auth: str) -> Any:
    """The one-time interactive login: browser (SSO / Snowflake login page) or password + MFA."""
    import snowflake.connector

    common = {"account": account, "user": user, "application": APPLICATION}
    if auth == "browser":
        print("Opening your browser for the Snowflake login (SSO or the Snowflake login page)...")
        return snowflake.connector.connect(authenticator="externalbrowser", **common)
    password = getpass.getpass("Snowflake password: ")
    passcode = input("MFA passcode (leave empty for a push notification): ").strip()
    extra = {"passcode": passcode} if passcode else {}
    return snowflake.connector.connect(password=password, **common, **extra)


def load_settings(required: tuple[str, ...] = SnowflakeSettings.REQUIRED) -> SnowflakeSettings:
    """Settings from .env plus the process environment (the latter wins, as `just` loads .env too)."""
    file_values = {k: (v or "") for k, v in dotenv_values(ENV_FILE).items()} if ENV_FILE.exists() else {}
    settings = SnowflakeSettings.from_env({**file_values, **os.environ})
    missing = settings.missing(required)
    if missing:
        sys.exit(f"Missing in .env: {', '.join(missing)}. Run `just sf setup` first.")
    if not settings.key_path().exists():
        sys.exit(f"Private key not found: {settings.key_path()}. Run `just sf setup` again.")
    return settings


def verify(settings: SnowflakeSettings) -> bool:
    """Connect with the key pair and print the resolved context."""
    try:
        with settings.connect() as conn:
            user, role, warehouse, database, version = (
                conn.cursor().execute(f"{CONTEXT_SQL}, CURRENT_VERSION()").fetchone()
            )
    except Exception as exc:  # noqa: BLE001 - report whatever the connector raises
        print(f"Key-pair login failed: {exc}")
        return False
    ok(f"Key-pair login OK: user={user} role={role} warehouse={warehouse} database={database}")
    print(f"Snowflake version {version}")
    return True


def personal_prefix(user: str) -> str:
    """Prefix of the personal schemas Terraform provisions for `user` (terraform/personal.tf).

    The `schema_prefix` of the user's file under terraform/config/users, else DBT_<first part of the
    login>: DBT_USERNAME for username@example.com.
    """
    for path in sorted((TF_DIR / "config" / "users").glob("*.yaml")):
        config = yaml.safe_load(path.read_text()) or {}
        if str(config.get("login", "")).upper() == user.upper() and config.get("schema_prefix"):
            return str(config["schema_prefix"]).upper()
    return "DBT_" + re.sub(r"[^A-Za-z0-9]+", "_", user.split("@")[0]).strip("_").upper()


def resolve_prefix(current: str, user: str) -> str:
    """The prefix from .env, or one derived from the login while .env still holds what .env.example ships."""
    return current if current and current.upper() not in PLACEHOLDER_SCHEMAS else personal_prefix(user)


def prompt_context(settings: SnowflakeSettings) -> SnowflakeSettings:
    """Confirm role, warehouse, database and schema prefix (defaults come from your user's settings)."""
    print("Your development context (press Enter to keep the defaults):")
    return dataclasses.replace(
        settings,
        role=ask("  Role (RL_<PROJECT>_DEV__ENG)", settings.role or None),
        warehouse=ask("  Warehouse (WH_<PROJECT>_DEV)", settings.warehouse or None),
        database=ask("  Database (DB_<PROJECT>_DEV)", settings.database or None),
        # Terraform creates the personal schemas; another prefix needs `schema_prefix` in your
        # terraform/config/users file and an apply first.
        schema=ask("  Personal schema prefix", settings.schema or personal_prefix(settings.user)),
    )


def write_settings(settings: SnowflakeSettings) -> None:
    if not ENV_FILE.exists():
        shutil.copy(ENV_EXAMPLE, ENV_FILE)
    update_env_file(
        ENV_FILE,
        {
            "SNOWFLAKE_ACCOUNT": settings.account,
            "SNOWFLAKE_USER": settings.user,
            "SNOWFLAKE_PRIVATE_KEY_PATH": settings.key_path().as_posix(),
            "SNOWFLAKE_PRIVATE_KEY_PASSPHRASE": settings.private_key_passphrase,
            "SNOWFLAKE_ROLE": settings.role,
            "SNOWFLAKE_WAREHOUSE": settings.warehouse,
            "SNOWFLAKE_DATABASE": settings.database,
            "SNOWFLAKE_SCHEMA": settings.schema,
            "ENVIRONMENT": settings.environment,
        },
    )
    ok(f"Wrote {ENV_FILE}")


# --- setup steps --------------------------------------------------------------


def register_key_pair(conn: Any, user: str, key_name: str, slot: str, ask_passphrase: bool) -> tuple[Path, str] | None:
    """Create (or keep) the key pair <key_name> and register its public key on `user`; None when Snowflake refuses."""
    private_path, public_path = key_paths(key_name)
    passphrase = ""
    if private_path.exists() and confirm(f"{private_path} exists. Keep it and register it again?"):
        if key_is_encrypted(private_path):
            passphrase = getpass.getpass("Passphrase of the existing key: ")
    else:
        if ask_passphrase:
            passphrase = getpass.getpass("Passphrase for the new key (empty for none): ")
            if passphrase and passphrase != getpass.getpass("Repeat passphrase: "):
                sys.exit("Passphrases differ, aborting.")
        generate_key_pair(key_name, passphrase)
        ok(f"Wrote {private_path} and {public_path}")
    try:
        conn.cursor().execute(f"ALTER USER {quote_ident(user)} SET {slot} = '{public_key_body(public_path)}'")
    except Exception as exc:  # noqa: BLE001 - surface the Snowflake error with guidance
        print(f"Could not set {slot} on {user}: {exc}")
        return None
    ok(f"{slot} set on {user}")
    return private_path, passphrase


def finish_settings(settings: SnowflakeSettings, args: argparse.Namespace) -> int:
    """Discover the project context with the key pair, confirm it, verify the login and write .env."""
    with settings.connect(role=None, warehouse=None, database=None) as conn:
        settings = discover_context(conn, settings, args.role, interactive=not args.yes)
    if not args.yes:
        settings = prompt_context(settings)
    if not verify(settings):
        return 1
    write_settings(settings)
    return 0


def provisioning_sql(public_key: str, slot: str) -> str:
    """init.sql with the Terraform user's public key filled in (the commented RSA_PUBLIC_KEY line)."""
    sql, count = re.subn(r"^\s*--RSA_PUBLIC_KEY = '.*$", f"  {slot} = '{public_key}'", INIT_SQL.read_text(), flags=re.M)
    if count != 1:
        sys.exit(f"Expected exactly one commented RSA_PUBLIC_KEY line in {INIT_SQL}, found {count}")
    return sql


def ensure_user_config(login: str, account_users: set[str]) -> None:
    """Write terraform/config/users/<login>.yaml (engineer in dev on every project) unless a file lists the login.

    Warns about every enabled `create: false` file whose login is not in `account_users` (upper-cased names
    from SHOW USERS): Terraform fails with "object does not exist or not authorized" on its grants.
    """
    users_dir, projects_dir = TF_DIR / "config" / "users", TF_DIR / "config" / "projects"
    listed = False
    for existing in sorted(users_dir.glob("*.yaml")):
        user = yaml.safe_load(existing.read_text()) or {}
        other = str(user.get("login", ""))
        if user.get("disabled") or not other:
            continue
        if other.upper() == login.upper():
            print(f"{existing} already lists {login}")
            listed = True
        elif other.upper() not in account_users and not user.get("create"):
            warn(
                f"{existing} lists {other}, which does not exist in this account: Terraform will fail on its "
                "grants. Delete the file or set `disabled: true`."
            )
    if listed:
        return
    roles = "".join(
        f"  - project: {project.stem}\n    role: engineer\n    environments:\n      - development\n"
        for project in sorted(projects_dir.glob("*.yaml"))
    )
    path = users_dir / f"{safe_name(login)}.yaml"
    path.write_text(
        "# yaml-language-server: $schema=../_validation/schemas/user.schema.json\n"
        f"# Written by `just sf bootstrap` for {login}.\n\n"
        f'login: "{login}"\ncreate: false\nroles:\n{roles}'
    )
    ok(f"Wrote {path}")


def refresh_windows_path() -> None:
    """Pick up PATH entries an installer (winget) wrote to the registry after this shell started."""
    if sys.platform != "win32":
        return
    import winreg

    keys = [
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
        (winreg.HKEY_CURRENT_USER, "Environment"),
    ]
    current = os.environ.get("PATH", "").split(os.pathsep)
    for hive, subkey in keys:
        try:
            with winreg.OpenKey(hive, subkey) as key:
                value = os.path.expandvars(winreg.QueryValueEx(key, "Path")[0])
        except OSError:
            continue
        current += [p for p in value.split(os.pathsep) if p and p not in current]
    os.environ["PATH"] = os.pathsep.join(current)


def terraform(env: dict[str, str], *args: str) -> None:
    subprocess.run(["terraform", *args], cwd=TF_DIR, env=env, check=True)


# Resource types an earlier Terraform state may already have created in the account: type -> (label, the
# plan attributes that name the object, outermost first). Grants are left out: granting again is a no-op.
ADOPTABLE = {
    "snowflake_database": ("database", ("name",)),
    "snowflake_schema": ("schema", ("database", "name")),
    "snowflake_stage_internal": ("stage", ("database", "schema", "name")),
    "snowflake_warehouse": ("warehouse", ("name",)),
    "snowflake_account_role": ("role", ("name",)),
    "snowflake_user": ("user", ("name",)),
}


# The system role Terraform creates each type as (terraform/providers.tf), so the owner an adopted object needs.
OWNER = {
    "snowflake_database": "SYSADMIN",
    "snowflake_schema": "SYSADMIN",
    "snowflake_stage_internal": "SYSADMIN",
    "snowflake_warehouse": "SYSADMIN",
    "snowflake_account_role": "SECURITYADMIN",
    "snowflake_user": "USERADMIN",
}


def object_path(resource: dict[str, Any]) -> tuple[str, ...]:
    return tuple(str(resource[attr]) for attr in ADOPTABLE[resource["type"]][1])


def planned_creates(env: dict[str, str]) -> list[dict[str, Any]]:
    """The adoptable resources `terraform plan` would create: address, type and planned attributes."""

    def run(*args: str) -> str:
        result = subprocess.run(["terraform", *args], cwd=TF_DIR, env=env, capture_output=True, encoding="utf-8")
        if result.returncode != 0:
            print(result.stdout + result.stderr)
            sys.exit(f"terraform {args[0]} failed")
        return result.stdout

    with tempfile.TemporaryDirectory() as tmp:
        plan = str(Path(tmp) / "plan")
        run("plan", "-input=false", "-no-color", f"-out={plan}")
        shown = run("show", "-json", plan)
    return [
        {"address": change["address"], "type": change["type"], **(change["change"]["after"] or {})}
        for change in json.loads(shown).get("resource_changes", [])
        if change["type"] in ADOPTABLE and change["change"]["actions"] == ["create"]
    ]


def existing_objects(conn: Any, creates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The planned creates that already exist in the account (run as ACCOUNTADMIN, which sees everything)."""

    def names(sql: str, *columns: str) -> set[tuple[str, ...]]:
        cursor = conn.cursor().execute(sql)
        header = [d[0].lower() for d in cursor.description]
        return {tuple(str(row[header.index(c)]) for c in columns) for row in cursor.fetchall()}

    found = {
        "snowflake_database": names("SHOW DATABASES", "name"),
        "snowflake_schema": names("SHOW SCHEMAS IN ACCOUNT", "database_name", "name"),
        "snowflake_stage_internal": names("SHOW STAGES IN ACCOUNT", "database_name", "schema_name", "name"),
        "snowflake_warehouse": names("SHOW WAREHOUSES", "name"),
        "snowflake_account_role": names("SHOW ROLES", "name"),
        "snowflake_user": names("SHOW USERS", "name"),
    }
    return [r for r in creates if object_path(r) in found[r["type"]]]


def write_imports(resources: list[dict[str, Any]]) -> None:
    """Import blocks so the next `terraform apply` adopts `resources` instead of creating them."""
    blocks = "".join(
        f"import {{\n  to = {r['address']}\n  id = {json.dumps('.'.join(map(quote_ident, object_path(r))))}\n}}\n\n"
        for r in resources
    )
    ADOPT_FILE.write_text(f"# Written by `just sf bootstrap` for one apply; deleted afterwards.\n\n{blocks}")


def drop_objects(conn: Any, resources: list[dict[str, Any]], current_user: str) -> None:
    """DROP the objects, innermost first (a database takes its schemas and stages with it)."""
    order = ["snowflake_stage_internal", "snowflake_schema", "snowflake_database"]
    order += ["snowflake_warehouse", "snowflake_account_role", "snowflake_user"]
    for resource in sorted(resources, key=lambda r: order.index(r["type"])):
        kind = ADOPTABLE[resource["type"]][0].upper()
        path = object_path(resource)
        if kind == "USER" and path[0].upper() == current_user.upper():
            continue
        conn.cursor().execute(f"DROP {kind} IF EXISTS {'.'.join(map(quote_ident, path))}")
        ok(f"Dropped {kind.lower()} {'.'.join(path)}")


def transfer_ownership(conn: Any, resources: list[dict[str, Any]]) -> None:
    """Hand adopted objects to the role Terraform manages them as, keeping the grants they have.

    An account provisioned by an earlier version has them owned by RL_PLATFORM_PROVISIONING, which
    init.sql drops (leaving them to ACCOUNTADMIN); personal schemas were owned by the engineer role.
    """
    for resource in resources:
        kind = ADOPTABLE[resource["type"]][0].upper()
        path = ".".join(map(quote_ident, object_path(resource)))
        owner = OWNER[resource["type"]]
        conn.cursor().execute(f"GRANT OWNERSHIP ON {kind} {path} TO ROLE {owner} COPY CURRENT GRANTS")
        ok(f"{kind.lower()} {'.'.join(object_path(resource))} now owned by {owner}")


def reconcile_existing(conn: Any, env: dict[str, str], mode: str, current_user: str, yes: bool) -> bool:
    """Handle objects Terraform would create that already exist (an account provisioned from another checkout).

    `mode` is sync (adopt them into this checkout's state), wipe (drop them, then create them anew) or ask.
    Returns False when the user aborts.
    """
    print("Looking for objects in the account that this checkout's Terraform state does not track...")
    existing = existing_objects(conn, planned_creates(env))
    if not existing:
        ok("None found; Terraform creates everything.")
        return True
    warn(f"{len(existing)} objects Terraform would create already exist (provisioned from another checkout?):")
    for resource in existing:
        print(f"    {ADOPTABLE[resource['type']][0]:<10} {'.'.join(object_path(resource))}")
    if mode == "ask":
        if yes:
            mode = "sync"
        else:
            print("  sync  adopt them into this checkout's Terraform state; data and grants stay, owners become")
            print("        SYSADMIN (databases, schemas, stages, warehouses), SECURITYADMIN (roles), USERADMIN (users)")
            print("  wipe  drop them (databases with all their schemas and data), then provision from scratch")
            choice = ask("sync, wipe or abort?", "sync").lower()
            mode = {"s": "sync", "w": "wipe"}.get(choice[:1], "abort")
    if mode == "sync":
        transfer_ownership(conn, existing)
        write_imports(existing)
        ok(f"Wrote {ADOPT_FILE.name}: the apply below imports them before provisioning the rest")
        return True
    if mode == "wipe" and (yes or ask('Type "wipe" to drop them for good') == "wipe"):
        drop_objects(conn, existing, current_user)
        return True
    print("Aborted; nothing was changed in Snowflake.")
    return False


# --- subcommands --------------------------------------------------------------


def cmd_setup(args: argparse.Namespace) -> int:
    current = {k: (v or "") for k, v in dotenv_values(ENV_FILE).items()} if ENV_FILE.exists() else {}
    account = args.account or ask(
        "Snowflake account (<organization>-<account>, e.g. MYORG-MYACCOUNT)", current.get("SNOWFLAKE_ACCOUNT") or None
    )
    user = args.user or ask("Snowflake user", current.get("SNOWFLAKE_USER") or None)
    slot = "RSA_PUBLIC_KEY" if args.slot == 1 else "RSA_PUBLIC_KEY_2"

    step("1/3 One-time interactive login")
    conn = interactive_connect(account, user, args.auth)
    try:
        exact_user, role, warehouse, database = conn.cursor().execute(CONTEXT_SQL).fetchone()
        ok(f"Logged in as {exact_user} (role {role or 'none'})")

        step("2/3 Key pair, registered on your user")
        key_name = args.key_name or f"{safe_name(account)}__{safe_name(exact_user)}"
        registered = register_key_pair(conn, exact_user, key_name, slot, args.passphrase)
        if registered is None:
            print(
                f"Your account does not let you set your own key. Send {key_paths(key_name)[1]} to a platform "
                "administrator to register (see terraform/README.md), fill in the Snowflake block of "
                ".env by hand, then run `just sf check`."
            )
            return 1
        private_path, passphrase = registered
    finally:
        conn.close()

    step("3/3 Verifying key-pair login and writing .env")
    settings = SnowflakeSettings(
        account=account,
        user=exact_user,
        private_key_path=str(private_path),
        private_key_passphrase=passphrase,
        role=role or current.get("SNOWFLAKE_ROLE", ""),
        warehouse=warehouse or current.get("SNOWFLAKE_WAREHOUSE", ""),
        database=database or current.get("SNOWFLAKE_DATABASE", ""),
        schema=resolve_prefix(current.get("SNOWFLAKE_SCHEMA", ""), exact_user),
    )
    if finish_settings(settings, args):
        return 1
    done("Next: `just sf check`, then `just start` for the Dagster UI.")
    return 0


def cmd_bootstrap(args: argparse.Namespace) -> int:
    """A fresh account (trial or otherwise) from account, user and password to a provisioned project and .env."""
    refresh_windows_path()  # installed by an earlier run, but this shell predates it
    if shutil.which("terraform") is None:
        step("Installing Terraform (just install terraform)")
        subprocess.run(["just", "install", "terraform"], cwd=ROOT, check=True)
        refresh_windows_path()
        if shutil.which("terraform") is None:
            sys.exit("terraform still not on PATH; open a new shell or install it by hand, then rerun `just setup`")
    # A rerun offers what the previous run wrote to .env as defaults (Enter keeps them).
    current = {k: (v or "") for k, v in dotenv_values(ENV_FILE).items()} if ENV_FILE.exists() else {}
    previous_org, _, previous_account = current.get("SNOWFLAKE_ACCOUNT", "").partition("-")
    organization = (
        args.organization
        or ask(
            "Snowflake organization (e.g. MYORG)", current.get("TF_VAR_SNOWFLAKE_ORGANIZATION") or previous_org or None
        )
    ).upper()
    account_name = (
        args.account
        or ask(
            "Snowflake account name within the organization (e.g. MYACCOUNT)",
            current.get("TF_VAR_SNOWFLAKE_ACCOUNT") or previous_account or None,
        )
    ).upper()
    account = f"{organization}-{account_name}"
    user = args.user or ask("Snowflake user (must hold ACCOUNTADMIN)", current.get("SNOWFLAKE_USER") or None)
    slot = "RSA_PUBLIC_KEY" if args.slot == 1 else "RSA_PUBLIC_KEY_2"

    step("1/5 Logging in with your password")
    conn = interactive_connect(account, user, "password")
    try:
        conn.cursor().execute("USE ROLE ACCOUNTADMIN")
        exact_user = conn.cursor().execute("SELECT CURRENT_USER()").fetchone()[0]
        ok(f"Logged in as {exact_user} on {account} (role ACCOUNTADMIN)")

        step("2/5 Account settings, Terraform service user, warehouse and database (init.sql)")
        tf_private, tf_public = key_paths(TERRAFORM_KEY)
        if not tf_private.exists():
            generate_key_pair(TERRAFORM_KEY)
            ok(f"Wrote {tf_private} and {tf_public}")
        for cursor in conn.execute_string(provisioning_sql(public_key_body(tf_public), slot)):
            cursor.close()
        ok(f"TERRAFORM_USER ready, {slot} set from {tf_public}")

        step("3/5 Your own key pair")
        key_name = args.key_name or f"{safe_name(account)}__{safe_name(exact_user)}"
        registered = register_key_pair(conn, exact_user, key_name, slot, args.passphrase)
        if registered is None:
            return 1
        private_path, passphrase = registered

        step("4/5 Provisioning the projects with Terraform")
        ensure_user_config(exact_user, account_users(conn))
        tf_vars = {
            "SNOWFLAKE_ORGANIZATION": organization,
            "SNOWFLAKE_ACCOUNT": account_name,
            "SNOWFLAKE_USER": "TERRAFORM_USER",
            "SNOWFLAKE_PRIVATE_KEY_PATH": tf_private.as_posix(),
        }
        if not ENV_FILE.exists():
            shutil.copy(ENV_EXAMPLE, ENV_FILE)
        update_env_file(ENV_FILE, {f"TF_VAR_{k}": v for k, v in tf_vars.items()})
        env = {**os.environ, **{f"TF_VAR_{k}": v for k, v in tf_vars.items()}}
        terraform(env, "init", "-input=false")
        # Still logged in as ACCOUNTADMIN here, which can see (and drop) whatever an earlier state created.
        if not reconcile_existing(conn, env, args.existing, exact_user, args.yes):
            return 1
    finally:
        conn.close()
    try:
        terraform(env, "apply", *(["-auto-approve"] if args.yes else []))
    finally:
        ADOPT_FILE.unlink(missing_ok=True)

    step("5/5 Verifying key-pair login and writing .env")
    settings = SnowflakeSettings(
        account=account,
        user=exact_user,
        private_key_path=str(private_path),
        private_key_passphrase=passphrase,
        schema=personal_prefix(exact_user),
    )
    if finish_settings(settings, args):
        return 1
    done("Next: `just sf check`, then `just start` for the Dagster UI.")
    return 0


def cmd_wizard(_args: argparse.Namespace) -> int:
    """`just setup`: one question, then either the fresh-account bootstrap or the key-pair setup."""
    step("Snowflake setup")
    fresh = style(f"{BOLD};{CYAN}", "Fresh account")
    provisioned = style(f"{BOLD};{CYAN}", "Provisioned account")
    existing = style(f"{BOLD};{CYAN}", "Existing account")
    print(f"  {style(BOLD, '1')}  {fresh}: nothing provisioned yet, you hold ACCOUNTADMIN (a trial, for example).")
    print(style(DIM, "     Installs Terraform if missing, bootstraps the service user, provisions the projects,"))
    print(style(DIM, "     registers your key pair and writes .env."))
    print(f"  {style(BOLD, '2')}  {provisioned}: an administrator ran Terraform and granted you a project role.")
    print(style(DIM, "     Registers your key pair and writes .env."))
    print(f"  {style(BOLD, '3')}  {existing}: you hold ACCOUNTADMIN and provisioned it before, from another")
    print(style(DIM, "     checkout or machine, so this checkout's Terraform state does not know the objects."))
    print(style(DIM, "     Like 1, but first asks to sync the existing objects into Terraform or wipe them."))
    print()
    choice = ask("Which one is this? (1/2/3)", "1").strip()
    if choice == "3":
        return main(["bootstrap", "--existing", "ask"])
    return main(["bootstrap"] if choice == "1" else ["setup"])


def cmd_context(args: argparse.Namespace) -> int:
    """Re-point .env at a project without logging in again (the key pair does the work)."""
    settings = load_settings(required=SnowflakeSettings.CREDENTIALS)
    with settings.connect(role=None, warehouse=None, database=None) as conn:
        settings = discover_context(conn, settings, args.role, interactive=not args.yes)
    if not args.yes:
        settings = prompt_context(settings)
    if not verify(settings):
        return 1
    write_settings(settings)
    done("Next: `just sf check`, then restart `just start` so Dagster reads the new .env.")
    return 0


def cmd_check(_args: argparse.Namespace) -> int:
    settings = load_settings()
    print(f"Private key: {settings.key_path()}")
    with settings.connect() as conn:
        row = (
            conn.cursor()
            .execute(
                "SELECT CURRENT_ORGANIZATION_NAME(), CURRENT_ACCOUNT_NAME(), CURRENT_USER(), CURRENT_ROLE(), "
                "CURRENT_WAREHOUSE(), CURRENT_DATABASE(), CURRENT_SCHEMA(), CURRENT_VERSION()"
            )
            .fetchone()
        )
        labels = ("organization", "account", "user", "role", "warehouse", "database", "schema", "version")
        for label, value in zip(labels, row, strict=True):
            if label == "schema" and settings.is_personal:
                value = f"{settings.schema} (personal prefix)"
            print(f"{label:<13} {value}")
        schemas = [
            r[1] for r in conn.cursor().execute(f"SHOW TERSE SCHEMAS IN DATABASE {settings.database}").fetchall()
        ]
        print(f"schemas       {', '.join(schemas) if schemas else '(none yet)'}")
        layers = f"{settings.schema_for_layer('src')}, {settings.schema_for_layer('stg')}, ..."
        print(f"layer schemas {layers} ({settings.environment})")
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    settings = load_settings()
    with settings.connect() as conn:
        cursor = conn.cursor().execute(args.sql)
        print(*(d[0] for d in cursor.description), sep="\t")
        rows = cursor.fetchmany(args.limit)
    for row in rows:
        print(*row, sep="\t")
    print(f"({len(rows)} row{'s' if len(rows) != 1 else ''}{', limited' if len(rows) == args.limit else ''})")
    return 0


def cmd_keygen(args: argparse.Namespace) -> int:
    private_path, public_path = key_paths(args.name)
    if private_path.exists() and not args.force:
        print(f"{private_path} exists; pass --force to overwrite it.")
        return 1
    passphrase = ""
    if args.passphrase:
        passphrase = getpass.getpass("Passphrase (empty for none): ")
        if passphrase and passphrase != getpass.getpass("Repeat passphrase: "):
            print("Passphrases differ, aborting.")
            return 1
    generate_key_pair(args.name, passphrase)
    print(f"Wrote {private_path} and {public_path}\n")
    print("Public key body, for CREATE USER ... RSA_PUBLIC_KEY = '...' (see terraform/init.sql):\n")
    print(public_key_body(public_path))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="just sf", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)

    wizard = sub.add_parser("wizard", help="`just setup`: asks fresh or provisioned account, then bootstrap or setup")
    wizard.set_defaults(func=cmd_wizard)

    bootstrap = sub.add_parser("bootstrap", help="fresh account: Terraform user, provisioning, your key pair, .env")
    bootstrap.add_argument("--organization", help="organization name, the part before the dash; asked when omitted")
    bootstrap.add_argument("--account", help="account name within the organization, after the dash; asked when omitted")
    bootstrap.add_argument("--user", help="Snowflake user holding ACCOUNTADMIN; asked interactively when omitted")
    bootstrap.add_argument("--key-name", help="file name under ~/.snowflake/keys (default: <account>__<user>)")
    bootstrap.add_argument("--passphrase", action="store_true", help="encrypt your private key with a passphrase")
    bootstrap.add_argument(
        "--slot", type=int, choices=(1, 2), default=1, help="RSA_PUBLIC_KEY (1) or RSA_PUBLIC_KEY_2 (2)"
    )
    bootstrap.add_argument("--role", help="project role to work as (default: your engineer role in dev)")
    bootstrap.add_argument(
        "--yes", action="store_true", help="terraform apply -auto-approve and skip the context prompt"
    )
    bootstrap.add_argument(
        "--existing",
        choices=("ask", "sync", "wipe"),
        default="ask",
        help="objects Terraform would create that already exist: adopt them (sync), drop them first (wipe), "
        "or ask (default; --yes picks sync)",
    )
    bootstrap.set_defaults(func=cmd_bootstrap)

    setup = sub.add_parser("setup", help="one-time key-pair setup for your own user")
    setup.add_argument("--account", help="<organization>-<account>; asked interactively when omitted")
    setup.add_argument("--user", help="Snowflake user; asked interactively when omitted")
    setup.add_argument("--auth", choices=("browser", "password"), default="browser", help="interactive login method")
    setup.add_argument("--key-name", help="file name under ~/.snowflake/keys (default: <account>__<user>)")
    setup.add_argument("--passphrase", action="store_true", help="encrypt the private key with a passphrase")
    setup.add_argument("--slot", type=int, choices=(1, 2), default=1, help="RSA_PUBLIC_KEY (1) or RSA_PUBLIC_KEY_2 (2)")
    setup.add_argument("--role", help="project role to work as (default: your engineer role in dev)")
    setup.add_argument("--yes", action="store_true", help="skip the role/warehouse/database confirmation")
    setup.set_defaults(func=cmd_setup)

    context = sub.add_parser("context", help="pick the project to work in and update .env, no login needed")
    context.add_argument("--role", help="project role to work as (default: your engineer role in dev)")
    context.add_argument("--yes", action="store_true", help="take the defaults without asking")
    context.set_defaults(func=cmd_context)

    check = sub.add_parser("check", help="connect with the key pair from .env and print who you are")
    check.set_defaults(func=cmd_check)

    query = sub.add_parser("query", help="run one SQL statement with the key pair from .env")
    query.add_argument("sql")
    query.add_argument("--limit", type=int, default=50)
    query.set_defaults(func=cmd_query)

    keygen = sub.add_parser("keygen", help="generate a key pair without logging in (service users)")
    keygen.add_argument("name", help="file name under ~/.snowflake/keys, e.g. terraform")
    keygen.add_argument("--passphrase", action="store_true", help="encrypt the private key with a passphrase")
    keygen.add_argument("--force", action="store_true", help="overwrite an existing key pair")
    keygen.set_defaults(func=cmd_keygen)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
