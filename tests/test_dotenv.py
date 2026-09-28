import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from dotenv import dotenv_values

from orchestrator.utils.dotenv import update_env_file, writable


def read_with_python_dotenv(env_file: Path) -> str:
    """KEY as python-dotenv reads it (scripts/snowflake.py, dlt, Dagster)."""
    return dotenv_values(env_file)["KEY"] or ""


def read_with_just(env_file: Path) -> str:
    """KEY as `just` reads it from .env, the other reader update_env_file promises to satisfy."""
    (env_file.parent / "justfile").write_text("set dotenv-load := true\n\nvalue := env_var('KEY')\n")
    # --evaluate prints the value without running a recipe, so no shell is involved on any OS.
    command = ["just", "--evaluate", "value"]
    result = subprocess.run(command, cwd=env_file.parent, capture_output=True, text=True, encoding="utf-8", check=True)
    return result.stdout.rstrip("\n")


# Both readers of .env, since a value has to come back unchanged from either (utils/dotenv.py).
READERS = [
    read_with_python_dotenv,
    pytest.param(read_with_just, marks=pytest.mark.skipif(shutil.which("just") is None, reason="just not on PATH")),
]


def test_update_replaces_in_place_and_appends_new_keys(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("# comment\nSNOWFLAKE_ACCOUNT=\nSNOWFLAKE_USER=old\nOTHER=keep\n")
    update_env_file(env, {"SNOWFLAKE_USER": "new", "SNOWFLAKE_ROLE": "RL_X"})
    assert env.read_text() == "# comment\nSNOWFLAKE_ACCOUNT=\nSNOWFLAKE_USER=new\nOTHER=keep\n\nSNOWFLAKE_ROLE=RL_X\n"


def test_update_replaces_every_line_of_a_key(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("KEY=first\n# KEY=comment\nOTHER=keep\nKEY=second\n")
    update_env_file(env, {"KEY": "new"})
    assert env.read_text() == "KEY=new\n# KEY=comment\nOTHER=keep\nKEY=new\n"
    assert dotenv_values(env)["KEY"] == "new"


@pytest.mark.parametrize(
    ("value", "written"),
    [
        ("", ""),
        ("C:/Users/me/key.p8", "C:/Users/me/key.p8"),
        ("a=b:c@d+e,f_g-h", "a=b:c@d+e,f_g-h"),
        ("pass word #1", "'pass word #1'"),
        ("p$ss $(x) $HOME", "'p$ss $(x) $HOME'"),
        ('say "hi"', "'say \"hi\"'"),
        (r"C:\Users\me\key.p8", r"'C:\Users\me\key.p8'"),
        ("café", "'café'"),
    ],
)
@pytest.mark.parametrize("reader", READERS)
def test_update_writes_safe_values_bare_and_quotes_the_rest(
    tmp_path: Path, value: str, written: str, reader: Callable[[Path], str]
) -> None:
    env = tmp_path / ".env"
    update_env_file(env, {"KEY": value})
    assert env.read_text(encoding="utf-8") == f"KEY={written}\n"
    assert reader(env) == value


@pytest.mark.parametrize("value", ["it's", "a\nb", "a\rb", r"a\\b", r"a\'b", "trailing\\", "${HOME}"])
def test_update_refuses_values_that_would_not_read_back(tmp_path: Path, value: str) -> None:
    env = tmp_path / ".env"
    env.write_text("KEY=old\n")
    assert writable(value) is False
    with pytest.raises(ValueError, match="KEY"):
        update_env_file(env, {"KEY": value})
    assert env.read_text() == "KEY=old\n"


def test_update_creates_missing_file(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    update_env_file(env, {"A": "1"})
    assert env.read_text() == "A=1\n"
