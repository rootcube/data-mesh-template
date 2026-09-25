---
icon: material/test-tube
---

# Testing

Three kinds of checks, in increasing scope: pytest for Python code, dbt tests for the data, and
`just validate` for the wiring between everything. `just check` runs what CI runs; the
pre-commit hooks run the relevant subset on every commit.

## Python tests (pytest)

```bash
just test                      # uv run pytest (testpaths = tests, -q)
uv run pytest tests/test_snowflake_settings.py
uv run pytest -k keypair
```

`tests/` is flat and small, and every test runs offline: no Snowflake, no API, no Dagster
instance.

| File | Covers |
|------|--------|
| `tests/test_snowflake_settings.py` | `SnowflakeSettings.from_env()`: prefixed variables, blank values, `missing()`, `dlt_credentials()`, `schema_for_layer()` in dev (a blank prefix falls back to `DBT_<LAYER>`, never `_<LAYER>`) and in `prd` |
| `tests/test_keypair.py` | `scripts/snowflake.py`: key generation, PKCS#8 output, passphrase encryption, key fingerprints and the replace prompt, key rotation with `.bak` files, schema prefix rules, context discovery, `init.sql` and `account_settings.sql` |
| `tests/test_dotenv.py` | `update_env_file()`: in-place replacement of every line of a key, appending, creating the file, bare versus single-quoted values, refusing values `.env` cannot hold |
| `tests/test_dlt_pipelines.py` | `discover()` finds the `knmi` source; the load stage, merge staging in the temporary layer and `truncate_staging_dataset` from `.dlt/config.toml` |

Conventions for new tests: a `test_<module>.py` next to these, plain functions, `tmp_path` for
files, no network. Logic worth testing lives in plain functions (a date chunker, a settings
reader), not inside an asset body. `pyproject.toml` configures pytest (`testpaths = ["tests"]`,
`addopts = "-q"`); `ty` type-checks `tests/` along with the source packages.

## dbt tests

Data tests are declared in each model's `_conf/` YAML and run wherever the models run:

```bash
just dbt build                                        # seed + run + test, dependency order
just dbt build --select stg__knmi__climate_hourly+    # a model and everything downstream
just dbt test --select stg__knmi__climate_hourly      # tests only
```

In Dagster, materializing a dbt asset runs `dbt build` for the selection, and failing tests
show on the asset. Failures are stored: `dbt_example` sets `+store_failures: true` with
`+schema: tmp`, so every failing test leaves a table with the offending rows in the temporary
layer (`DBT_<USERNAME>_TMP` in dev, `_TMP` elsewhere). `has_data` is the one exception; its failure
row is a constant, so it switches storing off.

Tests available: dbt's built-ins (`not_null`, `unique`, `accepted_values`, `relationships`),
the `dbt_utils` generics (`unique_combination_of_columns` is the one
`stg__knmi__climate_hourly` uses for its grain) and the four `dbt_common` generics
(`dbt_common.has_data`, `dbt_common.rows_expected`, `dbt_common.not_empty`,
`dbt_common.not_negative`). A model needs at least a uniqueness test on its grain, `not_null` on
its keys and `has_data`; every test is named. See [Adding a dbt model](adding-dbt-models.md).

`dbt parse --target dummy` is the no-connection check: it validates project config, YAML and
`ref()`/`source()` wiring without touching Snowflake (the `dummy` target is an in-memory
DuckDB). It does not run tests or compile SQL against real objects, so a passing parse is
necessary, not sufficient.

## `just validate`

```bash
just validate    # dagster definitions validate -w workspace.yaml
```

Loads every code location in `workspace.yaml`, each in its own subprocess, exactly like
`just start` does. It catches import errors, a broken `defs.yaml`, a dbt project that does not
parse, and missing dbt packages (the dbt locations run `dbt parse` on load). Run it after any
change to `src/`, `dlt_pipelines/`, `dbt/` or `workspace.yaml`. If it fails, `just start` will
fail the same way.

Dagster's CLI marks `dagster definitions validate` as superseded by `dg check defs`, which
only loads the project's `defs_module` from `pyproject.toml` and ignores `workspace.yaml`. The
recipe (which the pre-commit hook runs) and CI keep the old command and silence that one warning
through `PYTHONWARNINGS`, next to the global Snowflake connector filter; `just validate` works the
same in PowerShell.

## `just check`

Everything CI runs, in one recipe:

```bash
just check
```

1. `just lint`: `ruff check`, `ruff format --check`, `sqlfluff lint models` in the dbt project
2. `just typecheck`: `ty check` over `src/`, `dlt_pipelines/`, `scripts/`, `tests/`
3. `just test`: pytest
4. `dbt parse --target dummy` in every project (`scripts/dbt_all.py`)
5. `dagster definitions validate -w workspace.yaml`
6. The Terraform YAML validation (`terraform/config/_validation/validate_configs.py`, the same
   thing `just tf-validate-config` runs)

`just fmt` first (ruff format, `ruff check --fix`, `sqlfluff fix models`) saves a round trip.

## Pre-commit hooks

Install once with `just pre-commit-install`; run everything by hand with `just pre-commit`.
The hooks in `.pre-commit-config.yaml`:

| Hook | Runs | On |
|------|------|----|
| `trailing-whitespace`, `end-of-file-fixer`, `check-yaml --unsafe`, `check-added-large-files`, `check-merge-conflict`, `detect-private-key` | pre-commit-hooks | all files |
| `ruff-format`, `ruff-check --fix` | ruff | `*.py` |
| `ty-check` | `ty check` (whole project) | any `*.py` change |
| `dbt-parse` | `dbt parse --target dummy` in every project | `dbt/**/*.sql`, `.yml`, `.yaml`, `.csv`, `.py` |
| `sqlfluff-lint` | `just sqlfluff lint models` (inside `dbt/dbt_example`) | `dbt/dbt_example/models/**/*.sql` |
| `dagster-validate` | `just validate` | `src/**` and `dlt_pipelines/**` `.py`/`.yaml` |
| `terraform-fmt` | `terraform fmt -recursive terraform` | `*.tf` (needs the `terraform` binary, so in practice administrators) |
| `validate-configs` | `validate_configs.py` (schemas and cross-references) | `terraform/config/**` `.yaml`/`.json` |

`detect-private-key` is there for a reason: the `.p8` files stay under `~/.snowflake/keys/`, never
in the repo. The two hooks that call `just` need it on the `PATH`, also for a commit from an IDE.

!!! danger "Never bypass the hooks"
    `git commit --no-verify` is off-limits. Fix the issue; CI runs the same checks and fails
    anyway.

## What CI runs

`.github/workflows/ci.yml` runs on every push to `main` and every pull request, five jobs in
parallel:

| Job | Steps |
|-----|-------|
| Python | `uv sync --locked`, `ruff format --check`, `ruff check`, `ty check`, `pytest` |
| dbt parse + Dagster definitions | `dbt_all.py deps`, `dbt_all.py parse --target dummy`, `sqlfluff lint models` in `dbt/dbt_example`, `dagster definitions validate -w workspace.yaml` with `DBT_TARGET=dummy` |
| Terraform | `terraform fmt -check`, `terraform init -backend=false`, `terraform validate`, `validate_configs.py` |
| Docs | `uv sync --locked --group docs`, `zensical build --strict` |
| Setup (Linux, macOS, Windows) | The fresh-machine path: `just init`, `just info`, `just check`, `just sf keygen`, `just start` until the UI answers with every code location loaded, `just stop` until the port is free |

Every job but `Setup` installs with `uv sync --locked`, so a stale `uv.lock` fails CI: after changing
dependencies, run `uv lock` and commit `uv.lock`. `Setup` installs the way an engineer does, through
`just init`. CI has no Snowflake credentials. Everything it does works with the `dummy` target and an empty
`DAGSTER_HOME`; that is the design constraint behind the `dummy` target and the lazy credential
checks in dlt and the Dagster resource.

## What runs when

| Check | Local | Commit hook | CI |
|-------|-------|-------------|----|
| ruff, ty | `just lint`, `just typecheck` | yes | yes |
| pytest | `just test` | no | yes |
| sqlfluff | `just lint` | yes (`dbt_example` models) | yes |
| dbt parse (dummy) | `just dbt-all parse --target dummy` | yes | yes |
| Dagster definitions | `just validate` | yes | yes |
| Terraform YAML | `just tf-validate-config` | yes | yes |
| dbt data tests | `just dbt build` | no | no (needs a Snowflake connection) |
| docs | `just docs build --strict` | no | yes |
