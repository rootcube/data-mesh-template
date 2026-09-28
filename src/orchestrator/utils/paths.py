"""The repository root, shared by the code locations that hand it to Dagster.

`ComponentTree.from_module(project_root=...)` wants the checkout root, and every code location
wants the same one, so the parent count lives here instead of in each of them.
"""

from pathlib import Path

# paths.py -> utils -> orchestrator -> src -> the repository root. This only holds for a checkout,
# which is how the platform runs (`uv sync` installs the package editable); an installed wheel has
# no repository around the package.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
