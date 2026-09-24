---
icon: material/database-plus
---

# Adding a dbt model

A model is two files: the SQL in its layer and domain folder, and the YAML with the same name in
that folder's `_conf/`. This page builds the first intermediate model of `dbt_example` on top of
`stg__knmi__climate_hourly`, then sketches the step to a mart. The full rules are in the
[dbt style guide](../conventions/dbt-style-guide.md); the layer background on
[Layers](../architecture/layers.md).

## Which layer?

| Layer | Folder | Schema | Put here | May reference |
|-------|--------|--------|----------|---------------|
| STG | `models/02_stg/<source>/` | `_STG` | One model per source table: casts, renames, units | `source()`, seeds |
| INT | `models/03_int/<domain>/` | `_INT` | Joins, aggregations, business logic, reusable blocks | `stg__`, other `int__` |
| MRT | `models/04_mrt/<domain>/` | `_MRT` | Dimensions and facts with surrogate keys | `int__`, dims for FKs, `stg__seed__unknown` |
| EXP | `models/05_exp/<domain>/` | `_EXP` | Published, consumer-shaped views: the project's contract with the outside | `int__`, mart models |

The schema column is the provisioned name in `tst`, `acc` and `prd`. In dev you build into your
personal copies, `DBT_<NAME>_STG` and so on, in the shared `DB_<PROJECT>_DEV`;
`dbt_common.generate_schema_name` does the renaming.

!!! danger "Reference only the layer below"
    STG never refs INT, MRT never refs EXP, and nobody reads `source()` except STG. A shortcut
    is quicker today and confusing forever; add the missing model in the right layer instead.

Naming encodes the layer: `stg__<source>__<entity>`, `int__<domain>__<entity>`,
`dim__|fct__|brg__|agg__<domain>__<entity>`, `exp__<domain>__<entity>`. Sources are
`src_<source>.yml`, seeds `seed_<name>`. See [Naming](../conventions/naming.md).

## The `_conf` rule

```
dbt/dbt_example/models/03_int/weather/
├── _conf/
│   └── int__weather__station_day.yml   # always here, same stem as the SQL
└── int__weather__station_day.sql
```

Never put YAML next to SQL. Every model has its YAML with a description, column descriptions
with `data_type`, and named tests; the pre-commit `check-yaml` hook runs with `--unsafe` because
dbt YAML may carry Jinja.

## Worked example: a daily model per station

The staged KNMI data is one row per station per hour. A daily summary per station is a natural
first INT model: `int__weather__station_day`, domain `weather`.

```sql title="dbt/dbt_example/models/03_int/weather/int__weather__station_day.sql"
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

What the style guide wants, visible here: a config block first, a `cte_` CTE per input, every
table named with `AS` and every column qualified, leading commas, two-space indent, uppercase
keywords and functions, lowercase identifiers, `CAST()` rather than `::`, `COUNT(1)`, explicit
`GROUP BY` columns, aligned `AS` columns. `just fmt` runs `sqlfluff fix` and takes care of most
of the alignment.

The YAML, mirroring the staging model's: a description, `data_type` on every column, and every
test named `<model>__<test>` or `<model>__<column>__<test>` so failures read well in the
terminal and in `_TMP`.

```yaml title="dbt/dbt_example/models/03_int/weather/_conf/int__weather__station_day.yml"
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
`relationships`; everything in `dbt_utils` (`unique_combination_of_columns`,
`expression_is_true`, `accepted_range`, ...), which `packages.yml` installs; and the four
generics from `dbt_common` (`has_data`, `rows_expected`, `not_empty`, `not_negative`), called
with the `dbt_common.` prefix. Generic tests take their parameters under `arguments:`. The grain
gets a uniqueness test, keys get `not_null`, every model gets `has_data`.

## Build it

```bash
just dbt build --select int__weather__station_day       # the model and its tests
just dbt build --select +int__weather__station_day      # with everything upstream
just dbt ls --select tag:layer=int                       # what is in the layer now
```

`just dbt` runs from `dbt/dbt_example` with `DBT_PROFILES_DIR` set; the target follows
`ENVIRONMENT` in `.env` (`dev`). The run starts with the run-info banner and ends with the
summary; a failing test leaves its rows in your `_TMP` schema. `03_int` is configured as `table`
with `+schema: int`, so the result is `DBT_<NAME>_INT.INT__WEATHER__STATION_DAY` in
`DB_EXAMPLE_DEV` (and `_INT.INT__WEATHER__STATION_DAY` once it runs in a shared environment).

Lint before handing over:

```bash
just sqlfluff lint models
just fmt
```

sqlfluff uses the dbt templater with the `dummy` target (see `dbt/.sqlfluff`, shared by every
project), so it renders `ref()` and `source()` without a connection.

## From INT to a mart

The next layer turns the daily model into a fact. The house pattern, visible in
`dbt_common`'s dimensions:

- The first column is a surrogate key named `id_<model>`. `dim__common__calendar` uses the
  `YYYYMMDD` integer (`date_simple`); `dim__common__environment` uses `SHA1(environment_code)`.
- Dimensions end with `UNION ALL` on `stg__seed__unknown`, so facts can point at the unknown
  member (`-1`, `-2`, `-3`) instead of `NULL`.
- Facts carry the dimension keys they join to. A `fct__weather__station_day` would compute
  `CAST(REPLACE(CAST(observation_date AS VARCHAR), '-', '') AS INTEGER) AS id_dim__common__calendar`
  and get a `relationships` test to `dim__common__calendar`.

Mart models live in `models/04_mrt/<domain>/`, materialize as tables, and reference INT models
plus the dimensions they key into. A published view in `models/05_exp/<domain>/`
(`exp__<domain>__<entity>`) then joins the star back into whatever flat shape a consumer or
another project wants.

## Where Dagster comes in

Nothing to do. The `dbt_example` code location re-parses the project on load, so after
`just validate` (or a reload in the UI) the new model shows up as
`dbt_example/models/03_int/weather/int__weather__station_day` (group
`dbt_example/models/03_int/weather`), downstream of
`dbt_example/models/02_stg/knmi/stg__knmi__climate_hourly`. Materializing it runs
`dbt build` for that selection.

## Checklist

- [ ] SQL in `models/<layer>/<domain>/`, YAML with the same stem in `_conf/`
- [ ] Name matches the layer pattern; references only the layer below
- [ ] Grain has a uniqueness test, keys have `not_null`, the model has `has_data`, every test is named
- [ ] Every column has a description and a `data_type`
- [ ] `just dbt build --select <model>` passes, `just sqlfluff lint models` is clean
- [ ] `just validate` still loads the location
