---
icon: material/language-python
---

# Python style

Python 3.13, formatted and linted by ruff, type-checked by ty, fully type-annotated, and
deliberately boring. This page covers formatting, typing, naming, the simplicity rules, and the
patterns to reuse instead of reinventing.

The version is pinned in `.python-version` and `requires-python = ">=3.13,<3.14"`, and **uv**
manages the environment. Nobody activates the venv: every command runs through `uv run`, which
`just` does for you.

## ruff

ruff is the only Python linter and formatter. Configuration lives in `pyproject.toml`:

```toml title="pyproject.toml"
--8<-- "pyproject.toml:69:75"
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
under `[tool.ty]`: it checks `src/`, `dlt_pipelines/`, `scripts/`, `tests/` and
`terraform/config/_validation/` against Python 3.13. `dbt/` is left out for the same Snowpark
reason as above.

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
| Module-private names | `_` prefix | `_build_defs`, `_PROJECT_ROOT` |
| Booleans | `is_` / `has_` prefix | `is_personal`, `is_encrypted` |

Imports are ordered stdlib, third-party, local, each group separated by a blank line (ruff's `I`
rules enforce it). No wildcard imports.

```python title="dlt_pipelines/pipelines/ingest/knmi/source.py"
--8<-- "dlt_pipelines/pipelines/ingest/knmi/source.py:9:21"
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
    environment: str = "dev"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> SnowflakeSettings: ...
```

## Error handling and logging

- Catch **specific exception types**, never a bare `except`. Where a broad catch is unavoidable,
  say why on the same line: `except Exception as exc:  # noqa: BLE001 - ...`.
- Degrade gracefully only where that is the right call (`restrict_to_owner` in
  `scripts/snowflake.py` warns instead of failing when `icacls` cannot restrict a file on
  Windows); fail loudly everywhere else.
- Utility modules log through the `logging` module; Dagster assets use `context.log`.

```python title="dlt_pipelines/pipelines/ingest/knmi/source.py (excerpt)"
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
    [environment variables](environment-variables.md).

Layer schemas
:   `SnowflakeSettings.schema_for_layer("stg")` returns `_STG` in the shared environments and
    `<SNOWFLAKE_SCHEMA>_STG` in dev (`DBT_USERNAME_STG`). It is the Python side of the rule that
    `dbt_common.generate_schema_name` implements for dbt. Never spell a layer schema by hand.

dlt destination and dataset
:   `snowflake_destination(source)` and `source_dataset()` in `dlt_pipelines/utils/destination.py`
    build the destination and the source-layer schema every ingest pipeline loads into. A new
    pipeline calls them; it does not build its own.

Dagster definitions
:   `build_dbt_defs()` in `src/orchestrator/locations/dbt/shared.py` turns a dbt project into a
    code location with its jobs and its source-freshness chain; dlt loads and dbt projects are
    declared in a `defs.yaml` rather than in Python. Extend those factories instead of writing
    assets and jobs by hand. See [adding Python assets](../build/adding-python-assets.md) and
    [adding dlt loads](../build/adding-dlt-loads.md).

`.env` editing
:   `update_env_file()` in `src/orchestrator/utils/dotenv.py` rewrites `KEY=value` lines and keeps
    comments and ordering. Values are written bare when they hold only `[A-Za-z0-9_./:@+,=-]`,
    otherwise in single quotes, which `just` and python-dotenv both strip; values single quotes
    cannot carry for both readers raise `ValueError`.

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
(`tests/test_dotenv.py`, `tests/test_snowflake_settings.py`). Two habits keep them free of
mocking:

- **Pass inputs as arguments.** `SnowflakeSettings.from_env(env)` takes any mapping, so a test
  builds a dict instead of patching `os.environ`. Write new functions the same way.
- **Write into `tmp_path`.** Anything that touches a file (`.env`, a key pair) gets the pytest
  fixture, never the repo.

`scripts/` is not a package: `tests/test_keypair.py` loads `scripts/snowflake.py` by path with
`importlib.util.spec_from_file_location`. Copy that helper to test another script. What the suite
covers, and the dbt and Dagster halves of testing: [Testing](../build/testing.md).

## Dependencies

`pyproject.toml` is authoritative and `uv` resolves it. The `dev` group installs on every plain
`uv sync` (`default-groups`); the `docs` group is pulled in by `just docs` with `--group docs`.

```bash
uv sync            # after pulling dependency changes
uv lock --upgrade  # rewrites uv.lock
```

Never edit `uv.lock` by hand. CI installs with `uv sync --locked`, so a lockfile that no longer
matches `pyproject.toml` fails the build: run `uv lock` and include it in the same change.

## Where the configuration lives

| What | Where |
|---|---|
| ruff | `pyproject.toml`: `[tool.ruff]`, `[tool.ruff.lint]` |
| ty | `pyproject.toml`: `[tool.ty.src]`, `[tool.ty.environment]` |
| pytest | `pyproject.toml`: `[tool.pytest.ini_options]` |
| Dependency groups | `pyproject.toml`: `[dependency-groups]`, `[tool.uv]` |
| dg (Dagster CLI) | `pyproject.toml`: `[tool.dg]`, `[tool.dg.project]` |
| Hooks | `.pre-commit-config.yaml` |

Pre-commit runs `ruff format`, `ruff check --fix` and `ty check` on every commit that touches
Python; the CI `python` job repeats them and adds `pytest`, which is not a hook, so run
`just test` yourself. The full chain: [What runs when](git-workflow.md#what-runs-when).

!!! danger "Never `--no-verify`"
    Bypassing pre-commit hooks is explicitly forbidden. If a hook fails, fix the cause; the same
    checks fail the pull request anyway.

## Related pages

- [Naming](naming.md): dlt asset keys, Dagster names, schemas
- [Adding Python assets](../build/adding-python-assets.md)
- [For AI agents](ai-agents.md): what to run after changing what
- [Commands](commands.md)
