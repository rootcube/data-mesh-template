from pathlib import Path

from dotenv import dotenv_values

from orchestrator.utils.dotenv import update_env_file


def test_update_replaces_in_place_and_appends_new_keys(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("# comment\nSNOWFLAKE_ACCOUNT=\nSNOWFLAKE_USER=old\nOTHER=keep\n")
    update_env_file(env, {"SNOWFLAKE_USER": "new", "SNOWFLAKE_ROLE": "RL_X"})
    assert env.read_text() == "# comment\nSNOWFLAKE_ACCOUNT=\nSNOWFLAKE_USER=new\nOTHER=keep\n\nSNOWFLAKE_ROLE=RL_X\n"


def test_update_single_quotes_values_with_backslashes(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    update_env_file(env, {"KEY_PATH": r"C:\Users\me\key.p8", "PLAIN": "C:/Users/me/key.p8"})
    assert env.read_text() == "KEY_PATH='C:\\Users\\me\\key.p8'\nPLAIN=C:/Users/me/key.p8\n"
    assert dotenv_values(env) == {"KEY_PATH": r"C:\Users\me\key.p8", "PLAIN": "C:/Users/me/key.p8"}


def test_update_creates_missing_file(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    update_env_file(env, {"A": "1"})
    assert env.read_text() == "A=1\n"
