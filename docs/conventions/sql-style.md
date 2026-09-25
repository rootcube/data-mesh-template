---
icon: material/code-tags
---

# SQL style

All SQL is Snowflake dialect, written as dbt models with Jinja, and linted by sqlfluff with the
dbt templater. The configuration in `dbt/.sqlfluff` (shared by every project under `dbt/`) is the
machine-readable truth; this page explains the rules you will actually bump into.

## The setup

| Setting | Value |
|---|---|
| Dialect | `snowflake` |
| Templater | `dbt`, rendering through the project with the `dummy` target (an in-memory DuckDB from `dbt/profiles.yml`, so no Snowflake credentials are needed; SQL is rendered, never executed) |
| Line length | `max_line_length = 120`, but rule LT05 is not in the enabled rule list, so long lines are a convention, not a lint failure |
| Indent | 2 spaces, indented `JOIN`s, `ON` contents not indented further |
| Commas | Leading, aligned with the following clause (`leading:align-following`) |
| Aliases | Explicit `AS` for tables and columns; the `AS` of the `SELECT` list aligned within the clause |
| Parallelism | All CPU cores (`processes = -1`) |
| Scope | `models/` of the project you run it from; `target/` and `packages/` are ignored via `dbt/.sqlfluffignore` |

The rule set is an explicit allowlist (`rules = ...` in `dbt/.sqlfluff`): aliasing (`AL`),
ambiguity (`AM`), capitalisation (`CP`), conventions (`CV`), Jinja (`JJ`), layout (`LT`),
references (`RF`) and structure (`ST`). Anything not listed there is not checked.

## Formatting basics

**Capitalisation.** Keywords, functions, types and literals like `NULL`/`TRUE` in UPPER (CP01,
CP03, CP05, CP04); identifiers (tables, columns, CTEs, aliases) in lower (CP02):

```sql
SELECT COALESCE(src.station_code, -1) AS station_code
FROM {{ ref('stg__knmi__climate_hourly') }} AS src
WHERE src.observed_at IS NOT NULL
```

**Leading commas, 2-space indent, aligned `AS`, every column qualified.** From the real staging
model:

```sql title="dbt/dbt_example/models/02_stg/knmi/stg__knmi__climate_hourly.sql (excerpt)"
SELECT
  CAST(obs.station_code AS INTEGER)                                                         AS station_code
, DATEADD('hour', CAST(obs.hour AS INTEGER), CAST(CAST(obs.date AS DATE) AS TIMESTAMP_NTZ)) AS observed_at
, CAST(obs.t AS INTEGER) / 10.0                                                             AS temperature_celsius
, CAST(obs.fh AS INTEGER) / 10.0                                                            AS wind_speed_ms
, CAST(obs.q AS INTEGER)                                                                    AS global_radiation_jcm2
, obs._dlt_load_id
FROM
  cte_source AS obs
```

**Joins indented under `FROM`, with explicit `AS` names** (AL01), unique per query (AL04). When
more than one table is referenced, qualify every column (RF02):

```sql title="dbt/dbt_common/models/03_int/common/int__common__calendar.sql (excerpt)"
FROM
  cte_calendar AS cal

  LEFT JOIN cte_month_label AS mlb
    ON mlb.month_nr = cal.month

  LEFT JOIN cte_weekday_label AS dlb
    ON dlb.day_nr = cal.day_of_week
```

In `ON` conditions, put the just-joined (later) table's column on the left:
`ON mlb.month_nr = cal.month`, not the reverse (ST09, `preferred_first_table_in_join_clause = later`).

## Syntax conventions

These are enabled sqlfluff rules; violations fail pre-commit and CI:

| Do | Don't | Rule |
|---|---|---|
| `CAST(x AS INTEGER)` | `x::INTEGER` | CV11 |
| `LEFT JOIN` | `RIGHT JOIN` | CV08 |
| `INNER JOIN` | bare `JOIN` | AM05 |
| `JOIN ... ON ...` | `JOIN ... USING (...)` | ST07 |
| CTEs | subqueries in `FROM` / `JOIN` | ST05 |
| `!=` | `<>` | CV01 |
| `COALESCE(x, y)` | `IFNULL` / `NVL` | CV02 |
| `COUNT(1)` | `COUNT(*)` / `COUNT(0)` | CV04 |
| `x IS NULL` / `IS NOT NULL` | `x = NULL` | CV05 |
| `'single quotes'` for literals | `"double quotes"` | CV10 |
| `UNION ALL` (or `UNION DISTINCT`) | bare `UNION` | AM02 |
| `GROUP BY col_a, col_b` | `GROUP BY 1, 2` | AM06 |
| `FROM x AS src` | `FROM x src` | AL01 |
| `expression AS name` | `expression name` | AL02 |
| A name on every computed column | an unnamed expression in `SELECT` | AL03 |

Also enabled: no unused CTEs (ST03), no `CASE` nested in `ELSE` (ST04), no `CASE` that a simpler
expression replaces (ST02), no special characters or unnecessary quoting in identifiers (RF05,
RF06), consistent `ASC`/`DESC` in `ORDER BY` (AM03), the same column count on both sides of a set
operator (AM07), and a final `SELECT` whose column count sqlfluff can determine (AM04), so list
columns explicitly at the end. The layout rules (LT01, LT02, LT04, LT06 to LT13) handle spacing,
indentation, comma position, one set operator per line, and a single newline at the end of the
file.

## Good vs bad

=== "Good"

    ```sql
    WITH cte_warm_hours AS (
      SELECT
        obs.station_code
      , obs.observed_at
      , obs.temperature_celsius
      FROM
        {{ ref('stg__knmi__climate_hourly') }} AS obs
      WHERE obs.temperature_celsius > 25
    )

    SELECT
      hrs.station_code
    , hrs.observed_at
    , cal.year_nr
    FROM
      cte_warm_hours AS hrs

      LEFT JOIN {{ ref('dim__common__calendar') }} AS cal
        ON cal.date = CAST(hrs.observed_at AS DATE)
    ```

=== "Bad"

    ```sql
    select hrs.station_code,                               -- lowercase keywords, trailing commas
        hrs.observed_at::date,                             -- :: cast, no name for the expression
        cal.year_nr
    from (select * from {{ ref('stg__knmi__climate_hourly') }}
          where temperature_celsius > 25) hrs              -- subquery, table name without AS
    right join {{ ref('dim__common__calendar') }} cal     -- RIGHT JOIN, no AS
        on hrs.observed_at::date = cal.date                -- earlier table first
    ```

## CTEs

- Prefix CTEs with `cte_`, as the real models do (`cte_source` in the staging model,
  `cte_date_range`, `cte_month_label`, `cte_calendar` in `dbt_common`). Not every model needs
  CTEs; a seed staging model is often one `SELECT`.
- One logical unit of work per CTE, named as verbosely as needed.
- The second and later CTEs start with a leading comma on their own line, and a blank line follows
  every closing bracket (LT04, LT08).
- Comment CTEs with confusing logic, above the CTE.
- A CTE duplicated across models should become its own model.

```sql
WITH cte_source AS (
  SELECT
    src.station_code
  , src.observed_at
  , src.temperature_celsius
  FROM
    {{ ref('stg__knmi__climate_hourly') }} AS src
)

, cte_filtered AS (
  SELECT
    obs.station_code
  , obs.observed_at
  , obs.temperature_celsius
  FROM
    cte_source AS obs
  WHERE obs.temperature_celsius IS NOT NULL
)

SELECT
  flt.station_code
, flt.observed_at
, flt.temperature_celsius
FROM
  cte_filtered AS flt
```

## Jinja

- Spaces inside curly braces: `{{ ref('model') }}`, not `{{ref('model')}}` (JJ01).
- Use `{%-` / `-%}` and `{#-` / `-#}` for whitespace control in block tags and comments.
- Multi-line `config()` blocks use 4-space indentation inside the outer `{{ }}`.
- Keep inline Jinja short; complex logic belongs in a macro.
- `ignore_templated_areas = True`: sqlfluff skips whatever a macro renders, so a macro's output is
  not linted, only the model around it.

Common patterns, all from this repo:

```sql
{{ ref('stg__knmi__climate_hourly') }}                      -- reference a model
{{ source('knmi', 'climate_hourly') }}                      -- reference a source table
{{ ref('dim__common__calendar') }}                         -- a shared dbt_common model
{{ dbt_common.utc_now() }}                                  -- a shared macro
{{ dbt_utils.generate_surrogate_key(['station_code']) }}    -- dbt_utils
```

When a Jinja block genuinely cannot be made lint-clean, fence it:

```sql
-- noqa: disable=all
{{ complex_jinja_block }}
-- noqa: enable=all
```

## Column naming

| Type | Pattern | Example |
|---|---|---|
| Surrogate key (dim) | `id_dim__<domain>__<entity>` | `id_dim__common__calendar` |
| Surrogate key (fct) | `id_fct__<domain>__<entity>` | `id_fct__weather__knmi_measurement` |
| Foreign key to a dimension | `id_dim__<domain>__<entity>` | `id_dim__common__calendar` |
| Boolean | `is_<condition>` / `has_<thing>` | `is_holiday`, `is_weekend` |
| Timestamp | `<event>_at` | `observed_at` |
| Date | `<event>_date` | `first_date_of_month` |
| Measure with a unit | `<measure>_<unit>` | `temperature_celsius`, `wind_speed_ms`, `precipitation_mm` |
| dlt bookkeeping | `_dlt_<name>` | `_dlt_load_id` |

The full per-layer naming rules live on the [naming page](naming.md).

## Running the linter

=== "just"

    ```bash
    just fmt                                      # sqlfluff fix on dbt_example/models (+ ruff)
    just lint                                     # sqlfluff lint on dbt_example/models (+ ruff), no changes
    just sqlfluff lint models/02_stg              # lint a specific path (runs from dbt/dbt_example)
    just sqlfluff fix models/02_stg               # auto-fix a specific path
    just project=dbt_other sqlfluff lint models   # another project under dbt/
    ```

=== "sqlfluff directly"

    ```bash
    cd dbt/dbt_example
    uv run sqlfluff lint models
    uv run sqlfluff fix models
    ```

!!! info "Run it from inside a project, with the packages installed"
    The dbt templater takes `dbt_project.yml` from the working directory and `profiles.yml` from
    `DBT_PROFILES_DIR` (the justfile and `.envrc` point it at `dbt/`), so run sqlfluff from a
    project directory, which is what `just sqlfluff` does; sqlfluff finds the shared
    `dbt/.sqlfluff` by walking up from there. It also needs the dbt packages: `just init`
    installs them, `just dbt-all deps` repeats it. A "dbt templater error" almost always means
    one of those two.

Enforcement happens twice more after your editor:

1. **Pre-commit** runs `sqlfluff lint models` in `dbt/dbt_example` whenever a model under it
   changes. It lints, it does not fix, so run `just fmt` first.
2. **CI** runs the same lint in the `dbt-and-dagster` job on every pull request.

## Related pages

- [dbt style guide](dbt-style-guide.md): model design, layers, tests (this page is formatting only)
- [Naming](naming.md): model and column naming per layer
- [Adding dbt models](../development/adding-dbt-models.md)
- [AI agent guide: SQL](../ai-agents/sql.md)
