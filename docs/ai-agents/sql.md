---
icon: material/database-search
---

# SQL

The working loop for agents writing SQL in this repo: the rules in one line each, a template, the Jinja you will use, and the validation commands to run after every change. All SQL is Snowflake dialect, written as dbt models with Jinja, and linted by sqlfluff with the dbt templater. The rules themselves live on the canonical pages below; this page does not restate them.

## Where the rules live

| Topic | Canonical page |
|---|---|
| Formatting and syntax: capitalisation, commas, `AS` names, casting, CTE rules, Jinja, the full rule table | [SQL style](../conventions/sql-style.md) |
| Model design: layers and reference rules, `_conf/` placement, required config, tests, docs, seeds, macros | [dbt style guide](../conventions/dbt-style-guide.md) |
| Model, column, test and source naming per layer | [Naming](../conventions/naming.md) |
| The dbt workflow around the SQL (projects, layers, environments, running models) | [dbt](dbt.md) and [adding a dbt model](../development/adding-dbt-models.md) |

Machine-readable truth: `dbt/.sqlfluff` (dialect, templater, rules, layout) and `dbt/.sqlfluffignore` (`target/` and `packages/` are excluded), shared by every project under `dbt/`.

!!! tip "Orientation in one line each"
    Keywords, functions, literals and types UPPER, identifiers lower; leading commas, 2-space indent, 120-character lines; every table and column named explicitly with `AS`; `CAST()` never `::`; `LEFT JOIN` never `RIGHT JOIN`; CTEs (`cte_` prefix), never subqueries; single-quoted literals; `COUNT(1)` over `COUNT(*)`; explicit `GROUP BY` and `ORDER BY` columns; in an `ON` condition the just-joined table's column goes on the left. Never spell out a schema or database: `source()`, `ref()` and `generate_schema_name` resolve them per environment. Details and the complete rule table: [SQL style](../conventions/sql-style.md).

## Template

The staging model that exists, `dbt/dbt_example/models/02_stg/knmi/stg__knmi__climate_hourly.sql`, is the shape to copy: config block first, one `cte_` CTE per step, every relation named with `AS`, `AS` names aligned, a final `SELECT` that names every column. In full:

```sql
{{
    config(
        materialized='table',
        unique_key=['station_code', 'observed_at']
    )
}}

-- KNMI hourly observations, typed and converted to SI-ish units. The API's hour 1..24 is the
-- hour *ending* at that time, so hour 24 of 2024-01-01 becomes 2024-01-02 00:00.
WITH cte_source AS (

  SELECT
    src.station_code
  , src.date
  , src.hour
  , src.t
  , src.fh
  , src.rh
  , src.q
  , src.u
  , src._dlt_load_id
  FROM
    {{ source('knmi', 'climate_hourly') }} AS src

)

SELECT
  CAST(obs.station_code AS INTEGER)                                                         AS station_code
, DATEADD('hour', CAST(obs.hour AS INTEGER), CAST(CAST(obs.date AS DATE) AS TIMESTAMP_NTZ)) AS observed_at
, CAST(obs.t AS INTEGER) / 10.0                                                             AS temperature_celsius
, CAST(obs.fh AS INTEGER) / 10.0                                                            AS wind_speed_ms
, CASE
    WHEN CAST(obs.rh AS INTEGER) = -1 THEN 0.05
    ELSE CAST(obs.rh AS INTEGER) / 10.0
  END                                                                                       AS precipitation_mm
, CAST(obs.q AS INTEGER)                                                                    AS global_radiation_jcm2
, CAST(obs.u AS INTEGER)                                                                    AS relative_humidity_pct
, obs._dlt_load_id
FROM
  cte_source AS obs
```

A model with a join follows the same layout; `dbt/dbt_common/models/04_mrt/common/dim__common__environment.sql` (two `SELECT`s over `ref()`s with a `UNION ALL`) and `int__common__calendar.sql` (a `cte_` chain) are the in-repo examples for marts and multi-CTE models. Which config keys each layer needs: [dbt style guide](../conventions/dbt-style-guide.md).

## Jinja you will use

| Jinja | Meaning |
|---|---|
| `{{ source('knmi', 'climate_hourly') }}` | A dlt-loaded table declared in `sources/src_knmi.yml` (`identifier: knmi__climate_hourly` in the source layer); only staging models use `source()` |
| `{{ ref('stg__knmi__climate_hourly') }}` | Another model; reference only the layer directly below |
| `{{ dbt_common.utc_today() }}`, `{{ dbt_common.utc_now() }}` | Session-timezone-proof date and timestamp; package macros are always namespaced |
| `{{ config(...) }}` | First thing in the file; `materialized`, `unique_key`, `tags`, hooks |
| `{{ this }}` | The model's own relation, for post-hooks such as `dbt_common.search_optimization(this)` |

There are no incremental models in the repo yet. The staging table rebuilds fully; deduplication over the overlapping fetch window is dlt's job (`merge` with a primary key), so staging never needs it.

## After making changes

Always run at least steps 1 and 2 before presenting changes.

### 1. Fix formatting

=== "just"

    ```bash
    just sqlfluff fix models/02_stg/knmi   # one path
    just sqlfluff lint models              # check only, what the hook and CI run
    just fmt                               # ruff + sqlfluff fix models
    ```

=== "sqlfluff directly"

    ```bash
    cd dbt/dbt_example && uv run sqlfluff fix models
    ```

sqlfluff runs from inside the dbt project because the dbt templater resolves `dbt_project.yml` from the working directory; the `just` recipes `cd` there for you. The templater uses the `dummy` target (an in-memory DuckDB), so it never connects. A "dbt templater error" almost always means missing packages: `just dbt deps` first.

### 2. Parse and compile

Catches broken `{{ ref() }}` / `{{ source() }}` references and invalid Jinja:

```bash
just dbt parse                # never connects
just dbt compile              # renders SQL to target/compiled; needs your .env
```

For another project: `just project=dbt_x dbt parse`.

### 3. Build and look at the result

```bash
just dbt build --select stg__knmi__climate_hourly
just snowflake query "SELECT COUNT(1), MIN(observed_at), MAX(observed_at) FROM dbt_username_stg.stg__knmi__climate_hourly"
```

`dbt build` runs the model and its tests; a failed test stores its rows in the temporary layer (`<prefix>_TMP` in `dev`, `_TMP` elsewhere). Replace `dbt_username` with your own `SNOWFLAKE_SCHEMA` prefix.

### 4. Full validation

```bash
just validate        # Dagster loads the dbt project, so a dbt error surfaces here too
just pre-commit      # all hooks
```

## Key files

| What | Where |
|---|---|
| sqlfluff config | `dbt/.sqlfluff`, `dbt/.sqlfluffignore` (shared by every project) |
| Model examples | `dbt/dbt_example/models/02_stg/knmi/`, `dbt/dbt_common/models/` |
| Macros | `dbt/dbt_common/macros/` (shared), `dbt/dbt_example/macros/` (project, empty so far) |
| Generic tests | `dbt/dbt_common/tests/generic/` (`has_data`, `rows_expected`, `not_empty`, `not_negative`) |
| Sources | `dbt/dbt_example/sources/src_knmi.yml` |

## Related pages

- [SQL style](../conventions/sql-style.md): the formatting and syntax rules this page assumes
- [dbt style guide](../conventions/dbt-style-guide.md): model design, layers, tests
- [Naming](../conventions/naming.md): model, column and source naming in one place
- [dbt](dbt.md): the agent guide for the dbt workflow around the SQL
- [Adding a dbt model](../development/adding-dbt-models.md): step-by-step workflow
