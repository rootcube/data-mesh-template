"""Test-wide setup.

dlt finds `.dlt/config.toml` through `DLT_PROJECT_DIR`, falling back to the working directory, and
caches its config providers on first use. Pinning the variable here, before any test module imports
dlt, keeps the suite passing from any working directory (`just test` and `.envrc` already export it,
a bare `uv run pytest` from `tests/` does not).
"""

import os
from pathlib import Path

os.environ.setdefault("DLT_PROJECT_DIR", str(Path(__file__).resolve().parents[1]))
