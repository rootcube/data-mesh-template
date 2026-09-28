---
icon: material/database-plus
---

# Adding a dbt model

A model is two files: the SQL in its layer and domain folder, and the YAML with the same name in
that folder's `_conf/`. This page builds a daily intermediate model of `dbt_example` on top of
`stg__knmi__climate_hourly`, then points at the mart the project ships. The full rules live in the
[dbt style guide](../reference/dbt-style-guide.md), the layer background in
[Layer](../understand/layer.md).

## Which layer?

| Layer | Folder | Put here | May reference |
|-------|--------|----------|---------------|
| STG | `models/02_stg/<source>/` | One model per source table: casts, renames, units | `source()`, seeds |
| INT | `models/03_int/<domain>/` | Joins, aggregations, business logic, reusable blocks | `stg__`, other `int__` |
| MRT | `models/04_mrt/<domain>/` | Dimensions and facts with surrogate keys | `int__`, dims for FKs, `stg__seed__unknown` |
| EXP | `models/05_exp/<domain>/` | Published, consumer-shaped views: the project's contract with the outside | `int__`, mart models |

Each layer has its own schema, personal to you in dev and shared in the other environments;
`dbt_common.generate_schema_name` does that translation and you never write a schema by hand.
Model, seed and source names are fixed by [Naming](../reference/naming.md).

!!! danger "Reference only the layer below"
    STG never refs INT, MRT never refs EXP, and nobody reads `source()` except STG. A shortcut is
    quicker today and confusing forever; add the missing model in the right layer instead.

## The `_conf` rule

```
dbt/dbt_example/models/03_int/weather/
├── _conf/
│   └── int__weather__station_day.yml   # always here, same stem as the SQL
└── int__weather__station_day.sql
```

Never put YAML next to SQL. Every model has its YAML with a description, column descriptions with
`data_type`, and named tests; the pre-commit `check-yaml` hook runs with `--unsafe` because dbt
YAML may carry Jinja.

## Worked example: a daily model per station

The staged KNMI data is one row per station per hour. A daily summary per station is a natural
next INT model beside the shipped `int__weather__knmi_measurement`: `int__weather__station_day`,
domain `weather`. The `unique_key` below documents the grain; a `table` materialization rebuilds
in full, so dbt only acts on it once the model turns `incremental`.

```sql title="dbt/dbt_example/models/03_int/weather/int__weather__station_day.sql (new file)"
{{
    config(
        materialized='table',
        unique_key=['station_code', 'observation_date']
    )
}}

-- One row per station per day, aggregated from the hourly observations. `observed_at` is the
-- end of the hour, so hour 24 of a day carries the next day's midnight; shifting back one hour
-- puts every observation on the day it belongs to.
WITH cte_observation AS (

  SELECT
    src.station_code
  , CAST(DATEADD('hour', -1, src.observed_at) AS DATE) AS observation_date
  , src.temperature_celsius
  , src.wind_speed_ms
  , src.precipitation_mm
  FROM
    {{ ref('stg__knmi__climate_hourly') }} AS src

)

SELECT
  obs.station_code
, obs.observation_date
, COUNT(1)                     AS observation_count
, AVG(obs.temperature_celsius) AS temperature_celsius_avg
, MIN(obs.temperature_celsius) AS temperature_celsius_min
, MAX(obs.temperature_celsius) AS temperature_celsius_max
, AVG(obs.wind_speed_ms)       AS wind_speed_ms_avg
, SUM(obs.precipitation_mm)    AS precipitation_mm_sum
FROM
  cte_observation AS obs
GROUP BY
  obs.station_code
, obs.observation_date
```

That is the [SQL style](../reference/sql-style.md) in one screen: config block first, a `cte_` CTE
per input, every table aliased and every column qualified, leading commas, `CAST()` rather than
`::`, explicit `GROUP BY` columns. `just fmt` runs `sqlfluff fix` and handles most of the
alignment for you.

The YAML mirrors the staging model's: a description, `data_type` on every column, and every test
named `<model>__<test>` or `<model>__<column>__<test>` so failures read well in the terminal and
in `_TMP`.

```yaml title="dbt/dbt_example/models/03_int/weather/_conf/int__weather__station_day.yml (new file)"
version: 2

models:
  - name: int__weather__station_day
    description: Daily weather per KNMI station, aggregated from the hourly observations.

    data_tests:
      - dbt_common.has_data:
          name: int__weather__station_day__has_data

      - dbt_utils.unique_combination_of_columns:
          name: int__weather__station_day__station_code__observation_date__unique
          arguments:
            combination_of_columns: [station_code, observation_date]

    columns:
      - name: station_code
        description: KNMI station number.
        data_type: integer
        data_tests:
          - not_null:
              name: int__weather__station_day__station_code__not_null

      - name: observation_date
        description: The day the observations belong to.
        data_type: date
        data_tests:
          - not_null:
              name: int__weather__station_day__observation_date__not_null

      - name: observation_count
        description: Number of hourly observations that day (24 for a complete day).
        data_type: integer
        data_tests:
          - not_null:
              name: int__weather__station_day__observation_count__not_null

      - name: temperature_celsius_avg
        description: Mean air temperature over the day.
        data_type: number

      - name: temperature_celsius_min
        description: Lowest hourly temperature of the day.
        data_type: number

      - name: temperature_celsius_max
        description: Highest hourly temperature of the day.
        data_type: number

      - name: wind_speed_ms_avg
        description: Mean hourly wind speed in m/s.
        data_type: number

      - name: precipitation_mm_sum
        description: Total precipitation in mm.
        data_type: number
        data_tests:
          - dbt_common.not_negative:
              name: int__weather__station_day__precipitation_mm_sum__not_negative
```

Tests available out of the box: dbt's `not_null`, `unique`, `accepted_values` and
`relationships`; everything in `dbt_utils` (`unique_combination_of_columns`, `expression_is_true`,
`accepted_range`, ...), which `packages.yml` installs; and the four generics from `dbt_common`
(`has_data`, `rows_expected`, `not_empty`, `not_negative`), called with the `dbt_common.` prefix.
Generic tests take their parameters under `arguments:`. The grain gets a uniqueness test, keys get
`not_null`, every model gets `has_data`.

## Build it

```bash
just dbt build --select int__weather__station_day       # the model and its tests
just dbt build --select +int__weather__station_day      # with everything upstream
just dbt ls --select tag:layer=int                      # what is in the layer now
```

`just dbt` runs from `dbt/dbt_example` with `DBT_PROFILES_DIR` set; the target follows
`ENVIRONMENT` in `.env`. The run opens with the run-info banner and closes with the summary, and a
failing test leaves its rows in your `_TMP` schema. `03_int` is configured as `table` with
`+schema: int`, so the result is `DBT_<USERNAME>_INT.INT__WEATHER__STATION_DAY` in
`DB_EXAMPLE_DEV`.

Lint before handing over:

```bash
just sqlfluff lint models
just fmt
```

sqlfluff uses the dbt templater with the `dummy` target (see `dbt/.sqlfluff`, shared by every
project), so it renders `ref()` and `source()` without a connection.

## From INT to a mart

The next layer turns an INT model into a fact. `dbt_example` ships the pattern for the hourly
observations in `models/04_mrt/weather/`; read those files next to `dbt_common`'s dimensions:

- The first column is a surrogate key named `id_<model>`. `dim__common__calendar` uses the
  `YYYYMMDD` integer (`date_simple`); `dim__weather__knmi_station` uses `SHA1` of the station
  code; `fct__weather__knmi_measurement` uses `dbt_utils.generate_surrogate_key` over its grain.
- Dimensions end with `UNION ALL` on `stg__seed__unknown`, so facts can point at the unknown
  member (`-1`, `-2`, `-3`) instead of `NULL`: `COALESCE(stn.id_dim__weather__knmi_station, '-2')`.
- Facts carry the dimension keys they join to, plus computed keys for the common dimensions:
  `CAST(TO_CHAR(hour_start_at, 'YYYYMMDD') AS INTEGER) AS id_dim__common__calendar`, each with a
  `relationships` test (`severity: warn`). A `fct__weather__station_day` on top of the daily model
  would do the same with `observation_date`.

A published view in `models/05_exp/<domain>/` (`exp__weather__station_weather`) then joins the star
back into the flat shape a consumer wants, and `exposures/weather_dashboard.yml` names that
consumer.

## Where Dagster comes in

Nothing to do. `dagster dev` re-parses the project when it loads the `dbt_example` location, so
after `just start` (or a reload of the location in the running UI) the new model shows up as
`dbt_example/models/03_int/weather/int__weather__station_day` (group
`dbt_example/models/03_int/weather`), downstream of
`dbt_example/models/02_stg/knmi/stg__knmi__climate_hourly`. Materializing it runs `dbt build` for
that selection.

`just validate` does not parse dbt. It reads the manifest the last `dbt parse` wrote, which
`just init` and `just check` run for you; after editing models outside those, run
`just dbt-all parse --target dummy` first.

## Before you hand it over

`just dbt build --select <model>` passes, `just sqlfluff lint models` is clean, `just validate`
still loads the location, and the model itself holds up:

- SQL in `models/<layer>/<domain>/`, YAML with the same stem in `_conf/`.
- The name matches the layer pattern, and the model references only the layer below.
- The grain has a uniqueness test, keys have `not_null`, the model has `has_data`, every test is
  named.
- Every column has a description and a `data_type`.
