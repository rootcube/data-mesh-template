import argparse
import base64
import dataclasses
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from dotenv import dotenv_values
from snowflake.connector.errors import ProgrammingError

from orchestrator.resources.snowflake import SnowflakeSettings

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "snowflake.py"


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("snowflake_script", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["snowflake_script"] = module
    spec.loader.exec_module(module)
    return module


def test_generate_key_pair_writes_loadable_pkcs8_and_public_body(tmp_path: Path) -> None:
    script = load_script()
    private_path, public_path = script.generate_key_pair("unit", key_dir=tmp_path)
    key = serialization.load_pem_private_key(private_path.read_bytes(), password=None)
    assert isinstance(key, rsa.RSAPrivateKey)
    assert key.key_size == 2048
    body = script.public_key_body(public_path)
    assert body.startswith("MIIB") and "-----" not in body and "\n" not in body
    assert script.key_is_encrypted(private_path) is False
    if sys.platform != "win32":
        # The one security behaviour of the key pair: nobody but the owner reads the private key.
        assert private_path.stat().st_mode & 0o777 == 0o600
        assert tmp_path.stat().st_mode & 0o777 == 0o700


def test_generate_key_pair_with_passphrase_is_encrypted(tmp_path: Path) -> None:
    script = load_script()
    private_path, _ = script.generate_key_pair("secret", passphrase="hunter2", key_dir=tmp_path)
    assert script.key_is_encrypted(private_path) is True


def test_project_role_discovery_prefers_engineer_in_dev() -> None:
    script = load_script()
    roles = ["RL_EXAMPLE_PRD__ANL", "RL_EXAMPLE_DEV__ENG", "RL_OTHER_DEV__ANL"]
    assert script.choose_role(roles, wanted=None, interactive=False) == "RL_EXAMPLE_DEV__ENG"
    assert script.choose_role(roles, wanted="rl_other_dev__anl", interactive=False) == "RL_OTHER_DEV__ANL"
    assert script.choose_role([], wanted=None, interactive=False) is None
    assert script.context_for_role("RL_EXAMPLE_DEV__ENG") == {
        "role": "RL_EXAMPLE_DEV__ENG",
        "database": "DB_EXAMPLE_DEV",
        "warehouse": "WH_EXAMPLE_DEV",
        "environment": "dev",
    }


def test_provisioning_sql_fills_in_the_terraform_key() -> None:
    script = load_script()
    sql = script.provisioning_sql("MIIBkey", "RSA_PUBLIC_KEY")
    assert "  RSA_PUBLIC_KEY = 'MIIBkey'" in sql
    assert "--RSA_PUBLIC_KEY" not in sql and "INSERT_YOUR" not in sql
    # Without a key (the slot holds it already) init.sql runs as it is, leaving the key alone.
    assert script.provisioning_sql(None, "RSA_PUBLIC_KEY") == script.INIT_SQL.read_text(encoding="utf-8")


def test_ensure_user_config_writes_engineer_grants_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    script = load_script()
    (tmp_path / "config" / "users").mkdir(parents=True)
    (tmp_path / "config" / "projects").mkdir()
    (tmp_path / "config" / "projects" / "example.yaml").write_text("code: example\n")
    monkeypatch.setattr(script, "TF_DIR", tmp_path)
    script.ensure_user_config("USERNAME", {"USERNAME"})
    # users/local/ is git-ignored: the file only describes this account.
    written = tmp_path / "config" / "users" / "local" / "username.yaml"
    assert "$schema=../../_validation/schemas/user.schema.json" in written.read_text()
    assert 'login: "USERNAME"' in written.read_text()
    assert "  - project: example\n    role: engineer\n    environments:\n      - development\n" in written.read_text()
    script.ensure_user_config("username", {"USERNAME"})
    assert len(list((tmp_path / "config" / "users").rglob("*.yaml"))) == 1


def test_ensure_user_config_warns_about_logins_missing_from_the_account(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    script = load_script()
    users = tmp_path / "config" / "users"
    users.mkdir(parents=True)
    (tmp_path / "config" / "projects").mkdir()
    (users / "admin.yaml").write_text('login: "ADMIN"\ncreate: false\nroles: []\n')
    (users / "gone.yaml").write_text('login: "GONE"\ncreate: false\ndisabled: true\nroles: []\n')
    (users / "new.yaml").write_text('login: "NEW"\ncreate: true\nroles: []\n')
    monkeypatch.setattr(script, "TF_DIR", tmp_path)
    script.ensure_user_config("USERNAME", {"USERNAME"})
    out = capsys.readouterr().out
    assert "admin.yaml lists ADMIN, which does not exist in this account" in out
    assert "GONE" not in out and "NEW" not in out


class FakeConnection:
    """Answers the SHOW statements existing_objects runs (and `answers`) and records every other statement.

    Like Snowflake, it raises for DESC USER of a user it has no answer for; statements starting with
    `refuse` raise too.
    """

    SHOW = {
        "SHOW DATABASES": (["name", "owner"], [["DB_EXAMPLE_DEV", "ACCOUNTADMIN"], ["SNOWFLAKE", ""]]),
        "SHOW SCHEMAS IN ACCOUNT": (["database_name", "name", "owner"], [["DB_EXAMPLE_DEV", "_SRC", "SYSADMIN"]]),
        "SHOW STAGES IN ACCOUNT": (
            ["database_name", "schema_name", "name", "owner"],
            [["DB_EXAMPLE_DEV", "_SRC", "ST_DEFAULT", "SYSADMIN"]],
        ),
        "SHOW WAREHOUSES": (["name", "owner"], []),
        "SHOW ROLES": (["name", "owner"], [["RL_EXAMPLE_DEV__ENG", "SECURITYADMIN"]]),
        "SHOW USERS": (["name", "owner"], [["ADMIN", "ACCOUNTADMIN"]]),
    }

    def __init__(self, answers: dict[str, tuple[list[str], list[list[str]]]] | None = None, refuse: str = "") -> None:
        self.executed: list[str] = []
        self.scripts: list[str] = []
        self.answers = {**self.SHOW, **(answers or {})}
        self.refuse = refuse

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def cursor(self) -> "FakeConnection":
        return self

    def execute(self, sql: str) -> "FakeConnection":
        self.executed.append(sql)
        if (self.refuse and sql.startswith(self.refuse)) or (sql.startswith("DESC USER") and sql not in self.answers):
            raise ProgrammingError(f"{sql}: does not exist or not authorized")
        columns, self.rows = self.answers.get(sql, ([], []))
        self.description = [(c,) for c in columns]
        return self

    def execute_string(self, sql: str) -> list["FakeConnection"]:
        self.scripts.append(sql)
        return []

    def fetchall(self) -> list[list[str]]:
        return self.rows

    def fetchone(self) -> list[str] | None:
        return self.rows[0] if self.rows else None

    def close(self) -> None:
        return None


PLANNED = [
    {
        "address": 'module.database["dev"].snowflake_database.this',
        "type": "snowflake_database",
        "name": "DB_EXAMPLE_DEV",
    },
    {
        "address": 'module.database["prd"].snowflake_database.this',
        "type": "snowflake_database",
        "name": "DB_EXAMPLE_PRD",
    },
    {
        "address": 'module.schema["dev_src"].snowflake_schema.this',
        "type": "snowflake_schema",
        "database": "DB_EXAMPLE_DEV",
        "name": "_SRC",
    },
    {
        "address": 'snowflake_stage_internal.default["dev_src"]',
        "type": "snowflake_stage_internal",
        "database": "DB_EXAMPLE_DEV",
        "schema": "_SRC",
        "name": "ST_DEFAULT",
    },
    {
        "address": 'module.warehouse["dev"].snowflake_warehouse.this',
        "type": "snowflake_warehouse",
        "name": "WH_EXAMPLE_DEV",
    },
    {
        "address": 'module.role["dev_eng"].snowflake_account_role.this',
        "type": "snowflake_account_role",
        "name": "RL_EXAMPLE_DEV__ENG",
    },
    {"address": 'snowflake_user.person["admin"]', "type": "snowflake_user", "name": "ADMIN"},
]


def test_existing_objects_matches_planned_creates_by_full_name() -> None:
    script = load_script()
    found = script.existing_objects(FakeConnection(), PLANNED)
    assert [script.object_path(r) for r in found] == [
        ("DB_EXAMPLE_DEV",),
        ("DB_EXAMPLE_DEV", "_SRC"),
        ("DB_EXAMPLE_DEV", "_SRC", "ST_DEFAULT"),
        ("RL_EXAMPLE_DEV__ENG",),
        ("ADMIN",),
    ]


def test_write_imports_uses_quoted_identifiers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    script = load_script()
    monkeypatch.setattr(script, "TF_DIR", tmp_path)
    instance = script.Instance("snowflake-project", "example-dev")
    instance.adopt_file.parent.mkdir(parents=True)
    script.write_imports(instance, [PLANNED[0], PLANNED[3]])
    text = (tmp_path / "components" / "snowflake-project" / "adopt_imports.tf").read_text()
    assert "one apply of stack example-dev" in text
    assert 'import {\n  to = module.database["dev"].snowflake_database.this\n  id = "\\"DB_EXAMPLE_DEV\\""\n}' in text
    assert 'id = "\\"DB_EXAMPLE_DEV\\".\\"_SRC\\".\\"ST_DEFAULT\\""' in text


def test_apply_stack_imports_the_adopted_objects_for_that_one_apply(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The import blocks sit in the component directory, so they exist only while their own stack applies."""
    script = load_script()
    monkeypatch.setattr(script, "TF_DIR", tmp_path)
    instance = script.Instance("snowflake-project", "example-dev")
    instance.adopt_file.parent.mkdir(parents=True)
    seen: list[tuple[tuple[str, ...], bool]] = []
    monkeypatch.setattr(script, "atmos", lambda env, *args: seen.append((args, instance.adopt_file.exists())))
    script.apply_stack({}, instance, [PLANNED[0]], yes=True)
    assert seen == [
        (("terraform", "apply", "snowflake-project", "-s", "example-dev", "--skip-init", "--", "-auto-approve"), True)
    ]
    assert not instance.adopt_file.exists()
    seen.clear()
    script.apply_stack({}, instance, [], yes=False)
    assert seen == [(("terraform", "apply", "snowflake-project", "-s", "example-dev", "--skip-init"), False)]


def test_apply_stacks_stops_at_a_stack_that_was_not_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    """A declined `yes` (Terraform exits 1) ends the bootstrap with the stack's name, not a traceback."""
    script = load_script()
    applied: list[str] = []

    def apply(env: dict[str, str], instance: Any, adopted: list[dict[str, Any]], yes: bool) -> None:
        if instance.stack == "example-dev":
            raise subprocess.CalledProcessError(1, ["atmos", "terraform", "apply"])
        applied.append(instance.stack)

    monkeypatch.setattr(script, "apply_stack", apply)
    stacks = [
        script.Instance("snowflake-account", "account"),
        script.Instance("snowflake-project", "example-dev"),
        script.Instance("snowflake-project", "example-prd"),
    ]
    with pytest.raises(SystemExit, match="Stack example-dev was not applied"):
        script.apply_stacks({}, stacks, {}, yes=False)
    assert applied == ["account"]


def test_instances_put_the_account_stack_first(monkeypatch: pytest.MonkeyPatch) -> None:
    """The project stacks grant roles to the persons the account stack creates."""
    script = load_script()
    described = {
        stack: {"components": {"terraform": {component: {"workspace": stack}}}}
        for stack, component in [
            ("example-prd", "snowflake-project"),
            ("account", "snowflake-account"),
            ("example-dev", "snowflake-project"),
            ("dagster-prd", "dagster"),  # the Kubernetes deployment: not the bootstrap's business
        ]
    }
    monkeypatch.setattr(script, "atmos_output", lambda env, *args: json.dumps(described))
    assert script.instances({}) == [
        script.Instance("snowflake-account", "account"),
        script.Instance("snowflake-project", "example-dev"),
        script.Instance("snowflake-project", "example-prd"),
    ]


def test_drop_objects_takes_ownership_goes_outermost_first_and_spares_the_current_user() -> None:
    script = load_script()
    conn = FakeConnection()
    script.drop_objects(conn, list(reversed(PLANNED)), current_user="admin", take_ownership=True)
    assert conn.executed == [
        'GRANT OWNERSHIP ON DATABASE "DB_EXAMPLE_PRD" TO ROLE SYSADMIN COPY CURRENT GRANTS',
        'DROP DATABASE IF EXISTS "DB_EXAMPLE_PRD"',
        'GRANT OWNERSHIP ON DATABASE "DB_EXAMPLE_DEV" TO ROLE SYSADMIN COPY CURRENT GRANTS',
        'DROP DATABASE IF EXISTS "DB_EXAMPLE_DEV"',
        'GRANT OWNERSHIP ON WAREHOUSE "WH_EXAMPLE_DEV" TO ROLE SYSADMIN COPY CURRENT GRANTS',
        'DROP WAREHOUSE IF EXISTS "WH_EXAMPLE_DEV"',
        'GRANT OWNERSHIP ON ROLE "RL_EXAMPLE_DEV__ENG" TO ROLE SECURITYADMIN COPY CURRENT GRANTS',
        'DROP ROLE IF EXISTS "RL_EXAMPLE_DEV__ENG"',
    ]


def test_drop_objects_drops_a_schema_itself_when_its_database_stays() -> None:
    script = load_script()
    conn = FakeConnection()
    script.drop_objects(conn, [PLANNED[3], PLANNED[2]], current_user="admin", take_ownership=True)
    assert conn.executed == [
        'GRANT OWNERSHIP ON SCHEMA "DB_EXAMPLE_DEV"."_SRC" TO ROLE SYSADMIN COPY CURRENT GRANTS',
        'DROP SCHEMA IF EXISTS "DB_EXAMPLE_DEV"."_SRC"',
    ]


@pytest.mark.parametrize(
    ("answers", "proceeds", "imports", "drops"),
    [
        (["sync"], True, True, False),
        (["wipe", "wipe"], True, False, True),
        (["wipe", "no"], False, False, False),
        (["abort"], False, False, False),
    ],
)
def test_reconcile_existing_asks_to_sync_wipe_or_abort(
    monkeypatch: pytest.MonkeyPatch, answers: list[str], proceeds: bool, imports: bool, drops: bool
) -> None:
    script = load_script()
    monkeypatch.setattr(script, "planned_changes", lambda env, instance: [])
    monkeypatch.setattr(script, "planned_creates", lambda changes: PLANNED)
    replies = iter(answers)
    monkeypatch.setattr("builtins.input", lambda prompt: next(replies))
    conn = FakeConnection()
    stacks = [script.Instance("snowflake-project", "example-dev")]
    adopt = script.reconcile_existing(conn, {}, stacks, "ask", "ADMIN", yes=False)
    assert (adopt is not None) is proceeds
    assert bool(adopt) is imports
    assert any(sql.startswith("DROP") for sql in conn.executed) is drops
    assert any(sql.startswith("GRANT OWNERSHIP") for sql in conn.executed) is proceeds


def test_reconcile_existing_adopts_each_object_into_the_stack_that_plans_it(monkeypatch: pytest.MonkeyPatch) -> None:
    script = load_script()
    account, dev = script.Instance("snowflake-account", "account"), script.Instance("snowflake-project", "example-dev")
    planned = {"account": [PLANNED[6]], "example-dev": [PLANNED[0], PLANNED[1]]}
    monkeypatch.setattr(script, "planned_changes", lambda env, instance: [instance.stack])
    monkeypatch.setattr(script, "forget_vanished_grants", lambda env, instance, changes: None)
    monkeypatch.setattr(script, "planned_creates", lambda changes: planned[changes[0]])
    adopt = script.reconcile_existing(FakeConnection(), {}, [account, dev], "sync", "ADMIN", yes=False)
    # DB_EXAMPLE_PRD does not exist in the account, so Terraform creates it instead of adopting it.
    assert adopt == {account: [PLANNED[6]], dev: [PLANNED[0]]}


def test_sync_hands_adopted_objects_to_the_system_role_terraform_uses() -> None:
    script = load_script()
    conn = FakeConnection()
    script.transfer_ownership(conn, [PLANNED[0], PLANNED[3], PLANNED[5], PLANNED[6]])
    assert conn.executed == [
        'GRANT OWNERSHIP ON DATABASE "DB_EXAMPLE_DEV" TO ROLE SYSADMIN COPY CURRENT GRANTS',
        'GRANT OWNERSHIP ON STAGE "DB_EXAMPLE_DEV"."_SRC"."ST_DEFAULT" TO ROLE SYSADMIN COPY CURRENT GRANTS',
        'GRANT OWNERSHIP ON ROLE "RL_EXAMPLE_DEV__ENG" TO ROLE SECURITYADMIN COPY CURRENT GRANTS',
        'GRANT OWNERSHIP ON USER "ADMIN" TO ROLE USERADMIN COPY CURRENT GRANTS',
    ]


def test_personal_prefix_follows_the_terraform_user_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    script = load_script()
    users = tmp_path / "config" / "users"
    users.mkdir(parents=True)
    (users / "custom.yaml").write_text('login: "jane.doe@example.com"\nschema_prefix: "DBT_JANE"\nroles: []\n')
    (users / "local").mkdir()
    (users / "local" / "me.yaml").write_text('login: "ME"\nschema_prefix: "DBT_MINE"\nroles: []\n')
    monkeypatch.setattr(script, "TF_DIR", tmp_path)
    assert script.personal_prefix("JANE.DOE@example.com") == "DBT_JANE"
    assert script.personal_prefix("john.smith@example.com") == "DBT_JOHN_SMITH"
    assert script.personal_prefix("me") == "DBT_MINE"


def test_init_sql_provisions_through_the_system_roles_and_leaves_the_account_alone() -> None:
    script = load_script()
    sql = script.INIT_SQL.read_text(encoding="utf-8")
    for role in ("SYSADMIN", "SECURITYADMIN", "USERADMIN"):
        assert f"GRANT ROLE {role:<13} TO USER TERRAFORM_USER;" in sql
    assert "DROP ROLE IF EXISTS RL_PLATFORM_PROVISIONING;" in sql
    assert "DROP DATABASE IF EXISTS DB_PLATFORM_PROVISIONING;" in sql
    assert "DROP RESOURCE MONITOR IF EXISTS RM_PLATFORM_PROVISIONING;" in sql
    assert "CREATE DATABASE IF NOT EXISTS" not in sql
    assert "RESOURCE_MONITOR" not in sql
    assert "ALTER ACCOUNT" not in sql


def test_init_sql_drops_the_trial_defaults_once_terraform_has_its_own_warehouse() -> None:
    script = load_script()
    sql = script.INIT_SQL.read_text(encoding="utf-8")
    for statement in (
        "DROP WAREHOUSE IF EXISTS COMPUTE_WH;",
        "DROP WAREHOUSE IF EXISTS SNOWFLAKE_LEARNING_WH;",
        "DROP DATABASE IF EXISTS SNOWFLAKE_LEARNING_DB;",
        "DROP DATABASE IF EXISTS SNOWFLAKE_SAMPLE_DATA;",
        "DROP ROLE IF EXISTS SNOWFLAKE_LEARNING_ROLE;",
    ):
        assert statement in sql
    for warehouse in ("WH_PLATFORM_PROVISIONING", "WH_PLATFORM"):
        assert sql.index(f"CREATE WAREHOUSE IF NOT EXISTS {warehouse}\n") < sql.index(
            "DROP WAREHOUSE IF EXISTS COMPUTE_WH"
        )
    disable = sql.index("SELECT SYSTEM$DISABLE_SNOWFLAKE_LEARNING_ENVIRONMENT();")
    assert disable < sql.index("DROP WAREHOUSE IF EXISTS SNOWFLAKE_LEARNING_WH")


def test_ensure_default_warehouse_replaces_a_dropped_or_missing_default_only() -> None:
    script = load_script()
    columns = ["property", "value", "default", "description"]
    desc = f"DESC USER {script.quote_ident('ADMIN')}"
    alter = f"ALTER USER {script.quote_ident('ADMIN')} SET DEFAULT_WAREHOUSE = {script.quote_ident('WH_PLATFORM')}"
    for current, replaced in [("COMPUTE_WH", True), ("null", True), ("WH_OWN", False)]:
        conn = FakeConnection({desc: (columns, [["DEFAULT_WAREHOUSE", current, "null", ""]])})
        script.ensure_default_warehouse(conn, "ADMIN", "WH_PLATFORM")
        assert conn.executed == ([desc, alter] if replaced else [desc]), current


def test_account_settings_set_utc_and_list_their_parameters() -> None:
    script = load_script()
    sql = script.ACCOUNT_SQL.read_text(encoding="utf-8")
    assert "USE ROLE ACCOUNTADMIN;" in sql
    assert "TIMEZONE               = 'UTC'" in sql
    parameters = script.account_parameters(sql)
    assert parameters[:2] == ["TIMEZONE = 'UTC'", "TIMESTAMP_TYPE_MAPPING = 'TIMESTAMP_NTZ'"]
    assert "PERIODIC_DATA_REKEYING = TRUE" in parameters


@pytest.mark.parametrize(
    ("mode", "yes", "answer", "applied"),
    [
        ("ask", False, "", True),
        ("ask", False, "n", False),
        ("ask", True, "n", True),
        ("apply", False, "n", True),
        ("skip", True, "", False),
    ],
)
def test_account_settings_are_asked_applied_or_skipped(
    monkeypatch: pytest.MonkeyPatch, mode: str, yes: bool, answer: str, applied: bool
) -> None:
    script = load_script()
    monkeypatch.setattr("builtins.input", lambda prompt: answer)
    conn = FakeConnection()
    script.apply_account_settings(conn, mode, yes)
    assert bool(conn.scripts) is applied


def test_reconcile_existing_does_nothing_on_a_fresh_account(monkeypatch: pytest.MonkeyPatch) -> None:
    script = load_script()
    monkeypatch.setattr(script, "planned_changes", lambda env, instance: [])
    monkeypatch.setattr(script, "planned_creates", lambda changes: [PLANNED[1]])
    stacks = [script.Instance("snowflake-project", "example-prd")]
    assert script.reconcile_existing(FakeConnection(), {}, stacks, "ask", "ADMIN", yes=False) == {}


def grant_change(
    address: str, actions: list[str], privileges: list[str], all_privileges: bool = False
) -> dict[str, Any]:
    before = {"privileges": privileges, "all_privileges": all_privileges}
    return {
        "address": address,
        "type": "snowflake_grant_privileges_to_account_role",
        "change": {"actions": actions, "before": before},
    }


def test_forget_vanished_grants_removes_only_revokes_of_grants_the_account_lost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = load_script()
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(script, "atmos_output", lambda env, *args: calls.append(args) or "")
    instance = script.Instance("snowflake-project", "example-dev")
    changes = [
        grant_change("gone", ["delete"], []),
        grant_change("replaced", ["delete", "create"], []),
        grant_change("revoked", ["delete"], ["USAGE"]),
        grant_change("granted_again", ["update"], []),
        grant_change("all", ["delete"], [], all_privileges=True),
        {"address": "schema", "type": "snowflake_schema", "change": {"actions": ["delete"], "before": {}}},
    ]
    script.forget_vanished_grants({}, instance, changes)
    assert calls == [
        ("terraform", "state", "rm", "snowflake-project", "-s", "example-dev", "--skip-init", "--", "gone", "replaced")
    ]
    calls.clear()
    script.forget_vanished_grants({}, instance, [grant_change(f"g{i}", ["delete"], []) for i in range(150)])
    assert [len(args) - 8 for args in calls] == [100, 50]


def test_usable_prefix_follows_the_user_schema_and_refuses_placeholders() -> None:
    script = load_script()
    schema = json.loads(
        SCRIPT.parents[1].joinpath("terraform", "config", "_validation", "schemas", "user.schema.json").read_text()
    )
    assert script.SCHEMA_PREFIX.pattern == schema["properties"]["schema_prefix"]["pattern"]
    assert script.usable_prefix(" dbt_jane ") == "DBT_JANE"
    for value in ("", "DBT", "dbt", "DBT_<USERNAME>", "1_DBT", "DBT-JANE"):
        assert script.usable_prefix(value) is None


def grants(user: str, *roles: str) -> dict[str, tuple[list[str], list[list[str]]]]:
    """A SHOW GRANTS TO USER answer granting `roles`."""
    rows = [["USAGE", "ROLE", role] for role in roles]
    return {f'SHOW GRANTS TO USER "{user}"': (["privilege", "granted_on", "name"], rows)}


@pytest.mark.parametrize(
    ("role", "schema", "expected"),
    [
        ("RL_EXAMPLE_DEV__ENG", "DBT_<USERNAME>", "DBT_JANE"),
        ("RL_EXAMPLE_DEV__ENG", "DBT", "DBT_JANE"),
        ("RL_EXAMPLE_DEV__ENG", "dbt_custom", "DBT_CUSTOM"),
        ("RL_EXAMPLE_PRD__ANL", "DBT_JANE", ""),
    ],
)
def test_discover_context_keeps_a_usable_prefix_in_dev_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, role: str, schema: str, expected: str
) -> None:
    script = load_script()
    monkeypatch.setattr(script, "TF_DIR", tmp_path)
    settings = SnowflakeSettings(user="JANE", schema=schema)
    found = script.discover_context(FakeConnection(grants("JANE", role)), settings, None, interactive=False)
    assert (found.role, found.schema) == (role, expected)


def test_discover_context_without_a_project_role_leaves_the_context_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    script = load_script()
    monkeypatch.setattr(script, "TF_DIR", tmp_path)
    settings = SnowflakeSettings(user="JANE", role="ACCOUNTADMIN", warehouse="COMPUTE_WH", database="SNOWFLAKE")
    found = script.discover_context(FakeConnection(grants("JANE")), settings, None, interactive=False)
    assert (found.role, found.warehouse, found.database, found.schema) == ("", "", "", "DBT_JANE")
    assert "docs/operate/onboarding.md" in capsys.readouterr().out


def test_discover_context_keeps_a_project_role_from_env_that_is_not_granted_directly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = load_script()
    monkeypatch.setattr(script, "TF_DIR", tmp_path)
    settings = SnowflakeSettings(
        user="JANE", role="RL_EXAMPLE_DEV__ENG", warehouse="WH_EXAMPLE_DEV", database="DB_EXAMPLE_DEV"
    )
    found = script.discover_context(FakeConnection(grants("JANE")), settings, None, interactive=False)
    assert (found.role, found.warehouse, found.database) == ("RL_EXAMPLE_DEV__ENG", "WH_EXAMPLE_DEV", "DB_EXAMPLE_DEV")


def test_setup_keeps_the_project_context_in_env_when_no_project_role_is_granted_directly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A role granted through a hierarchy is invisible to SHOW GRANTS TO USER; setup must not blank it."""
    script = load_script()
    env_file = tmp_path / ".env"
    env_file.write_text(
        "SNOWFLAKE_ROLE=RL_EXAMPLE_DEV__ENG\n"
        "SNOWFLAKE_WAREHOUSE=WH_EXAMPLE_DEV\n"
        "SNOWFLAKE_DATABASE=DB_EXAMPLE_DEV\n"
        "SNOWFLAKE_SCHEMA=DBT_JANE\n"
    )
    monkeypatch.setattr(script, "ENV_FILE", env_file)
    monkeypatch.setattr(script, "ENV_EXAMPLE", env_file)
    monkeypatch.setattr(script, "TF_DIR", tmp_path)
    conn = FakeConnection({script.CONTEXT_SQL: (["user", "role"], [["JANE", "ACCOUNTADMIN"]]), **grants("JANE")})
    monkeypatch.setattr(script, "interactive_connect", lambda account, user, auth: conn)
    monkeypatch.setattr(script, "register_key_pair", lambda *args: (tmp_path / "jane.p8", ""))
    monkeypatch.setattr(SnowflakeSettings, "connect", lambda self, **overrides: conn)
    monkeypatch.setattr(script, "verify", lambda settings: True)
    args = argparse.Namespace(
        account="MYORG-MYACCOUNT",
        user="JANE",
        auth="password",
        key_name="jane",
        passphrase=False,
        slot=1,
        role=None,
        yes=True,
    )
    assert script.cmd_setup(args) == 0
    written = dotenv_values(env_file)
    assert [written[f"SNOWFLAKE_{k}"] for k in ("ROLE", "WAREHOUSE", "DATABASE", "SCHEMA")] == [
        "RL_EXAMPLE_DEV__ENG",
        "WH_EXAMPLE_DEV",
        "DB_EXAMPLE_DEV",
        "DBT_JANE",
    ]


def test_choose_role_takes_an_asked_for_role_when_show_grants_lists_none() -> None:
    script = load_script()
    assert script.choose_role([], wanted="rl_example_dev__eng", interactive=False) == "RL_EXAMPLE_DEV__ENG"
    with pytest.raises(SystemExit):
        script.choose_role([], wanted="ACCOUNTADMIN", interactive=False)


@pytest.mark.parametrize(
    ("role", "expected"),
    [("RL_EXAMPLE_DEV__ENG", "DBT_JANE"), ("RL_EXAMPLE_DEV__ANL", ""), ("RL_EXAMPLE_DEV__RPT", "")],
)
def test_discover_context_gives_a_prefix_only_to_dev_roles_with_personal_schemas(
    role: str, expected: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """The `personal:` block in terraform/config/roles decides, not the environment alone."""
    script = load_script()
    settings = SnowflakeSettings(user="JANE")
    found = script.discover_context(FakeConnection(grants("JANE", role)), settings, None, interactive=False)
    assert (found.role, found.schema) == (role, expected)
    assert ("shared _<LAYER> schemas" in capsys.readouterr().out) is (expected == "")


def test_prompt_context_takes_the_environment_of_a_typed_role(monkeypatch: pytest.MonkeyPatch) -> None:
    script = load_script()
    dev = SnowflakeSettings(
        user="JANE",
        role="RL_EXAMPLE_DEV__ENG",
        warehouse="WH_EXAMPLE_DEV",
        database="DB_EXAMPLE_DEV",
        schema="DBT_JANE",
    )
    replies = iter(["rl_example_prd__anl", "", ""])
    monkeypatch.setattr("builtins.input", lambda prompt: next(replies))
    found = script.prompt_context(dev)
    assert (found.role, found.environment, found.database, found.warehouse, found.schema) == (
        "RL_EXAMPLE_PRD__ANL",
        "prd",
        "DB_EXAMPLE_PRD",
        "WH_EXAMPLE_PRD",
        "",
    )


def test_prompt_context_asks_again_for_an_unusable_prefix_and_not_at_all_outside_dev(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = load_script()
    dev = SnowflakeSettings(
        user="JANE",
        role="RL_EXAMPLE_DEV__ENG",
        warehouse="WH_EXAMPLE_DEV",
        database="DB_EXAMPLE_DEV",
        schema="DBT_JANE",
    )
    replies = iter(["", "", "", "DBT", "dbt_<me>", "dbt_me"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(replies))
    assert script.prompt_context(dev).schema == "DBT_ME"
    prd = dataclasses.replace(dev, role="RL_EXAMPLE_PRD__ANL", environment="prd", schema="")
    replies = iter(["", "", ""])
    assert script.prompt_context(prd) == prd


def test_choose_role_asks_until_it_gets_a_listed_number(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    script = load_script()
    replies = iter(["0", "x", "3", "-1", "2"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(replies))
    roles = ["RL_EXAMPLE_PRD__ANL", "RL_EXAMPLE_DEV__ENG"]
    assert script.choose_role(roles, wanted=None, interactive=True) == "RL_EXAMPLE_PRD__ANL"
    # A role outside dev is marked in the list, so a mistyped number is visible before it is made.
    out = capsys.readouterr().out
    assert "RL_EXAMPLE_DEV__ENG\n" in out
    assert "RL_EXAMPLE_PRD__ANL  (prd: shared schemas, not a laptop)" in out


def test_confirm_environment_asks_before_pointing_env_outside_dev(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    script = load_script()
    dev = SnowflakeSettings(user="JANE", role="RL_EXAMPLE_DEV__ENG", database="DB_EXAMPLE_DEV")
    prd = SnowflakeSettings(user="JANE", role="RL_EXAMPLE_PRD__ANL", database="DB_EXAMPLE_PRD")
    monkeypatch.setattr("builtins.input", lambda prompt: pytest.fail(f"asked: {prompt}"))
    script.confirm_environment(dev, interactive=True)  # dev needs no confirmation
    script.confirm_environment(prd, interactive=False)  # --yes or --role: warn, do not ask
    assert capsys.readouterr().out.count("DB_EXAMPLE_PRD") == 1
    monkeypatch.setattr("builtins.input", lambda prompt: "")  # the default is No
    with pytest.raises(SystemExit):
        script.confirm_environment(prd, interactive=True)
    monkeypatch.setattr("builtins.input", lambda prompt: "y")
    script.confirm_environment(prd, interactive=True)


def test_public_key_fingerprint_is_the_sha256_of_the_der_key(tmp_path: Path) -> None:
    script = load_script()
    _, public_path = script.generate_key_pair("fp", key_dir=tmp_path)
    der = serialization.load_pem_public_key(public_path.read_bytes()).public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    assert (
        script.public_key_fingerprint(public_path)
        == "SHA256:" + base64.b64encode(hashlib.sha256(der).digest()).decode()
    )


def desc_user(user: str, fingerprint: str) -> dict[str, tuple[list[str], list[list[str]]]]:
    """A DESC USER answer with `fingerprint` in the first slot and nothing in the second."""
    rows = [["RSA_PUBLIC_KEY_FP", fingerprint, "null", ""], ["RSA_PUBLIC_KEY_2_FP", "null", "null", ""]]
    return {f'DESC USER "{user}"': (["property", "value", "default", "description"], rows)}


def test_slot_needs_key_skips_the_same_key_and_asks_before_replacing_another(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = load_script()
    _, public_path = script.generate_key_pair("me", key_dir=tmp_path)
    same = FakeConnection(desc_user("JANE", script.public_key_fingerprint(public_path)))
    assert script.slot_needs_key(FakeConnection(), "JANE", "RSA_PUBLIC_KEY", public_path) is True  # unknown user
    assert script.slot_needs_key(same, "JANE", "RSA_PUBLIC_KEY", public_path) is False
    assert script.slot_needs_key(same, "JANE", "RSA_PUBLIC_KEY_2", public_path) is True
    other = FakeConnection(desc_user("JANE", "SHA256:another="))
    monkeypatch.setattr("builtins.input", lambda prompt: "y")
    assert script.slot_needs_key(other, "JANE", "RSA_PUBLIC_KEY", public_path) is True
    monkeypatch.setattr("builtins.input", lambda prompt: "")  # the default is No
    with pytest.raises(SystemExit):
        script.slot_needs_key(other, "JANE", "RSA_PUBLIC_KEY", public_path)


def test_slot_needs_key_replaces_a_key_this_run_generated_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Rotation: the key in the slot is the one being replaced, so no other machine is involved."""
    script = load_script()
    _, public_path = script.generate_key_pair("me", key_dir=tmp_path)
    other = FakeConnection(desc_user("JANE", "SHA256:another="))
    monkeypatch.setattr("builtins.input", lambda prompt: "")  # a bare Enter rotates
    assert script.slot_needs_key(other, "JANE", "RSA_PUBLIC_KEY", public_path, generated=True) is True
    out = capsys.readouterr().out
    assert "holds the key registered before" in out and "another machine" not in out
    monkeypatch.setattr("builtins.input", lambda prompt: "n")
    with pytest.raises(SystemExit):
        script.slot_needs_key(other, "JANE", "RSA_PUBLIC_KEY", public_path, generated=True)


def test_register_key_pair_keeps_the_old_key_when_snowflake_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = load_script()
    monkeypatch.setattr(script, "KEY_DIR", tmp_path)
    private_path, _ = script.generate_key_pair("me", key_dir=tmp_path)
    before = private_path.read_bytes()
    monkeypatch.setattr("builtins.input", lambda prompt: "n")  # do not keep it: make a new pair
    conn = FakeConnection(refuse="ALTER USER")
    assert script.register_key_pair(conn, "JANE", "me", "RSA_PUBLIC_KEY", ask_passphrase=False) is None
    assert private_path.read_bytes() == before
    assert sorted(path.name for path in tmp_path.iterdir()) == ["me.p8", "me.pub"]
    # Without an older key the refused pair stays, for an administrator to register its .pub.
    assert script.register_key_pair(conn, "JANE", "first", "RSA_PUBLIC_KEY", ask_passphrase=False) is None
    assert sorted(path.name for path in tmp_path.iterdir()) == ["first.p8", "first.pub", "me.p8", "me.pub"]


def test_register_key_pair_moves_the_new_pair_in_and_keeps_a_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = load_script()
    monkeypatch.setattr(script, "KEY_DIR", tmp_path)
    private_path, public_path = script.generate_key_pair("me", key_dir=tmp_path)
    before = private_path.read_bytes()
    monkeypatch.setattr("builtins.input", lambda prompt: "n")
    conn = FakeConnection()
    assert script.register_key_pair(conn, "JANE", "me", "RSA_PUBLIC_KEY", ask_passphrase=False) == (private_path, "")
    assert (tmp_path / "me.p8.bak").read_bytes() == before and private_path.read_bytes() != before
    assert sorted(path.name for path in tmp_path.iterdir()) == ["me.p8", "me.p8.bak", "me.pub", "me.pub.bak"]
    assert conn.executed[-1] == f"ALTER USER \"JANE\" SET RSA_PUBLIC_KEY = '{script.public_key_body(public_path)}'"


def test_register_key_pair_keeps_a_registered_key_and_restores_its_public_half(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = load_script()
    monkeypatch.setattr(script, "KEY_DIR", tmp_path)
    private_path, public_path = script.generate_key_pair("me", key_dir=tmp_path)
    body, fingerprint = script.public_key_body(public_path), script.public_key_fingerprint(public_path)
    public_path.unlink()
    monkeypatch.setattr("builtins.input", lambda prompt: "y")  # keep it
    conn = FakeConnection(desc_user("JANE", fingerprint))
    assert script.register_key_pair(conn, "JANE", "me", "RSA_PUBLIC_KEY", ask_passphrase=False) == (private_path, "")
    assert script.public_key_body(public_path) == body
    assert not any(sql.startswith("ALTER USER") for sql in conn.executed)


def test_existing_key_passphrase_asks_until_it_opens_the_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    script = load_script()
    private_path, public_path = script.generate_key_pair("enc", passphrase="right", key_dir=tmp_path)
    public_path.unlink()
    replies = iter(["wrong", "right"])
    monkeypatch.setattr(script.getpass, "getpass", lambda prompt: next(replies))
    assert script.existing_key_passphrase(private_path, public_path) == "right"
    assert public_path.exists()


def test_new_passphrase_asks_again_for_one_env_cannot_hold(monkeypatch: pytest.MonkeyPatch) -> None:
    script = load_script()
    replies = iter(["it's mine", "a b#c $d", "a b#c $d"])
    monkeypatch.setattr(script.getpass, "getpass", lambda prompt: next(replies))
    assert script.new_passphrase("Passphrase") == "a b#c $d"


def test_write_env_reads_back_what_it_wrote(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    script = load_script()
    (tmp_path / ".env.example").write_text("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE=\n")
    monkeypatch.setattr(script, "ENV_FILE", tmp_path / ".env")
    monkeypatch.setattr(script, "ENV_EXAMPLE", tmp_path / ".env.example")
    script.write_env({"SNOWFLAKE_PRIVATE_KEY_PASSPHRASE": "a b#c $d", "SNOWFLAKE_SCHEMA": "DBT_JANE"})
    assert dotenv_values(tmp_path / ".env") == {
        "SNOWFLAKE_PRIVATE_KEY_PASSPHRASE": "a b#c $d",
        "SNOWFLAKE_SCHEMA": "DBT_JANE",
    }
    with pytest.raises(SystemExit):
        script.write_env({"SNOWFLAKE_PRIVATE_KEY_PASSPHRASE": "it's"})


def test_write_env_fills_in_the_commented_tf_var_block_instead_of_repeating_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`just sf bootstrap` writes TF_VAR_*, which .env.example ships commented out."""
    script = load_script()
    env_file = tmp_path / ".env"
    env_file.write_text(script.ENV_EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(script, "ENV_FILE", env_file)
    script.write_env({"TF_VAR_SNOWFLAKE_ORGANIZATION": "MYORG", "TF_VAR_SNOWFLAKE_ACCOUNT": "ACC"})
    text = env_file.read_text(encoding="utf-8")
    assert text.count("TF_VAR_SNOWFLAKE_ORGANIZATION") == 1
    assert "# TF_VAR_SNOWFLAKE_ACCOUNT=" not in text
    assert "# TF_VAR_SNOWFLAKE_USER=TERRAFORM_USER" in text  # keys it does not write stay commented
    assert dotenv_values(env_file)["TF_VAR_SNOWFLAKE_ACCOUNT"] == "ACC"


STATE = {
    "values": {
        "root_module": {
            "resources": [
                {
                    "address": 'snowflake_stage_internal.default["dev_src"]',
                    "mode": "managed",
                    "type": "snowflake_stage_internal",
                    "values": {"database": "DB_EXAMPLE_DEV", "schema": "_SRC", "name": "ST_DEFAULT"},
                },
                {
                    "address": "data.snowflake_x.y",
                    "mode": "data",
                    "type": "snowflake_database",
                    "values": {"name": "X"},
                },
            ],
            "child_modules": [
                {
                    "resources": [
                        {
                            "address": 'module.database["dev"].snowflake_database.this',
                            "mode": "managed",
                            "type": "snowflake_database",
                            "values": {"name": "DB_EXAMPLE_DEV"},
                        },
                        {
                            "address": 'module.database["dev"].snowflake_execute.drop_public_schema',
                            "mode": "managed",
                            "type": "snowflake_execute",
                            "values": {},
                        },
                    ]
                }
            ],
        }
    }
}


def test_managed_objects_reads_every_module_of_the_state(monkeypatch: pytest.MonkeyPatch) -> None:
    script = load_script()
    instance = script.Instance("snowflake-project", "example-dev")
    monkeypatch.setattr(script, "atmos_output", lambda env, *args: json.dumps(STATE))
    assert sorted(script.object_path(r) for r in script.managed_objects({}, instance)) == [
        ("DB_EXAMPLE_DEV",),
        ("DB_EXAMPLE_DEV", "_SRC", "ST_DEFAULT"),
    ]
    monkeypatch.setattr(script, "atmos_output", lambda env, *args: '{"format_version": "1.0"}')
    assert script.managed_objects({}, instance) == []  # no state yet


def test_misowned_objects_lists_what_another_role_owns() -> None:
    script = load_script()
    found = script.misowned_objects(FakeConnection(), PLANNED)
    # DB_EXAMPLE_PRD and the warehouse do not exist; the schema, stage and role have their Terraform owner.
    assert [(script.object_path(r), r["owner"]) for r in found] == [
        (("DB_EXAMPLE_DEV",), "ACCOUNTADMIN"),
        (("ADMIN",), "ACCOUNTADMIN"),
    ]


def test_reclaim_managed_objects_hands_them_back_after_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    script = load_script()
    monkeypatch.setattr(script, "managed_objects", lambda env, instance: PLANNED)
    stacks = [script.Instance("snowflake-project", "example-dev")]
    conn = FakeConnection()
    script.reclaim_managed_objects(conn, {}, stacks, yes=True)
    assert [sql for sql in conn.executed if sql.startswith("GRANT")] == [
        'GRANT OWNERSHIP ON DATABASE "DB_EXAMPLE_DEV" TO ROLE SYSADMIN COPY CURRENT GRANTS',
        'GRANT OWNERSHIP ON USER "ADMIN" TO ROLE USERADMIN COPY CURRENT GRANTS',
    ]
    conn = FakeConnection()
    monkeypatch.setattr("builtins.input", lambda prompt: "n")
    script.reclaim_managed_objects(conn, {}, stacks, yes=False)
    assert not [sql for sql in conn.executed if sql.startswith("GRANT")]


def test_destroy_targets_cover_everything_but_the_databases() -> None:
    script = load_script()
    addresses = [
        'module.database["dev"].snowflake_database.this',
        'module.database["dev"].snowflake_execute.drop_public_schema',
        'module.database_grant["dev_eng"].snowflake_grant_privileges_to_account_role.this[0]',
        'module.schema["dev_src"].snowflake_schema.this',
        'module.schema["dev_stg"].snowflake_schema.this',
        'random_password.user["jane"]',
        'snowflake_stage_internal.default["dev_src"]',
        "data.snowflake_current_account.this",
    ]
    assert script.destroy_targets(addresses) == [
        "module.database_grant",
        "module.schema",
        "random_password.user",
        "snowflake_stage_internal.default",
    ]


def test_terraform_settings_connect_as_the_terraform_user() -> None:
    script = load_script()
    settings = script.terraform_settings({"TF_VAR_SNOWFLAKE_ORGANIZATION": "MYORG", "TF_VAR_SNOWFLAKE_ACCOUNT": "ACC"})
    assert (settings.account, settings.user, settings.role, settings.warehouse) == (
        "MYORG-ACC",
        "TERRAFORM_USER",
        "SYSADMIN",
        "WH_PLATFORM_PROVISIONING",
    )
    assert settings.private_key_path.endswith("/.snowflake/keys/terraform.p8")
    with pytest.raises(SystemExit):
        script.terraform_settings({})


def fake_atmos(monkeypatch: pytest.MonkeyPatch, script: ModuleType, tracked: list[str]) -> list[tuple[str, ...]]:
    """Two stacks: `account` with an empty state, `example-dev` tracking `tracked` (its `show -json` is STATE).

    Returns the Atmos calls that change something (destroy, state rm), in the order they are made.
    """
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(script, "require_terraform", lambda: None)
    monkeypatch.setattr(
        script, "terraform_env", lambda: {"TF_VAR_SNOWFLAKE_ORGANIZATION": "MYORG", "TF_VAR_SNOWFLAKE_ACCOUNT": "ACC"}
    )
    stacks = {
        "account": {"components": {"terraform": {"snowflake-account": {"workspace": "account"}}}},
        "example-dev": {"components": {"terraform": {"snowflake-project": {"workspace": "example-dev"}}}},
    }
    states = {"account": [], "example-dev": tracked}

    def output(env: dict[str, str], *args: str) -> str:
        if args[0] == "describe":
            return json.dumps(stacks)
        stack = args[args.index("-s") + 1]
        if args[1:3] == ("state", "list"):
            return "\n".join(states[stack])
        if args[1] == "show":
            return json.dumps(STATE) if states[stack] else '{"format_version": "1.0"}'
        if args[1] == "init":
            return ""
        calls.append(args)
        return ""

    monkeypatch.setattr(script, "atmos_output", output)
    monkeypatch.setattr(script, "atmos", lambda env, *args: calls.append(args))
    return calls


def test_clean_changes_nothing_unless_the_account_name_is_typed(monkeypatch: pytest.MonkeyPatch) -> None:
    script = load_script()
    calls = fake_atmos(monkeypatch, script, ['module.database["dev"].snowflake_database.this'])
    monkeypatch.setattr("builtins.input", lambda prompt: "MYORG")
    assert script.cmd_clean(None) == 1
    assert calls == []


def test_clean_destroys_the_rest_then_drops_the_databases(monkeypatch: pytest.MonkeyPatch) -> None:
    script = load_script()
    addresses = ['module.database["dev"].snowflake_database.this', 'snowflake_stage_internal.default["dev_src"]']
    calls = fake_atmos(monkeypatch, script, addresses)
    conn = FakeConnection()
    settings = SnowflakeSettings(account="MYORG-ACC")
    monkeypatch.setattr(script, "terraform_settings", lambda env: settings)
    monkeypatch.setattr(SnowflakeSettings, "connect", lambda self: conn)
    monkeypatch.setattr("builtins.input", lambda prompt: "myorg-acc")
    assert script.cmd_clean(None) == 0
    stack = ("snowflake-project", "-s", "example-dev", "--skip-init", "--")
    assert calls == [
        ("terraform", "destroy", *stack, "-auto-approve", "-input=false", "-target=snowflake_stage_internal.default"),
        ("terraform", "state", "rm", *stack, "module.database"),
    ]
    assert conn.executed == ['DROP DATABASE IF EXISTS "DB_EXAMPLE_DEV"']


def test_clean_on_an_empty_state_says_so_and_fails(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Empty states mean this checkout knows nothing, not that the account is clean."""
    script = load_script()
    calls = fake_atmos(monkeypatch, script, [])
    assert script.cmd_clean(None) == 1
    assert calls == []
    out = capsys.readouterr().out
    assert "track no objects" in out and "--existing sync" in out


def test_clean_names_what_stays_in_the_account(capsys: pytest.CaptureFixture[str]) -> None:
    """The init.sql objects and the account_settings.sql parameters survive `just tf clean`."""
    script = load_script()
    script.print_leftovers()
    out = capsys.readouterr().out
    assert "DROP USER TERRAFORM_USER;" in out
    assert "DROP WAREHOUSE WH_PLATFORM_PROVISIONING;" in out
    assert "TERRAFORM_USER holds SYSADMIN, SECURITYADMIN, USERADMIN and a registered RSA key" in out
    assert "ALTER ACCOUNT UNSET TIMEZONE, TIMESTAMP_TYPE_MAPPING," in out


def test_keygen_keeps_the_pair_force_replaces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    script = load_script()
    monkeypatch.setattr(script, "KEY_DIR", tmp_path)
    private_path, _ = script.generate_key_pair("terraform", key_dir=tmp_path)
    before = private_path.read_bytes()
    assert script.cmd_keygen(argparse.Namespace(name="terraform", passphrase=False, force=False)) == 1
    assert private_path.read_bytes() == before
    assert script.cmd_keygen(argparse.Namespace(name="terraform", passphrase=False, force=True)) == 0
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "terraform.p8",
        "terraform.p8.bak",
        "terraform.pub",
        "terraform.pub.bak",
    ]
    assert (tmp_path / "terraform.p8.bak").read_bytes() == before
    assert private_path.read_bytes() != before
    assert "Snowflake still holds its public key" in capsys.readouterr().out


def test_wizard_asks_again_until_the_answer_is_one_to_four(monkeypatch: pytest.MonkeyPatch) -> None:
    script = load_script()
    calls: list[list[str]] = []

    def fake_main(argv: list[str]) -> int:
        calls.append(argv)
        return 0

    monkeypatch.setattr(script, "main", fake_main)
    replies = iter(["fresh", "5", "", "2"])  # the empty answer takes the default, 1
    monkeypatch.setattr("builtins.input", lambda prompt: next(replies))
    assert script.cmd_wizard(None) == 0
    assert calls == [["bootstrap"]]
    replies = iter(["2"])
    assert script.cmd_wizard(None) == 0
    assert calls[-1] == ["setup"]
    replies = iter(["4"])
    assert script.cmd_wizard(None) == 0
    assert calls[-1] == ["local"]


def test_local_writes_only_the_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`just setup` option 4: ENVIRONMENT=local, the Snowflake block untouched, no key pair."""
    script = load_script()
    env_file = tmp_path / ".env"
    env_file.write_text(script.ENV_EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(script, "ENV_FILE", env_file)
    before = dotenv_values(env_file)
    assert script.cmd_local(None) == 0
    after = dotenv_values(env_file)
    assert after["ENVIRONMENT"] == "local"
    assert {k: v for k, v in after.items() if k != "ENVIRONMENT"} == {
        k: v for k, v in before.items() if k != "ENVIRONMENT"
    }
