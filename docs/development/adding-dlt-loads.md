---
icon: material/database-import
---

# Adding a dlt load

A new source is one folder under `dlt_pipelines/pipelines/ingest/`, shaped exactly like `knmi`.
Nothing registers it: the standalone runner discovers packages, the Dagster component tree
discovers `defs.yaml` files, and `job_dlt_ingest_all` selects by key prefix. This page adds a
second REST source end to end, up to the dbt staging model that reads it. Background:
[Ingestion](../architecture/ingestion.md).

Every load lands in the **source layer** of the project database: schema `_SRC`, or your
personal `<SNOWFLAKE_SCHEMA>_SRC` in dev (`DBT_<NAME>_SRC`), as a table named
`<source>__<entity>`. The schema comes from `source_dataset()` in
`dlt_pipelines/utils/destination.py`; you never spell it out.

!!! info "The example is made up"
    The pages below use a fictional air-quality API called `airquality` with one entity,
    `measurement_hourly`. The URL, parameters and field names are placeholders; swap in the
    real endpoint you are ingesting. The KNMI files next to it are the reference for every
    detail.

## 1. Create the folder

```
dlt_pipelines/pipelines/ingest/airquality/
├── __init__.py       # empty
├── constants.py
├── source.py
├── pipelines.py
└── defs.yaml
```

The folder name is the source name. It becomes the first half of the table name
(`airquality__measurement_hourly`), part of the asset key (`dlt/ingest/airquality/...`) and the
argument of `just dlt run airquality`. Keep it short, lowercase, letters only.

## 2. constants.py

Everything that is a setting rather than logic: the URL, what to fetch, how far back. Sizing
comments help the next reader.

```python title="dlt_pipelines/pipelines/ingest/airquality/constants.py"
"""Constants for the airquality ingest pipeline."""

AIRQUALITY_MEASUREMENTS_URL = "https://example.org/api/v1/measurements"

# A handful of stations, keeping volumes small (3 stations x 24 hours x DAYS_BACK days).
STATIONS: dict[str, str] = {
    "NL10404": "Den Haag",
    "NL10636": "Utrecht",
    "NL10937": "Groningen",
}

DAYS_BACK = 7
```

## 3. source.py

The HTTP calls, as a generator of plain dicts. Use `dlt.sources.helpers.requests`: it is a
`requests` session with retries built in. Yield records exactly as the API returns them; renames
and casts belong in the dbt staging model.

```python title="dlt_pipelines/pipelines/ingest/airquality/source.py"
"""Fetch hourly measurements from the airquality API."""

import logging
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

from dlt.sources.helpers import requests as dlt_requests

from dlt_pipelines.pipelines.ingest.airquality.constants import AIRQUALITY_MEASUREMENTS_URL, DAYS_BACK, STATIONS

LOGGER = logging.getLogger(__name__)


def fetch_measurements(days_back: int = DAYS_BACK) -> Iterator[dict]:
    """Yield one dict per station per hour for the last `days_back` days."""
    end = datetime.now(tz=UTC)
    start = end - timedelta(days=days_back)

    total = 0
    for station_code in STATIONS:
        LOGGER.info("airquality: fetching %s for %s..%s", station_code, start.date(), end.date())
        response = dlt_requests.get(
            AIRQUALITY_MEASUREMENTS_URL,
            params={"station": station_code, "start": start.isoformat(), "end": end.isoformat()},
            timeout=120,
        )
        response.raise_for_status()
        records = response.json()
        total += len(records)
        yield from records
    LOGGER.info("airquality: fetched %d rows", total)
```

Full type hints on every function; `just typecheck` runs `ty` over `dlt_pipelines/`.

## 4. pipelines.py

The dlt objects. Two module-level names are the contract: `source` and `pipeline`. Copy the
KNMI file and change the names, the primary key and the fetch function.

```python title="dlt_pipelines/pipelines/ingest/airquality/pipelines.py"
"""dlt pipeline: airquality hourly measurements -> Snowflake source layer (airquality__measurement_hourly).

Every source lands in the project's source layer (`_SRC`, or your personal `<PREFIX>_SRC` in dev)
as `<source>__<entity>`. `merge` with a primary key keeps the table free of duplicates when the
pipeline runs daily over an overlapping window; `just dlt run airquality --full-refresh` reloads it.
"""

from collections.abc import Iterator

import dlt

from dlt_pipelines.pipelines.ingest.airquality.source import fetch_measurements
from dlt_pipelines.utils.destination import snowflake_destination, source_dataset

SOURCE = "airquality"
ENTITY = "measurement_hourly"


@dlt.source(name=f"{SOURCE}__{ENTITY}", max_table_nesting=0)
def airquality_source() -> Iterator[dlt.sources.DltResource]:
    """Hourly air-quality measurements for a handful of stations, last 7 days."""

    @dlt.resource(
        name=ENTITY,
        table_name=f"{SOURCE}__{ENTITY}",
        write_disposition="merge",
        primary_key=["station_code", "measured_at"],
    )
    def measurement_hourly() -> Iterator[dict]:
        yield from fetch_measurements()

    yield measurement_hourly()


source = airquality_source()

pipeline = dlt.pipeline(
    pipeline_name=f"ingest_{SOURCE}",
    destination=snowflake_destination(),
    dataset_name=source_dataset(),
)
```

Choices to make:

`primary_key`
:   The grain of one row, in the API's own field names. With `write_disposition="merge"`,
    re-running over an overlapping window upserts instead of duplicating.

`write_disposition`
:   `merge` is the default choice here. `replace` rewrites the table every run (fine for small
    reference-style endpoints); `append` only adds rows and needs a window that never overlaps.

`table_name`
:   Always `<source>__<entity>`. The resource name stays the bare entity (it becomes the last
    segment of the asset key); the table name carries the source prefix because every source of
    the project shares one `_SRC` schema.

More resources
:   One `@dlt.resource` per endpoint, all yielded from the same source function, each with its
    own `table_name`. Each becomes its own table and its own Dagster asset.

`snowflake_destination()` and `source_dataset()`
:   Always these two. They read `SNOWFLAKE_*` and `ENVIRONMENT` from `.env` through
    `SnowflakeSettings`, so there is nothing to configure per source. Credentials are only
    checked when the pipeline runs, which is why the module imports cleanly without a `.env`.

## 5. defs.yaml

The Dagster side, again a copy with the source name changed in two places:

```yaml title="dlt_pipelines/pipelines/ingest/airquality/defs.yaml"
type: dagster_dlt.DltLoadCollectionComponent

attributes:
  loads:
    - pipeline: .pipelines.pipeline
      source: .pipelines.source
      translation:
        key: '{{ resource.name | lower }}'
        key_prefix: '{{ ["dlt", "ingest", "airquality"] }}'
        group_name: dlt/ingest/airquality
        kinds:
          - dlt
          - snowflake
        # The API is the start of the graph: no placeholder upstream asset per resource.
        deps: []
```

`.pipelines.pipeline` is relative to the folder the file is in. The resulting asset is
`dlt/ingest/airquality/measurement_hourly` in group `dlt/ingest/airquality`. `deps: []` matters:
without it the component invents an upstream placeholder asset per resource.

## 6. Run it outside Dagster

```bash
just dlt list                   # airquality now listed next to knmi
just dlt run airquality
just snowflake query "SELECT COUNT(1) FROM DBT_<NAME>_SRC.airquality__measurement_hourly"
```

`just snowflake check` prints your layer schemas if you are unsure of the prefix. In dev the
schema is created on first load. `RUNTIME__LOG_LEVEL=INFO` in `.env` shows the extract,
normalize and load steps. Something wrong with the data? `just dlt run airquality --full-refresh`
drops the source's tables and state and loads again.

## 7. Run it in Dagster

```bash
just validate    # the dlt location loads with the new defs.yaml
just start
```

In the UI, the asset `measurement_hourly` sits in group `dlt/ingest/airquality`; **Materialize**
runs the same `pipeline.run(source)`. It is also part of `job_dlt_ingest_all`, without any
change to the job. `just dagster asset list -m orchestrator.locations.dlt.definitions` prints
both keys from the terminal.

## 8. Expose it to dbt

Two files in the dbt project that owns the source (`dbt/dbt_example` here). First the source,
with the Dagster asset key so the lineage crosses code locations. The `schema` line is the one
place the layer rule is spelled out by hand, because source YAML can use `env_var` but not
macros; copy it exactly from `src_knmi.yml`.

```yaml title="dbt/dbt_example/sources/src_airquality.yml"
version: 2

sources:
  - name: airquality
    description: >
      Hourly air-quality measurements, loaded into the source layer by the dlt pipeline
      `ingest_airquality` (dlt_pipelines/pipelines/ingest/airquality). Field names as the API
      returns them, lowercased by dlt.
    # The source layer: _SRC, or <SNOWFLAKE_SCHEMA>_SRC in dev (same rule as dbt_common's
    # generate_schema_name; source YAML can only use env_var, not macros).
    schema: "{{ env_var('SNOWFLAKE_SCHEMA', '') if env_var('ENVIRONMENT', 'dev') in ['dev', 'dummy'] else '' }}_SRC"
    tables:
      - name: measurement_hourly
        identifier: airquality__measurement_hourly
        description: One row per station per hour.
        config:
          meta:
            dagster:
              # Same key as the dlt asset, so the Dagster lineage runs dlt -> dbt.
              asset_key: ["dlt", "ingest", "airquality", "measurement_hourly"]
        columns:
          - name: station_code
            description: Station identifier.
          - name: measured_at
            description: Start of the measurement hour.
          - name: pm25
            description: Fine particulate matter (PM2.5) in ug/m3.
          - name: no2
            description: Nitrogen dioxide in ug/m3.
          - name: _dlt_load_id
            description: dlt load package that wrote the row.
```

`name` is the entity (what `source('airquality', 'measurement_hourly')` refers to);
`identifier` is the physical table, `<source>__<entity>`.

Then the staging model, in the house SQL style (a `cte_` CTE, explicit table names with `AS`,
leading commas, two-space indent, uppercase keywords, `CAST()`), plus its YAML in `_conf/`:

```sql title="dbt/dbt_example/models/02_stg/airquality/stg__airquality__measurement_hourly.sql"
{{
    config(
        materialized='table',
        unique_key=['station_code', 'measured_at']
    )
}}

-- Air-quality measurements, typed. One row per station per hour.
WITH cte_source AS (

  SELECT
    src.station_code
  , src.measured_at
  , src.pm25
  , src.no2
  , src._dlt_load_id
  FROM
    {{ source('airquality', 'measurement_hourly') }} AS src

)

SELECT
  CAST(obs.station_code AS VARCHAR)      AS station_code
, CAST(obs.measured_at AS TIMESTAMP_NTZ) AS measured_at
, CAST(obs.pm25 AS FLOAT)                AS pm25_ugm3
, CAST(obs.no2 AS FLOAT)                 AS no2_ugm3
, obs._dlt_load_id
FROM
  cte_source AS obs
```

```yaml title="dbt/dbt_example/models/02_stg/airquality/_conf/stg__airquality__measurement_hourly.yml"
version: 2

models:
  - name: stg__airquality__measurement_hourly
    description: Typed air-quality measurements, one row per station per hour.

    data_tests:
      - dbt_common.has_data:
          name: stg__airquality__measurement_hourly__has_data

      - dbt_utils.unique_combination_of_columns:
          name: stg__airquality__measurement_hourly__station_code__measured_at__unique
          arguments:
            combination_of_columns: [station_code, measured_at]

    columns:
      - name: station_code
        description: Station identifier.
        data_type: varchar
        data_tests:
          - not_null:
              name: stg__airquality__measurement_hourly__station_code__not_null

      - name: measured_at
        description: Start of the measurement hour (timestamp, no timezone).
        data_type: timestamp_ntz
        data_tests:
          - not_null:
              name: stg__airquality__measurement_hourly__measured_at__not_null

      - name: pm25_ugm3
        description: Fine particulate matter (PM2.5) in ug/m3.
        data_type: float
        data_tests:
          - dbt_common.not_negative:
              name: stg__airquality__measurement_hourly__pm25_ugm3__not_negative

      - name: no2_ugm3
        description: Nitrogen dioxide in ug/m3.
        data_type: float

      - name: _dlt_load_id
        description: dlt load package that wrote the source row.
        data_type: varchar
```

Build and lint:

```bash
just dbt build --select stg__airquality__measurement_hourly
just sqlfluff lint models
```

The model lands as `DBT_<NAME>_STG.STG__AIRQUALITY__MEASUREMENT_HOURLY` in your dev database.
After `just validate` (or a reload of the `dbt_example` location in the UI), the graph shows
`dlt/ingest/airquality/measurement_hourly` feeding
`dbt_example/models/02_stg/airquality/stg__airquality__measurement_hourly`.
From here on it is [Adding a dbt model](adding-dbt-models.md).

## 9. Validate

```bash
just fmt
just typecheck
just test
just validate
```

`tests/test_dlt_pipelines.py` shows how a source is asserted to be discoverable
(`discover()["knmi"]`); add the same line for the new one if you like. Tests stay offline: no
test calls the API or Snowflake.

## Checklist

- [ ] Folder under `dlt_pipelines/pipelines/ingest/<source>/` with `__init__.py`, `constants.py`, `source.py`, `pipelines.py`, `defs.yaml`
- [ ] `pipelines.py` exposes module-level `source` and `pipeline`; resources use `table_name="<source>__<entity>"`; `dataset_name=source_dataset()`
- [ ] `defs.yaml` has `key_prefix` `["dlt", "ingest", "<source>"]`, `group_name` `dlt/ingest/<source>` and `deps: []`
- [ ] `just dlt run <source>` loads rows; `just snowflake query` counts them in `<prefix>_SRC`
- [ ] `dbt/<project>/sources/src_<source>.yml` with the `env_var` schema line, `identifier` and `meta.dagster.asset_key` matching the dlt key
- [ ] Staging model plus `_conf` YAML with named tests; `just dbt build --select <model>` passes
- [ ] `just validate` and `just check` pass
