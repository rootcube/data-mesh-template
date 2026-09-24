"""Snowflake key-pair authentication for the platform.

    just snowflake setup              one-time: log in interactively, create + register a key pair, write .env
    just snowflake context            pick the project you work in (from the roles granted to you) and write
                                      role, warehouse, database and schema prefix to .env; no login needed
    just snowflake check              connect with the key pair from .env and print who you are
    just snowflake query "SELECT 1"   run one statement with the key pair from .env
    just snowflake keygen <name>      create a key pair only (for service users such as the Terraform user)

`setup` needs exactly one interactive login: your browser (SSO or the Snowflake login page,
the default) or your password plus MFA (`--auth password`). It then generates an RSA key
pair under ~/.snowflake/keys/, registers the public key on your own user with
ALTER USER ... SET RSA_PUBLIC_KEY, verifies that key-pair login works, and writes the
connection settings to .env for dbt, dlt and Dagster.

A person's SNOWFLAKE_ROLE is their engineer role in the project (RL_<PROJECT>_DEV__ENG),
SNOWFLAKE_DATABASE the development database (DB_<PROJECT>_DEV) and SNOWFLAKE_SCHEMA the prefix
of their personal schemas (DBT_<NAME>); see terraform/README.md for how those are provisioned.
Both `setup` and `context` derive those from the project roles granted to the user.
"""

from __future__ import annotations

import argparse
import dataclasses
import getpass
import os
import re
import shutil
import stat
import sys
from pathlib import Path
from typing import Any

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
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"
KEY_DIR = Path.home() / ".snowflake" / "keys"

# --- console helpers ----------------------------------------------------------


def step(title: str) -> None:
    print(f"\n== {title}")


def ask(label: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        value = input(f"{label}{suffix}: ").strip()
        if value:
            return value
        if default:
            return default


def confirm(label: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    value = input(f"{label} [{hint}]: ").strip().lower()
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
        # A bare "DBT" is the pre-project placeholder, not a personal prefix.
        schema=settings.schema
        if settings.schema and settings.schema.upper() != "DBT"
        else personal_prefix(settings.user),
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
        sys.exit(f"Missing in .env: {', '.join(missing)}. Run `just snowflake setup` first.")
    if not settings.key_path().exists():
        sys.exit(f"Private key not found: {settings.key_path()}. Run `just snowflake setup` again.")
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
    print(f"Key-pair login OK: user={user} role={role} warehouse={warehouse} database={database}")
    print(f"Snowflake version {version}")
    return True


def personal_prefix(user: str) -> str:
    """Default prefix for personal schemas: DBT_<first part of the login>, e.g. DBT_INFO."""
    return "DBT_" + re.sub(r"[^A-Za-z0-9]+", "_", user.split("@")[0]).strip("_").upper()


def prompt_context(settings: SnowflakeSettings) -> SnowflakeSettings:
    """Confirm role, warehouse, database and schema prefix (defaults come from your user's settings)."""
    print("Your development context (press Enter to keep the defaults):")
    return dataclasses.replace(
        settings,
        role=ask("  Role (RL_<PROJECT>_DEV__ENG)", settings.role or None),
        warehouse=ask("  Warehouse (WH_<PROJECT>_DEV)", settings.warehouse or None),
        database=ask("  Database (DB_<PROJECT>_DEV)", settings.database or None),
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
            "SNOWFLAKE_PRIVATE_KEY_PATH": str(settings.key_path()),
            "SNOWFLAKE_PRIVATE_KEY_PASSPHRASE": settings.private_key_passphrase,
            "SNOWFLAKE_ROLE": settings.role,
            "SNOWFLAKE_WAREHOUSE": settings.warehouse,
            "SNOWFLAKE_DATABASE": settings.database,
            "SNOWFLAKE_SCHEMA": settings.schema,
            "ENVIRONMENT": settings.environment,
        },
    )
    print(f"Wrote {ENV_FILE}")


# --- subcommands --------------------------------------------------------------


def cmd_setup(args: argparse.Namespace) -> int:
    current = {k: (v or "") for k, v in dotenv_values(ENV_FILE).items()} if ENV_FILE.exists() else {}
    account = args.account or ask(
        "Snowflake account (<organization>-<account>, e.g. MYORG-MYACCOUNT)", current.get("SNOWFLAKE_ACCOUNT") or None
    )
    user = args.user or ask("Snowflake user", current.get("SNOWFLAKE_USER") or None)

    step("1/4 One-time interactive login")
    conn = interactive_connect(account, user, args.auth)
    try:
        exact_user, role, warehouse, database = conn.cursor().execute(CONTEXT_SQL).fetchone()
        print(f"Logged in as {exact_user} (role {role or 'none'})")

        step("2/4 Key pair")
        key_name = args.key_name or f"{safe_name(account)}__{safe_name(exact_user)}"
        private_path, public_path = key_paths(key_name)
        passphrase = ""
        if private_path.exists() and confirm(f"{private_path} exists. Keep it and register it again?"):
            if key_is_encrypted(private_path):
                passphrase = getpass.getpass("Passphrase of the existing key: ")
        else:
            if args.passphrase:
                passphrase = getpass.getpass("Passphrase for the new key (empty for none): ")
                if passphrase and passphrase != getpass.getpass("Repeat passphrase: "):
                    print("Passphrases differ, aborting.")
                    return 1
            generate_key_pair(key_name, passphrase)
            print(f"Wrote {private_path} and {public_path}")

        step("3/4 Registering the public key on your user")
        slot = "RSA_PUBLIC_KEY" if args.slot == 1 else "RSA_PUBLIC_KEY_2"
        try:
            conn.cursor().execute(f"ALTER USER {quote_ident(exact_user)} SET {slot} = '{public_key_body(public_path)}'")
        except Exception as exc:  # noqa: BLE001 - surface the Snowflake error with guidance
            print(f"Could not set {slot} on {exact_user}: {exc}")
            print(
                f"Your account does not let you set your own key. Send {public_path} to a platform "
                "administrator to register (see terraform/README.md), fill in the Snowflake block of "
                ".env by hand, then run `just snowflake check`."
            )
            return 1
        print(f"{slot} set on {exact_user}")
    finally:
        conn.close()

    step("4/4 Verifying key-pair login and writing .env")
    settings = SnowflakeSettings(
        account=account,
        user=exact_user,
        private_key_path=str(private_path),
        private_key_passphrase=passphrase,
        role=role or current.get("SNOWFLAKE_ROLE", ""),
        warehouse=warehouse or current.get("SNOWFLAKE_WAREHOUSE", ""),
        database=database or current.get("SNOWFLAKE_DATABASE", ""),
        schema=current.get("SNOWFLAKE_SCHEMA") or personal_prefix(exact_user),
    )
    with settings.connect(role=None, warehouse=None, database=None) as conn:
        settings = discover_context(conn, settings, args.role, interactive=not args.yes)
    if not args.yes:
        settings = prompt_context(settings)
    if not verify(settings):
        return 1
    write_settings(settings)
    print("\nDone. Next: `just snowflake check`, then `just start` for the Dagster UI.")
    return 0


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
    print("\nDone. Next: `just snowflake check`, then restart `just start` so Dagster reads the new .env.")
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
        prog="just snowflake", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)

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
