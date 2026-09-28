"""Tool versions and local setup status (`just info`)."""

from __future__ import annotations

import importlib.metadata
import re
import shutil
import subprocess
import sys
from pathlib import Path

# scripts/ is on sys.path because this runs as `python scripts/info.py`.
from dbt_all import projects as dbt_projects
from dotenv import dotenv_values

from orchestrator.resources.snowflake import SnowflakeSettings

ROOT = Path(__file__).resolve().parents[1]
# A key .env.example only shows commented out, such as the TF_VAR block: optional, not drift.
COMMENTED_KEY = re.compile(r"^#\s*([A-Za-z_][A-Za-z0-9_]*)=")


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


def print_env_drift(env_file: Path, example: Path, width: int) -> None:
    """One line per key .env.example sets that .env misses, and per key .env has that it does not know."""
    documented = set(dotenv_values(example))
    optional = {
        match[1] for line in example.read_text(encoding="utf-8").splitlines() if (match := COMMENTED_KEY.match(line))
    }
    present = set(dotenv_values(env_file))
    for key in sorted(documented - present):
        print(f"  {'.env drift':<{width}} {key} is in .env.example, not in .env (copy the line over)")
    for key in sorted(present - documented - optional):
        print(f"  {'.env drift':<{width}} {key} is in .env, not in .env.example (removed upstream?)")


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
    # One line per dbt project `just dbt-all deps` installs into, so a rename or a second project shows up here.
    checks = [(".dagster", ROOT / ".dagster"), (".dlt/data", ROOT / ".dlt" / "data")]
    checks += [(f"{project.name} packages", project / "packages") for project in dbt_projects()]
    labels = [".env", ".env drift", "private key", "context", "next", *(label for label, _ in checks)]
    width = max(len(label) for label in labels)
    env_file = ROOT / ".env"
    if env_file.exists():
        settings = SnowflakeSettings.from_env({k: (v or "") for k, v in dotenv_values(env_file).items()})
        missing = settings.missing()
        print(f"  {'.env':<{width}} present{' (missing: ' + ', '.join(missing) + ')' if missing else ''}")
        if settings.private_key_path:
            state = "present" if settings.key_path().exists() else "MISSING"
            print(f"  {'private key':<{width}} {settings.key_path()} ({state})")
        if not missing:
            print(
                f"  {'context':<{width}} {settings.database} as {settings.role} "
                f"on {settings.warehouse} ({settings.environment})"
            )
        # Credentials and key in place but no project context: `just sf setup` would only repeat itself.
        if not missing:
            hint = "just sf check, then just start"
        elif settings.missing(SnowflakeSettings.CREDENTIALS) or not settings.key_path().exists():
            hint = "just sf setup"
        else:
            hint = "just sf context"
        print(f"  {'next':<{width}} {hint}")
        print_env_drift(env_file, ROOT / ".env.example", width)
    else:
        print(f"  {'.env':<{width}} missing (run `just init`, then `just sf setup`)")
    for label, path in checks:
        print(f"  {label:<{width}} {'present' if path.exists() else 'missing'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
