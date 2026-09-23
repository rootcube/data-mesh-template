from pathlib import Path

from orchestrator.utils.dotenv import update_env_file


def test_update_replaces_in_place_and_appends_new_keys(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("# comment\nSNOWFLAKE_ACCOUNT=\nSNOWFLAKE_USER=old\nOTHER=keep\n")
    update_env_file(env, {"SNOWFLAKE_USER": "new", "SNOWFLAKE_ROLE": "RL_X"})
    assert env.read_text() == "# comment\nSNOWFLAKE_ACCOUNT=\nSNOWFLAKE_USER=new\nOTHER=keep\n\nSNOWFLAKE_ROLE=RL_X\n"


def test_update_creates_missing_file(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    update_env_file(env, {"A": "1"})
    assert env.read_text() == "A=1\n"
