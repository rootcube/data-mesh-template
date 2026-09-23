import importlib.util
import sys
from pathlib import Path
from types import ModuleType

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
