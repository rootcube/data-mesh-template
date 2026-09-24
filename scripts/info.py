"""Tool versions and local setup status (`just info`)."""

from __future__ import annotations

import importlib.metadata
import shutil
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values

from orchestrator.resources.snowflake import SnowflakeSettings

ROOT = Path(__file__).resolve().parents[1]


def tool(command: str, *args: str) -> str:
    path = shutil.which(command)
    if not path:
        return "not found"
    result = subprocess.run([path, *args], capture_output=True, text=True, check=False)
    output = (result.stdout or result.stderr).strip()
    return output.splitlines()[0] if output else "unknown"


def package(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not installed"


def main() -> int:
    print("System tools:")
    print(f"  python      {sys.version.split()[0]} ({sys.executable})")
    print(f"  uv          {tool('uv', '--version')}")
    print(f"  just        {tool('just', '--version')}")
    print(f"  terraform   {tool('terraform', '--version')}  (administrators)")
    print(f"  direnv      {tool('direnv', '--version')}  (optional)")
    print()
    print("Python packages (.venv):")
    for name in ("dagster", "dagster-dbt", "dagster-dlt", "dlt", "dbt-core", "dbt-snowflake", "ruff", "ty", "sqlfluff"):
        print(f"  {name:<14} {package(name)}")
    print()
    print("Local setup:")
    env_file = ROOT / ".env"
    if env_file.exists():
        settings = SnowflakeSettings.from_env({k: (v or "") for k, v in dotenv_values(env_file).items()})
        missing = settings.missing()
        print(f"  .env        present{' (missing: ' + ', '.join(missing) + ')' if missing else ''}")
        if settings.private_key_path:
            state = "present" if settings.key_path().exists() else "MISSING"
            print(f"  private key {settings.key_path()} ({state})")
        if not missing:
            print(
                f"  context     {settings.database} as {settings.role} on {settings.warehouse} ({settings.environment})"
            )
        print(f"  next        {'just sf setup' if missing else 'just sf check, then just start'}")
    else:
        print("  .env        missing (run `just init`, then `just sf setup`)")
    for name in (".dagster", ".dlt/data", "dbt/dbt_example/packages"):
        print(f"  {name:<11} {'present' if (ROOT / name).exists() else 'missing'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
