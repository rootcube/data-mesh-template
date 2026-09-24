# Vendored dbt_artifacts (upload machinery)

Vendored from [brooklyn-data/dbt_artifacts](https://github.com/brooklyn-data/dbt_artifacts) v2.10.0
(Apache License 2.0). Only the upload machinery is included - the macros invoked (directly or
transitively) by `upload_results`. Models, migration scripts, and integration tests were not vendored.

## Trims applied

- **Snowflake only.** This repo runs dbt-core 1.11 on Snowflake exclusively. Every adapter-specific
  macro variant for BigQuery, Databricks, Postgres, Redshift, Spark, SQL Server, Trino, Athena,
  Fabric, DuckDB, and Glue was deleted. Only the dispatcher macros (no prefix), `default__*`, and
  `snowflake__*` variants remain. Where upstream ships a `snowflake__` override (the four
  `*_executions` DML builders, `insert_into_metadata_table`, `column_identifier`, `parse_json`),
  the shadowed `default__` variant was dropped too, since dispatch can never reach it on Snowflake.
- **Explicit dispatch namespace.** The `parse_json`/`column_identifier` wrapper macros upstream call
  `adapter.dispatch(...)` without a namespace; the vendored copies pass `'dbt_common'` explicitly so
  they resolve when called from a consuming project.
- **Namespace rewrite.** `adapter.dispatch('<name>', 'dbt_artifacts')` -> `adapter.dispatch('<name>', 'dbt_common')`,
  and direct `dbt_artifacts.<macro>(...)` calls -> `dbt_common.<macro>(...)`. `var()` keys (e.g.
  `dbt_artifacts_exclude_all_results`, `is_development`) were left unchanged to match upstream
  conventions and any existing project configuration.
- **`get_relation.sql` replaced.** Upstream resolves the raw upload tables via a `graph.nodes` lookup,
  which requires the table models to exist in the calling project's own graph. This repo instead
  resolves them by naming convention: fixed identifiers `pre__dbt__*` in the `MTD` (metadata)
  schema of the target database (via `dbt_common.generate_schema_name`). The physical tables are
  created on demand by `create_metadata_tables_if_not_exist()` (see below), not built as models by
  any project. A monitoring project can consume them as dbt *sources*.
- **`create_metadata_tables.sql` added.** Local addition, not present upstream - see "Local
  additions" below.

## Excluded on purpose

- `models/`, `migration/`, `integration_tests/` (including `safe_cast.sql`) - not part of the upload
  path.
- `database_specific_helpers/generate_surrogate_key.sql` - not referenced by any upload macro.
- `database_specific_helpers/string_functions.sql` (`str_left`) - not referenced by any upload macro,
  and has no Snowflake variant upstream.
- `database_specific_helpers/type_helpers.sql` - not referenced by any upload macro.
- `utils/copy_model.sql` - only referenced from a commented-out line in upstream's `upload_models.sql`;
  the active code path uses `safe_copy_mapping` instead.

## Local additions

- **`upload_results/create_metadata_tables.sql`** (`create_metadata_tables_if_not_exist()`) - not
  part of upstream dbt_artifacts. Upstream assumes the `pre__dbt__*` tables already exist
  as models built by some other project; that assumption doesn't hold here, since any project can
  call `dbt_common.upload_results(results)` from its own `on-run-end` hook without depending on
  a monitoring project having run first. This macro is called at the top of `upload_results`
  (before the `datasets_to_load` logic) and makes the upload self-sufficient in any database:
  - In dev, creates the personal metadata schema if it does not exist; elsewhere `_MTD` is provisioned.
  - Runs a plain `create table if not exists <relation> (...)` (permanent table, not a CTAS) for
    each of the 11 datasets, with explicit column definitions matching
    `get_column_name_lists.sql`'s Snowflake column names/order exactly.
  - **Schema evolution is manual.** `create table if not exists` never alters an existing table. If
    a future sync from upstream changes a dataset's columns, both this file and
    `get_column_name_lists.sql` must be updated together, and any already-created tables in every
    environment need a coordinated `ALTER TABLE` - the macro will not do it for you.

- **`upload_individual_datasets/upload_source_freshness.sql`** - local addition, not present
  upstream. On `dbt source freshness` runs (hook gate includes `flags.WHICH == 'freshness'`),
  the results are SourceFreshnessResult objects; `upload_results` uploads ONLY the
  `source_freshness` dataset plus the `invocations` anchor (never the graph datasets - freshness
  runs at least hourly and would flood the metadata tables). One row per checked source table per
  freshness invocation into `pre__dbt__source_freshness` (status, max_loaded_at, snapshotted_at,
  age_seconds). Wired through get_dataset_content / get_table_content_values /
  get_column_name_lists / get_relation / create_metadata_tables like every other dataset.

## Syncing fixes from upstream

When pulling a fix from upstream, diff the relevant file against the `v2.10.0` tag of
`brooklyn-data/dbt_artifacts`, re-apply the Snowflake trim and namespace rewrite above, and leave
`get_relation.sql` as the convention-based version - do not reintroduce the graph lookup. If the
sync changes any dataset's columns, update `create_metadata_tables.sql` in lockstep (see "Local
additions" above).
