import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

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


def test_schema_prefix_replaces_the_placeholder_env_example_ships() -> None:
    script = load_script()
    # .env.example ships DBT_USERNAME; it must never become someone's real schema prefix.
    assert script.schema_prefix("DBT_USERNAME", "username@example.com") == "DBT_USERNAME"
    assert script.schema_prefix("DBT_USERNAME", "j.doe@example.com") == "DBT_J_DOE"
    assert script.schema_prefix("dbt", "j.doe@example.com") == "DBT_J_DOE"
    assert script.schema_prefix("", "j.doe@example.com") == "DBT_J_DOE"
    assert script.schema_prefix("DBT_TEAM_SHARED", "j.doe@example.com") == "DBT_TEAM_SHARED"


def test_provisioning_sql_fills_in_the_terraform_key() -> None:
    script = load_script()
    sql = script.provisioning_sql("MIIBkey", "RSA_PUBLIC_KEY")
    assert "  RSA_PUBLIC_KEY = 'MIIBkey'" in sql
    assert "--RSA_PUBLIC_KEY" not in sql and "INSERT_YOUR" not in sql


def test_ensure_user_config_writes_engineer_grants_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    script = load_script()
    (tmp_path / "config" / "users").mkdir(parents=True)
    (tmp_path / "config" / "projects").mkdir()
    (tmp_path / "config" / "projects" / "example.yaml").write_text("code: example\n")
    monkeypatch.setattr(script, "TF_DIR", tmp_path)
    script.ensure_user_config("USERNAME", {"USERNAME"})
    written = tmp_path / "config" / "users" / "username.yaml"
    assert 'login: "USERNAME"' in written.read_text()
    assert "  - project: example\n    role: engineer\n    environments:\n      - development\n" in written.read_text()
    script.ensure_user_config("username", {"USERNAME"})
    assert len(list((tmp_path / "config" / "users").glob("*.yaml"))) == 1


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
    """Answers the SHOW statements existing_objects runs and records every other statement."""

    SHOW = {
        "SHOW DATABASES": (["name"], [["DB_EXAMPLE_DEV"], ["SNOWFLAKE"]]),
        "SHOW SCHEMAS IN ACCOUNT": (["database_name", "name"], [["DB_EXAMPLE_DEV", "_SRC"]]),
        "SHOW STAGES IN ACCOUNT": (
            ["database_name", "schema_name", "name"],
            [["DB_EXAMPLE_DEV", "_SRC", "ST_DEFAULT"]],
        ),
        "SHOW WAREHOUSES": (["name"], []),
        "SHOW ROLES": (["name"], [["RL_EXAMPLE_DEV__ENG"]]),
        "SHOW USERS": (["name"], [["ADMIN"]]),
    }

    def __init__(self) -> None:
        self.executed: list[str] = []

    def cursor(self) -> "FakeConnection":
        return self

    def execute(self, sql: str) -> "FakeConnection":
        self.executed.append(sql)
        columns, self.rows = self.SHOW.get(sql, ([], []))
        self.description = [(c,) for c in columns]
        return self

    def fetchall(self) -> list[list[str]]:
        return self.rows


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
    monkeypatch.setattr(script, "ADOPT_FILE", tmp_path / "adopt_imports.tf")
    script.write_imports([PLANNED[0], PLANNED[3]])
    text = (tmp_path / "adopt_imports.tf").read_text()
    assert 'import {\n  to = module.database["dev"].snowflake_database.this\n  id = "\\"DB_EXAMPLE_DEV\\""\n}' in text
    assert 'id = "\\"DB_EXAMPLE_DEV\\".\\"_SRC\\".\\"ST_DEFAULT\\""' in text


def test_drop_objects_goes_innermost_first_and_spares_the_current_user() -> None:
    script = load_script()
    conn = FakeConnection()
    script.drop_objects(conn, list(reversed(PLANNED)), current_user="admin")
    assert conn.executed == [
        'DROP STAGE IF EXISTS "DB_EXAMPLE_DEV"."_SRC"."ST_DEFAULT"',
        'DROP SCHEMA IF EXISTS "DB_EXAMPLE_DEV"."_SRC"',
        'DROP DATABASE IF EXISTS "DB_EXAMPLE_PRD"',
        'DROP DATABASE IF EXISTS "DB_EXAMPLE_DEV"',
        'DROP WAREHOUSE IF EXISTS "WH_EXAMPLE_DEV"',
        'DROP ROLE IF EXISTS "RL_EXAMPLE_DEV__ENG"',
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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, answers: list[str], proceeds: bool, imports: bool, drops: bool
) -> None:
    script = load_script()
    monkeypatch.setattr(script, "ADOPT_FILE", tmp_path / "adopt_imports.tf")
    monkeypatch.setattr(script, "planned_creates", lambda env: PLANNED)
    replies = iter(answers)
    monkeypatch.setattr("builtins.input", lambda prompt: next(replies))
    conn = FakeConnection()
    assert script.reconcile_existing(conn, {}, "ask", "ADMIN", yes=False) is proceeds
    assert (tmp_path / "adopt_imports.tf").exists() is imports
    assert any(sql.startswith("DROP") for sql in conn.executed) is drops
    assert any(sql.startswith("GRANT OWNERSHIP") for sql in conn.executed) is imports


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
    monkeypatch.setattr(script, "TF_DIR", tmp_path)
    assert script.personal_prefix("JANE.DOE@example.com") == "DBT_JANE"
    assert script.personal_prefix("john.smith@example.com") == "DBT_JOHN_SMITH"


def test_init_sql_provisions_through_the_system_roles_in_utc() -> None:
    sql = SCRIPT.parents[1].joinpath("terraform", "modules", "snowflake", "init.sql").read_text()
    for role in ("SYSADMIN", "SECURITYADMIN", "USERADMIN"):
        assert f"GRANT ROLE {role:<13} TO USER TERRAFORM_USER;" in sql
    assert "DROP ROLE IF EXISTS RL_PLATFORM_PROVISIONING;" in sql
    assert "TIMEZONE               = 'UTC'" in sql


def test_reconcile_existing_does_nothing_on_a_fresh_account(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    script = load_script()
    monkeypatch.setattr(script, "ADOPT_FILE", tmp_path / "adopt_imports.tf")
    monkeypatch.setattr(script, "planned_creates", lambda env: [PLANNED[1]])
    assert script.reconcile_existing(FakeConnection(), {}, "ask", "ADMIN", yes=False) is True
    assert not (tmp_path / "adopt_imports.tf").exists()
