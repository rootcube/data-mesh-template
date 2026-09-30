---
icon: material/test-tube
---

# Testing

Three kinds of check, in increasing scope: pytest for Python code, dbt tests for the data, and
`just validate` for the wiring between everything. `just check` runs what CI runs, apart from the
Terraform fmt and validate legs and the hygiene hooks, and the pre-commit hooks run the relevant
subset on every commit.

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
| `tests/test_dlt_pipelines.py` | The shared dlt layer: the load stage path, the folder per load, merge staging in the temporary layer and `truncate_staging_dataset` from `.dlt/config.toml` |
| `tests/test_dlt_knmi.py` | The example source on its own: `discover()` finds `knmi`, the load window never reaches past `START_DATE`, an empty API response fails the run. `pytest.importorskip` skips the module when the KNMI folder is gone, so deleting the example does not break collection |
| `tests/test_dbt_asset_keys.py` | `compute_asset_key()`: the path-based key for a project's own models, the `packages/<package>/` prefix for package nodes, Windows path separators, and a `config.meta.dagster.asset_key` that overrides all of it |
| `tests/test_dbt_source_freshness.py` | The freshness chain: `diff_freshness()` (first tick, unchanged, advanced, a source dbt could not query), `dbt_selector()`, the `<kind>__<location>__<name>` names of the jobs, schedule and sensor, their default status, and one sensor tick over a `sources.json` in `tmp_path` (run request, observation, cursor, then a skip) |
| `tests/test_dlt_location.py` | The dlt location derives, per source, a `job__dlt__ingest_<source>` selecting only that source's assets and its daily schedule; `job__dlt__ingest_all` has an opt-in schedule, stopped by default |
| `tests/test_schema_rule.py` | The layer-to-schema rule in all three places: `schema_for_layer()`, the `dbt_common.generate_schema_name` macro and the inline `schema:` of `sources/src_knmi.yml`, rendered with plain jinja2 over the environments, both prefixes and every layer |
| `tests/test_validate_configs.py` | `terraform/config/_validation/validate_configs.py`: schemas, project and role cross references, user role assignments, duplicate user file names, required versus disabled, required configs per project. One passing config tree under `tmp_path` and a broken one per rule |

Conventions for a new test: a `test_<module>.py` next to these, plain functions, `tmp_path` for
files, no network. Logic worth testing lives in plain functions (a date chunker, a settings
reader), not inside an asset body. `pyproject.toml` configures pytest (`testpaths = ["tests"]`,
`addopts = "-q"`), and `ty` type-checks `tests/` along with the source packages. A rule that
exists in more than one language (the layer schemas, the asset keys) gets a test that renders the
other implementations and compares them, so the copies cannot drift apart unnoticed.

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

A model needs at least a uniqueness test on its grain, `not_null` on its keys and `has_data`, and
every test is named. Which generics you can call, and how to declare them:
[Adding a dbt model](adding-dbt-models.md).

`dbt parse --target local` is the no-Snowflake check: it validates project config, YAML and
`ref()`/`source()` wiring against the local DuckDB file, not against Snowflake. It does not run
tests or build models against real objects, so a passing parse is necessary, not sufficient.

## `just validate`

```bash
just validate    # dagster definitions validate -w workspace.yaml, then scripts/check_asset_keys.py
```

Loads every code location in `workspace.yaml`, each in its own subprocess, catching import errors,
a broken `defs.yaml`, translator and selection errors, and missing dbt packages. The dbt locations
read the manifest the last `dbt parse` wrote (`just init` and `just check` run it; only
`dagster dev` re-parses on load), so after editing models run `just dbt-all parse --target local`
before you trust the result. Run `just validate` after any change to `src/`, `dlt_pipelines/`,
`dbt/` or `workspace.yaml`: if it fails, `just start` fails the same way.

Because each location loads on its own, that command cannot see the one thing they share: the
asset keys that carry lineage across them. `scripts/check_asset_keys.py` loads them all in one
process and compares the `dlt/` keys, so a dbt source whose `config.meta.dagster.asset_key` no
longer matches a dlt asset is an error, and a dlt asset that no dbt source claims is a warning (it
may simply be unused).

Dagster's CLI marks `dagster definitions validate` as superseded by `dg check defs`, which only
loads the project's `defs_module` from `pyproject.toml` and ignores `workspace.yaml`. The recipe
(which the pre-commit hook runs) and CI keep the old command and silence that one warning through
`PYTHONWARNINGS`, next to the global Snowflake connector filter. `just validate` works the same in
PowerShell.

## `just check`

All of it in one recipe, and the last thing to run before you hand a change over:

```bash
just check
```

1. `just lint`: `ruff check`, `ruff format --check`, `sqlfluff lint models` in every project under
   `dbt/`, `dbt_common` included
2. `just typecheck`: `ty check` over `src/`, `dlt_pipelines/`, `scripts/`, `tests/` and
   `terraform/config/_validation/`
3. `just test`: pytest
4. `dbt parse --target local` in every project (`scripts/dbt_all.py`), as is and again with
   `--use-v2-parser`, so the projects stay ready for dbt v2
5. `just validate`: `dagster definitions validate -w workspace.yaml` and the asset key contract
   (`scripts/check_asset_keys.py`)
6. The Terraform YAML validation (`terraform/config/_validation/validate_configs.py`, the same
   thing `just tf-validate-config` runs)
7. `scripts/check_doc_fences.py`: every fence titled with a repository path is a verbatim copy of
   that file
8. `just docs build --strict`

`just fmt` first (`ruff check --fix`, ruff format, `sqlfluff fix models`) saves a round trip.

## Pre-commit hooks

Install once with `just pre-commit-install`; run everything by hand with `just pre-commit`.
The hooks in `.pre-commit-config.yaml`:

| Hook | Runs | On |
|------|------|----|
| `trailing-whitespace`, `end-of-file-fixer`, `check-yaml --unsafe`, `check-added-large-files`, `check-merge-conflict`, `detect-private-key` | pre-commit-hooks | all files |
| `ruff-format`, `ruff-check --fix` | ruff | `*.py` |
| `ty-check` | `ty check` (whole project) | any `*.py` change |
| `dbt-parse` | `dbt parse --target local` in every project | `dbt/**/*.sql`, `.yml`, `.yaml`, `.csv`, `.py` |
| `dbt-parse-v2` | the same parse with `--use-v2-parser`, so the projects stay ready for dbt v2 | same files |
| `sqlfluff-lint`, one hook per project | `sqlfluff lint models` in that project; lint only, so run `just fmt` first | that project's `models/**/*.sql` |
| `dagster-validate` | `just validate` (definitions plus the asset key contract) | `src/**` and `dlt_pipelines/**` `.py`/`.yaml`, and the `sources/` YAML of every dbt project |
| `doc-fences` | `scripts/check_doc_fences.py` | `docs/**` |
| `terraform-fmt` | `terraform fmt -recursive terraform` | `*.tf` (needs the `terraform` binary, so in practice administrators) |
| `validate-configs` | `validate_configs.py` (schemas and cross-references) | `terraform/config/**` `.yaml`/`.json` |

`check-yaml` runs with `--unsafe` because dbt YAML carries `{{ env_var() }}` and `defs.yaml`
carries templates; `detect-private-key` keeps a `.p8` out of the repo, they live under
`~/.snowflake/keys/`. Four details that catch people out:

- **A new dbt project needs its own sqlfluff hook entry.** Each one fires only on its own models;
  the `.sqlfluff` config under `dbt/` is shared. See [Adding a project](adding-projects.md).
- **The sqlfluff and Dagster hooks call `just`**, so a commit needs `just` on the `PATH`, an IDE
  running the hooks included. In return they behave the same on Windows, where no `bash` is at
  hand.
- **`dbt parse` needs the packages.** Without `just dbt-all deps` the dbt and Dagster hooks fail
  before your change is even looked at.
- **`just pre-commit` runs with `.env` loaded**, so the dbt hooks use whatever `DBT_TARGET` says.
  CI has no `.env` and sets `DBT_TARGET=local` explicitly.

!!! danger "Never bypass the hooks"
    `git commit --no-verify` is off-limits. Fix the issue; CI runs the same checks and fails
    anyway.

## What CI runs

`.github/workflows/ci.yml` runs on every push to `main` and every pull request: a `Changed paths`
job that lists what the change touches, then six check jobs in parallel:

| Job | Steps |
|-----|-------|
| Hygiene hooks | `uv sync --locked`, then `pre-commit run --all-files` for `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-added-large-files`, `check-merge-conflict` and `detect-private-key` |
| Python | `uv sync --locked`, `ruff format --check`, `ruff check`, `ty check`, `pytest` |
| dbt parse + Dagster definitions | `dbt_all.py deps`, `dbt_all.py parse --target local`, the same parse with `--use-v2-parser`, `sqlfluff lint models` in every project under `dbt/`, `dagster definitions validate -w workspace.yaml` and `check_asset_keys.py`, all against the local DuckDB file (`DBT_TARGET=local`, `DUCKDB_PATH`) |
| Terraform | `terraform fmt -check`, `terraform init -backend=false`, `terraform validate`, `validate_configs.py` |
| Docs | `uv sync --locked --group docs`, `check_doc_fences.py`, `zensical build --strict` |
| Setup (Linux, macOS, Windows) | The fresh-machine path: `just init`, `just info`, `just check`, `just sf keygen`, `just start` until the UI answers with every code location loaded, `just stop` until the port is free |

On a pull request each check job runs only when the change touches its inputs; a skipped job
counts as passed for the required checks. Python and Terraform watch their own trees, dbt + Dagster
watches `dbt/`, `src/`, `dlt_pipelines/` and `workspace.yaml`, Docs watches `docs/` (the
template overrides in `docs/.overrides/` included), `mkdocs.yml` and the files the pages include
with `--8<--`, and the Setup matrix only the tooling path: the justfile, `scripts/`,
`.env.example`, `.envrc` and the dbt package files. A dependency
change (`pyproject.toml`, `uv.lock`, `.python-version`) or an edit to `ci.yml` runs everything, as
do pushes to `main` and manual runs. The `Setup` matrix is not a required check in the `main`
ruleset: it is the fresh-machine test of the setup path, and a runner hiccup on one OS should not
block a pull request. Treat a red leg as a bug in that recipe all the same.

`Hygiene hooks` is the one job `Changed paths` does not gate: it takes seconds, and trailing
whitespace or a stray private key can land in any file. It is also the only part of the pre-commit
chain CI would otherwise miss, since the rest needs `just`, the dbt packages and the terraform
binary and every check it makes is a step in another job. It is not a required check in the `main`
ruleset yet; add its `Hygiene hooks` context to `.github/rulesets/main.json` to make it one.

Every job but `Setup` installs with `uv sync --locked`, so a stale `uv.lock` fails CI: after
changing dependencies, run `uv lock` and commit `uv.lock`. `Setup` installs the way an engineer
does, through `just init`. CI holds no Snowflake credentials at all, and everything it runs works
with the `local` target and an empty `DAGSTER_HOME`. That constraint is why the `local` target
exists and why dlt and the Dagster resource check credentials lazily.

## What runs when

| Check | Local | Commit hook | CI |
|-------|-------|-------------|----|
| hygiene hooks (whitespace, end of file, YAML, large files, merge markers, private keys) | `just pre-commit` | yes | yes (Hygiene job) |
| ruff, ty | `just lint`, `just typecheck` | yes | yes |
| pytest | `just test` | no | yes |
| sqlfluff | `just lint` | yes (every project under `dbt/`) | yes |
| dbt parse (local) | `just dbt-all parse --target local` | yes | yes |
| Dagster definitions | `just validate` | yes | yes |
| dlt/dbt asset keys | `just validate` | yes, in the same hook (so not on a `dbt/` edit) | yes |
| Terraform YAML | `just tf-validate-config` | yes | yes |
| dbt data tests | `just dbt build` | no | no (needs a Snowflake connection) |
| doc fences | `just check` | yes (`docs/` files) | yes (Docs job) |
| docs | `just docs build --strict` | no | yes |
