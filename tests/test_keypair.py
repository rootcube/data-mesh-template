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
