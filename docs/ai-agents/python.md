---
icon: material/language-python
---

# Python

Agent guide for Python work: where the code lives, the exact validation loop to run after a change, the test pattern to copy, and dependency facts. The rules themselves (formatting, typing, naming, simplicity) live on the canonical pages linked below; this page does not restate them.

## Orientation

Python 3.13 (`.python-version`, `requires-python = ">=3.13,<3.14"`), managed by **uv**. **ruff** lints and formats, **ty** type-checks, **pytest** tests. Nobody activates the venv: every command runs through `uv run`, which `just` does for you.

| Root | Contents | ruff | ty |
|---|---|---|---|
| `src/orchestrator/` | The Dagster package: `locations/`, `resources/`, `utils/` | yes | yes |
| `dlt_pipelines/` | The ingest package loaded by the `dlt` code location | yes | yes |
| `scripts/` | `snowflake.py`, `info.py`, `dbt_all.py` | yes | yes |
| `tests/` | pytest, offline only | yes | yes |
| `dbt/` | Snowpark models run in Snowflake's Python, not in this venv | excluded | excluded |
| `terraform/` | `config/_validation/validate_configs.py`, run through `uv` by the hook and CI | excluded | excluded |
| `docs/` | Markdown with illustrative Python fences | excluded | excluded |

ruff runs on `.` with `dbt`, `terraform`, `site` and `docs` excluded (`[tool.ruff]`); ty checks exactly the four roots (`[tool.ty.src]`). Both packages `src/orchestrator` and `dlt_pipelines` are built by hatchling (`[tool.hatch.build.targets.wheel]`).

## Canonical rules

| Page | What it owns |
|---|---|
| [Python style](../conventions/python-style.md) | ruff config (line length 120, rules `E F I UP B`), type annotations and ty, naming, imports, simplicity rules, patterns to reuse |
| [Testing](../development/testing.md) | Test layout, what stays offline, dbt tests, `just validate` |
| [Adding Python assets](../development/adding-python-assets.md) | Where new Dagster asset code goes and how it gets a Snowflake resource |
| [Command reference](../reference/commands.md) | Every `just` recipe |

The behavior rules in `AGENTS.md` (type hint everything, `X | None` not `Optional[X]`, minimal changes, never bypass pre-commit) apply to every Python change.

## After making changes

Run at least steps 1 to 4 before presenting work. All of them also run in pre-commit and CI, so skipping them only postpones the failure.

### 1. Format and lint

=== "just"

    ```bash
    just fmt    # ruff format . + ruff check --fix . (+ sqlfluff fix)
    just lint   # ruff check . + ruff format --check . (+ sqlfluff lint), what CI runs
    ```

=== "ruff directly"

    ```bash
    uv run ruff format .
    uv run ruff check --fix .
    ```

`just fmt` runs both the formatter and the auto-fixing linter, so one command covers ruff completely.

### 2. Type check

=== "just"

    ```bash
    just typecheck
    ```

=== "ty directly"

    ```bash
    uv run ty check
    ```

Whole-project on purpose: a changed signature can break callers in files you did not touch.

### 3. Validate Dagster definitions

```bash
just validate
```

If you changed anything under `src/orchestrator/` or `dlt_pipelines/`, this catches import errors and broken definitions. What it checks: [Testing](../development/testing.md).

### 4. Run tests

=== "just"

    ```bash
    just test
    ```

=== "pytest directly"

    ```bash
    uv run pytest                          # all tests (addopts: -q)
    uv run pytest tests/test_dotenv.py     # one file
    uv run pytest -k "from_env"            # by name
    ```

### 5. Everything CI runs

```bash
just check         # lint + typecheck + test + dbt parse (dummy) + validate + Terraform YAML
just pre-commit    # every hook on every file
```

## Test patterns

Tests are plain pytest functions in `tests/`, one file per module under test, and they never reach Snowflake or the network. What exists today:

| File | Covers |
|---|---|
| `tests/test_snowflake_settings.py` | `SnowflakeSettings.from_env()`: prefix handling, blank values, `missing()`, `dlt_credentials()`, `schema_for_layer()` in `dev` and elsewhere |
| `tests/test_dotenv.py` | `update_env_file()`: in-place replace, append, file creation (`tmp_path`) |
| `tests/test_keypair.py` | `generate_key_pair()`, `public_key_body()` and `key_is_encrypted()` from `scripts/snowflake.py` |
| `tests/test_dlt_pipelines.py` | `discover()` finds the `knmi` pipeline module |

Two patterns to copy:

**Pass a mapping instead of patching the environment.** `SnowflakeSettings.from_env(env)` accepts any mapping, so tests build a dict. From `tests/test_snowflake_settings.py`:

```python
from orchestrator.resources.snowflake import SnowflakeSettings


def test_from_env_reads_prefixed_variables() -> None:
    env = {
        "SNOWFLAKE_ACCOUNT": "ORG-ACCOUNT",
        "SNOWFLAKE_USER": "someone",
        "SNOWFLAKE_PRIVATE_KEY_PATH": "/keys/k.p8",
        "SNOWFLAKE_ROLE": "RL_EXAMPLE_DEV__ENG",
        "SNOWFLAKE_WAREHOUSE": "WH_EXAMPLE_DEV",
        "SNOWFLAKE_DATABASE": "DB_EXAMPLE_DEV",
        "SNOWFLAKE_SCHEMA": " analytics ",
        "UNRELATED": "ignored",
    }
    settings = SnowflakeSettings.from_env(env)
    assert settings.account == "ORG-ACCOUNT"
    assert settings.schema == "analytics"
    assert settings.missing() == []


def test_layer_schemas_are_personal_in_dev_and_shared_elsewhere() -> None:
    dev = SnowflakeSettings.from_env({"SNOWFLAKE_SCHEMA": "dbt_info", "ENVIRONMENT": "dev"})
    assert dev.schema_for_layer("src") == "DBT_INFO_SRC"
    assert dev.schema_for_layer("_stg") == "DBT_INFO_STG"
    prd = SnowflakeSettings.from_env({"SNOWFLAKE_SCHEMA": "_TMP", "ENVIRONMENT": "PRD"})
    assert prd.environment == "prd"
    assert prd.schema_for_layer("mrt") == "_MRT"
```

**Use `tmp_path` for files.** Anything that writes (`.env`, key files) gets a pytest `tmp_path`, never the repo. From `tests/test_dotenv.py`:

```python
from pathlib import Path

from orchestrator.utils.dotenv import update_env_file


def test_update_creates_missing_file(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    update_env_file(env, {"A": "1"})
    assert env.read_text() == "A=1\n"
```

`scripts/` is not a package; `tests/test_keypair.py` loads `scripts/snowflake.py` by path with `importlib.util.spec_from_file_location`. Copy that helper if you test another script.

!!! tip "Design for testability the way the repo does"
    Functions take their inputs as arguments (a mapping, a `Path`, a `key_dir`) instead of reaching for `os.environ` or fixed paths inside. That is why these tests need no mocking library.

## Dependencies

`pyproject.toml` is authoritative; the versions below are the minimums pinned there.

| Package | Version | Purpose |
|---|---|---|
| `dagster`, `dagster-webserver` | >=1.13 | Orchestration and the UI |
| `dagster-dbt`, `dagster-dlt`, `dagster-snowflake` | >=0.29 | The dbt and dlt components, the Snowflake resource |
| `dlt[snowflake]` | >=1.30 | Ingestion |
| `requests` | >=2.32 | HTTP for sources |
| `dbt-core`, `dbt-snowflake` | >=1.11 | Transformation |
| `snowflake-connector-python` | >=3.12 | Direct connections (`scripts/snowflake.py`) |
| `cryptography` | >=43 | Key-pair generation and loading |
| `python-dotenv` | >=1.1 | Reading `.env` in the scripts |

The `dev` dependency group installs on every plain `uv sync` (`default-groups`): `ruff` >=0.13, `pytest` >=8.3, `pre-commit` >=4.0, `sqlfluff-templater-dbt` >=3.4, `dagster-dg-cli` >=1.13, `ty` >=0.0.1, `pyyaml` >=6.0 and `jsonschema` >=4.20 (for `validate_configs.py`), `dbt-duckdb` >=1.9 (the `dummy` dbt target). The `docs` group (`mkdocs-material` >=9.6) is pulled in by `just docs` with `--group docs`.

```bash
just sync      # uv sync, after pulling dependency changes
just upgrade   # uv lock --upgrade, rewrites uv.lock
```

Never edit `uv.lock` by hand.

## Config reference

| What | Where |
|---|---|
| ruff | `pyproject.toml`: `[tool.ruff]`, `[tool.ruff.lint]` |
| ty | `pyproject.toml`: `[tool.ty.src]`, `[tool.ty.environment]` |
| pytest | `pyproject.toml`: `[tool.pytest.ini_options]` (`testpaths = ["tests"]`, `addopts = "-q"`) |
| Dependency groups | `pyproject.toml`: `[dependency-groups]`, `[tool.uv]` |
| dg | `pyproject.toml`: `[tool.dg]`, `[tool.dg.project]` |
| Pre-commit hooks | `.pre-commit-config.yaml` |

## Related pages

- [Python style](../conventions/python-style.md): the canonical style, typing and pattern rules
- [Testing](../development/testing.md): pytest, dbt tests and definition validation in depth
- [Adding Python assets](../development/adding-python-assets.md): where new Dagster asset code goes
- [Standards](standards.md): the hook chain and CI
- [Command reference](../reference/commands.md): every `just` recipe
