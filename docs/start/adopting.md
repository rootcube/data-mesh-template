---
icon: material/content-copy
---

# Making it yours

This repository is a starter, not a dependency: you copy it and it becomes yours. Three things to
do once, in this order: take your own copy, rename or remove the example, and take over the
repository furniture that still points at the upstream project.

## Take your own copy

Use GitHub's **Use this template** button if upstream offers it, or fork, or clone and push to a
repository of your own. Either way, add upstream as a second remote; that is what later fixes
arrive through:

```bash
git clone https://github.com/<you>/<your-repo>.git && cd <your-repo>
git remote add upstream https://github.com/rootcube/data-mesh-template.git
git fetch upstream
```

Then continue with [Start](index.md): `just init`, `just setup`.

## Rename or remove the example

The starter ships one organisation, one team, one project (`example`), one dbt project
(`dbt_example`), one dlt source (`knmi`) and one example user. Rename what you keep and delete what
you do not. A project's `code` has to equal its file name, and the Snowflake names follow from it:
`DB_<CODE>_<ENV>`, `WH_<CODE>_<ENV>`, `RL_<CODE>_<ENV>__<PURPOSE>`.

| What | Where |
|------|-------|
| Organisation | `terraform/config/organisations/example.yaml`: file name, `code`, `name`, `desc`, plus `organisation:` in every file under `terraform/config/teams/` |
| Team | `terraform/config/teams/platform.yaml`: file name, `code`, `name`, `owners`, plus `team:` in every file under `terraform/config/projects/` |
| Project | `terraform/config/projects/example.yaml`: file name and `code` (they must match), and its `environments`, `layers`, `computes` and `roles` lists |
| Example user | `terraform/config/users/username_example.yaml`: replace it with one file per person, or delete it (it ships `disabled: true`, so it provisions nothing) |
| dbt project | the folder `dbt/dbt_example/` and `name:` in its `dbt_project.yml`; then `project := "dbt_example"` in the `justfile` and the `dbt/dbt_example` paths in `.github/workflows/ci.yml` and `.pre-commit-config.yaml` (`just info` discovers projects by itself) |
| Dagster code location | the package `src/orchestrator/locations/dbt/dbt_example/` (`definitions.py` and `defs/dbt/defs.yaml`) and its block in `workspace.yaml` |
| dlt source | the folder `dlt_pipelines/pipelines/ingest/knmi/`; then `dbt/dbt_example/sources/src_knmi.yml`, the models under `models/02_stg/knmi/`, `models/03_int/weather/`, `models/04_mrt/weather/` and `models/05_exp/weather/`, the seeds `seed_knmi_station` and `seed_knmi_measurement_type` with their `_conf/` YAML, and the exposure under `exposures/` |
| Tests that assert on the example | `tests/test_dlt_knmi.py` covers the KNMI source and skips itself when the folder is gone (`pytest.importorskip`), so deleting the source costs you coverage, not a red suite; `tests/test_dbt_asset_keys.py`, `tests/test_snowflake_settings.py` and `tests/test_keypair.py` assert on `dbt_example` and the `EXAMPLE` object names |
| Defaults in `.env` | `SNOWFLAKE_ROLE`, `SNOWFLAKE_WAREHOUSE` and `SNOWFLAKE_DATABASE` in `.env.example`, and in your own `.env` (or rerun `just sf context`) |
| Code ownership | the `Project: example` block and the `@rootcube/...` teams in `.github/CODEOWNERS` |

Do the halves of a removal in one change: a dlt source without its staging model, or a staging
model without its source, leaves a dbt project that cannot parse. Finish with `just check`.

Adding your own alongside the example instead of renaming it:
[Adding a project](../build/adding-projects.md),
[Adding a dlt load](../build/adding-dlt-loads.md).

## Take over the repository furniture

Everything below still names the upstream repository, so in your copy it is inert or plain wrong
until you change it.

| What | Do |
|------|----|
| `CHANGELOG.md` | Empty it. It is upstream's history, with upstream's commit links |
| `.release-please-manifest.json` | Set it to your own starting version, for instance `{".": "0.0.0"}` |
| `release-please-config.json` | Rename `package-name` |
| `pyproject.toml` | Rename `name`, rewrite `description`, and set `version` to match the manifest |
| `.github/workflows/release-please.yml` | The job's `if: github.repository == 'rootcube/data-mesh-template'` keeps release-please inert in a copy, so your first push to `main` does not continue upstream's version numbering. Put your own repository there to switch it on, or delete the workflow and version by hand |
| `SECURITY.md` | Replace the advisory link and the contact address; reports would otherwise go to a stranger |
| `.github/rulesets/main.json` | Apply it to your repository: `gh api -X POST repos/<owner>/<repo>/rulesets --input .github/rulesets/main.json`. The command in [Git workflow](../reference/git-workflow.md#protected-main) names the upstream repository |
| `.github/CODEOWNERS` | Replace the `@rootcube/...` teams with your own; GitHub ignores handles it cannot resolve |
| `LICENSE`, `NOTICE`, `LICENSES/` | The code you keep stays GPL-3.0. `NOTICE` and `LICENSES/` cover the third-party macros and the theme partial, so keep them as long as you keep those |

## Staying up to date with upstream

```bash
git fetch upstream
git merge upstream/main
```

Upstream owns the plumbing, you own the content. That split is what keeps a merge small:

| Usually upstream's | Usually yours |
|--------------------|---------------|
| `scripts/`, `src/orchestrator/` apart from your own code locations, `dbt/dbt_common/`, `dlt_pipelines/utils/`, `terraform/modules/`, `terraform/config/_validation/`, `justfile`, `.github/`, `docs/` | `terraform/config/` apart from `_validation/`, your `dbt/<project>/`, `dlt_pipelines/pipelines/`, your `src/orchestrator/locations/dbt/<project>/`, `workspace.yaml`, `.env` |

Expect conflicts in the files both sides touch: `.env.example`, `workspace.yaml`,
`.github/CODEOWNERS`, `pyproject.toml`, `CHANGELOG.md`, and anything you renamed above. After a
merge:

```bash
just init        # dependencies and dbt packages
just info        # reports keys .env.example gained that your .env is missing
just check       # lint, types, tests, dbt parse, Dagster definitions, config schemas, docs
```

`just init` never overwrites an existing `.env`, which is why `just info` compares it against
`.env.example` and names the difference. `just reset-local` clears the local state (run history,
caches, dbt `target/`) when a merge leaves something stale;
[First run](first-run.md#where-things-live-locally) lists what that removes.
