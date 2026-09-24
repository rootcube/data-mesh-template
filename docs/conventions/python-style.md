---
icon: material/language-python
---

# Python style

Python 3.13, formatted and linted by ruff, type-checked by ty, fully type-annotated, and
deliberately boring. This page covers formatting, typing, naming, the simplicity rules, and the
patterns to reuse instead of reinventing.

## ruff

ruff is the only Python linter and formatter. Configuration lives in `pyproject.toml`:

```toml title="pyproject.toml"
[tool.ruff]
line-length = 120
extend-exclude = ["dbt", "terraform", "site", "docs"]

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
```

| Rule set | What it catches |
|---|---|
| `E` | pycodestyle errors: whitespace, line length and friends |
| `F` | pyflakes: unused imports and variables, undefined names |
| `I` | import ordering (isort) |
| `UP` | outdated syntax that has a Python 3.13 replacement |
| `B` | bugbear: likely bugs such as mutable default arguments |

`dbt/` is excluded on purpose: the one Python model in `dbt_common` runs inside Snowflake's
Snowpark runtime, not in this venv. `docs/` is excluded because ruff would otherwise format the
illustrative Python fences in the Markdown.

Run it through the task runner or directly:

=== "just"

    ```bash
    just fmt    # ruff format + ruff check --fix (+ sqlfluff fix)
    just lint   # ruff check + ruff format --check (+ sqlfluff lint), no changes
    ```

=== "ruff directly"

    ```bash
    uv run ruff format .
    uv run ruff check --fix .
    ```

## Type annotations

All code is fully type-annotated: every parameter and every return type. Use the Python 3.13
syntax. Real signatures from the repo:

```python
# PEP 604 unions, never Optional[X]
def from_env(cls, env: Mapping[str, str] | None = None) -> SnowflakeSettings: ...


# Built-in generics, never typing.Dict / typing.List
def dlt_credentials(self) -> dict[str, str]: ...


# Iterator for generator functions
def date_chunks(start: datetime, end: datetime, days: int) -> Iterator[tuple[str, str]]: ...


# Always annotate the return type, even when it is None
def step(title: str) -> None: ...


# Annotate variables whose type is not obvious
failed: list[str] = []
```

!!! danger "`Optional[X]` is banned"
    Use `X | None`. It is one of the explicit rules in `AGENTS.md`.

The ruff rule set does not include the `ANN` rules, so a missing annotation does not fail lint.
Reviewers (and agents) check for it; ty checks that the annotations you write are consistent.

## Type checking

[ty](https://docs.astral.sh/ty/) is the type checker. Configuration lives in `pyproject.toml`
under `[tool.ty]`: it checks `src/`, `dlt_pipelines/`, `scripts/` and `tests/` against Python
3.13. `dbt/` is left out for the same Snowpark reason as above.

=== "just"

    ```bash
    just typecheck
    ```

=== "ty directly"

    ```bash
    uv run ty check
    ```

A suppression comment is a last resort and always carries a reason, the way `scripts/snowflake.py`
does with `# noqa: BLE001 - report whatever the connector raises`. The repo has no `# ty: ignore`
today; keep it that way if you can.

## Naming

| Kind | Convention | Example |
|---|---|---|
| Constants | `UPPER_SNAKE_CASE` | `ENV_PREFIX`, `DAYS_BACK`, `STATIONS`, `SOURCE_LAYER` |
| Classes | `PascalCase` | `SnowflakeSettings` |
| Functions, methods, variables | `lower_snake_case` | `build_dbt_defs`, `fetch_hourly_observations`, `schema_for_layer` |
| Module-private names | `_` prefix | `_build_defs`, `_chmod`, `_PROJECT_ROOT` |
| Booleans | `is_` / `has_` prefix | `is_personal`, `is_encrypted` |

Imports are ordered stdlib, third-party, local, each group separated by a blank line (ruff's `I`
rules enforce it). No wildcard imports.

```python title="dlt_pipelines/pipelines/ingest/knmi/source.py"
import logging
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

from dlt.sources.helpers import requests as dlt_requests

from dlt_pipelines.pipelines.ingest.knmi.constants import CHUNK_DAYS, DAYS_BACK, KNMI_UURGEGEVENS_URL, STATIONS
```

## Docstrings

Every module outside `tests/` starts with a docstring saying what it is for and how it fits in.
Public functions get a short docstring, one line when one line will do:

```python
def fetch_hourly_observations(days_back: int = DAYS_BACK) -> Iterator[dict]:
    """Yield one dict per station per hour for the last `days_back` days."""
```

Do not add docstrings to private helpers whose name already says what they do, and do not add
docstrings to code you are not otherwise changing ("no unsolicited docstrings", `AGENTS.md`).

## Classes

A function is the default. Reach for a class when there is state to carry or a framework contract
to meet. The only class in `src/orchestrator/` is a frozen dataclass:

```python title="src/orchestrator/resources/snowflake.py (pattern)"
@dataclass(frozen=True)
class SnowflakeSettings:
    """A connection to one project database, as read from the SNOWFLAKE_* environment variables."""

    account: str = ""
    user: str = ""
    ...
    environment: str = "dev"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> SnowflakeSettings:
        ...

    def schema_for_layer(self, layer_code: str) -> str:
        """The schema a layer lives in: `_<LAYER>`, or `<SNOWFLAKE_SCHEMA>_<LAYER>` in dev."""
        ...
```

## Error handling and logging

- Catch **specific exception types**, never a bare `except`. Where a broad catch is unavoidable,
  say why on the same line: `except Exception as exc:  # noqa: BLE001 - ...`.
- Degrade gracefully only where that is the right call (`_chmod` in `scripts/snowflake.py`
  swallows `OSError` on Windows and says so in a comment); fail loudly everywhere else.
- Utility modules log through the `logging` module; Dagster assets use `context.log`.

```python title="dlt_pipelines/pipelines/ingest/knmi/source.py"
LOGGER = logging.getLogger(__name__)

LOGGER.info("KNMI hourly: fetching %s..%s for stations %s", chunk_start, chunk_end, stations)
```

## Simplicity rules

Straight from `AGENTS.md`, and they apply to every Python change:

- **Small functions.** One thing per function; if you cannot describe it in one sentence, split it.
- **Flat is better than nested.** More than three levels of indentation means refactor.
- **Max four parameters.** Beyond that, use a dataclass or config object.
- **No premature abstractions.** Three similar lines beat a premature helper function.
- **No unnecessary indirection.** No wrappers, no classes where a function will do.
- **Delete dead code.** Do not comment it out or keep it "for reference".

## Patterns to reuse

Before writing something new, check whether one of these already covers it:

Snowflake settings
:   `SnowflakeSettings.from_env()` in `src/orchestrator/resources/snowflake.py` is the only reader
    of the `SNOWFLAKE_*` variables and `ENVIRONMENT`. It hands out `connect()` for the Snowflake
    connector and `dlt_credentials()` for dlt. Never read
    `os.environ["SNOWFLAKE_..."]` yourself. See
    [environment variables](../reference/environment-variables.md).

Layer schemas
:   `SnowflakeSettings.schema_for_layer("stg")` returns `_STG` in the shared environments and
    `<SNOWFLAKE_SCHEMA>_STG` in dev (`DBT_USERNAME_STG`). It is the Python side of the rule that
    `dbt_common.generate_schema_name` implements for dbt. Never spell a layer schema by hand.

dlt destination and dataset
:   `snowflake_destination()` and `source_dataset()` in `dlt_pipelines/utils/destination.py`
    build the destination and the source-layer schema every ingest pipeline loads into. A new
    pipeline calls them; it does not build its own.

Dagster code locations
:   `build_dbt_defs(project_name, defs_module)` in `src/orchestrator/locations/dbt/shared.py` turns
    a dbt project into a code location with a `job_<project>_build_all` job. dlt loads are
    declared in a `defs.yaml` next to the pipeline (`dagster_dlt.DltLoadCollectionComponent`),
    dbt projects in `defs/dbt/defs.yaml` (`DataMeshDbtProjectComponent` in `shared.py`, a
    `dagster_dbt.DbtProjectComponent` with path-based keys). Extend those instead
    of writing assets by hand. See [adding Python assets](../development/adding-python-assets.md)
    and [adding dlt loads](../development/adding-dlt-loads.md).

`.env` editing
:   `update_env_file()` in `src/orchestrator/utils/dotenv.py` rewrites `KEY=value` lines and keeps
    comments and ordering. Values are written unquoted on purpose: `just` passes quoted values
    literally.

## Python or SQL?

Most transformations belong in **SQL dbt models**. Reach for Python only when SQL cannot express
the logic:

| Use | When |
|---|---|
| SQL (dbt model) | Joins, filters, aggregations, window functions, casting, CTEs (the default) |
| Python (Snowpark dbt model) | Logic SQL handles poorly, such as a library lookup; `int__common__holiday.py` in `dbt_common` is the one example |
| Python (dlt pipeline or Dagster asset) | External APIs and non-database data, such as the KNMI load |

If in doubt, use SQL.

## DataFrames

The local environment has no DataFrame library as a dependency. The only DataFrame code is the
Snowpark model above, which runs inside Snowflake where pandas is provided. If a Python asset
genuinely needs one, add it to `pyproject.toml` and run `uv sync` first, and never mix
DataFrame libraries in one function.

## Testing

pytest, configured in `pyproject.toml` (`testpaths = ["tests"]`, `addopts = "-q"`). Tests are
offline: no Snowflake, no network. Plain test functions named
`test_<function>_<what_it_should_do>`, in files named after the module they cover
(`tests/test_dotenv.py`, `tests/test_snowflake_settings.py`), using pytest fixtures such as
`tmp_path`. Full guidance: [Testing](../development/testing.md).

## Enforcement

Pre-commit runs `ruff format`, `ruff check --fix` and `ty check` on every commit that touches
Python. The CI `python` job repeats `ruff format --check`, `ruff check`, `ty check` and `pytest`
on every pull request. pytest is not a pre-commit hook, so run `just test` before you push.

!!! danger "Never `--no-verify`"
    Bypassing pre-commit hooks is explicitly forbidden. If a hook fails, fix the cause; the same
    checks fail the pull request anyway.

## Related pages

- [Naming](naming.md): dlt asset keys, Dagster names, schemas
- [Adding Python assets](../development/adding-python-assets.md)
- [AI agent guide: Python](../ai-agents/python.md)
- [Commands](../reference/commands.md)
