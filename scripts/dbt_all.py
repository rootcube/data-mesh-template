"""Run one dbt command in every dbt project under dbt/ (`just dbt-all deps`, `just dbt-all parse`).

Packages such as dbt_common are skipped: they are built through the projects that install them.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DBT_DIR = ROOT / "dbt"
PACKAGES = {"dbt_common"}


def projects() -> list[Path]:
    return sorted(p.parent for p in DBT_DIR.glob("*/dbt_project.yml") if p.parent.name not in PACKAGES)


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: python scripts/dbt_all.py <dbt args>, e.g. deps | parse --target dummy")
        return 2
    dbt = shutil.which("dbt")
    if not dbt:
        print("dbt not found on PATH; run through `uv run` or `just`.")
        return 1
    env = {**os.environ, "DBT_PROFILES_DIR": str(DBT_DIR)}
    failed: list[str] = []
    for project in projects():
        print(f"== {project.name}: dbt {' '.join(argv)}")
        if subprocess.run([dbt, *argv], cwd=project, env=env, check=False).returncode != 0:
            failed.append(project.name)
    if failed:
        print(f"failed in: {', '.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
