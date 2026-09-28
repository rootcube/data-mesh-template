"""dlt pipeline: KNMI hourly weather observations -> the source layer (knmi__climate_hourly).

Every source lands in the project's source layer (`_SRC`, or your personal `<PREFIX>_SRC` in dev)
as `<source>__<entity>`. `merge` with a primary key keeps the table free of duplicates when the
pipeline runs daily over an overlapping window; `just dlt run knmi --full-refresh` reloads it.
"""

from collections.abc import Iterator

import dlt

from dlt_pipelines.pipelines.ingest.knmi.source import fetch_hourly_observations
from dlt_pipelines.utils.destination import destination, pipeline_name, source_dataset

SOURCE = "knmi"
ENTITY = "climate_hourly"


# The source (and so the dlt schema) is named after the source, not after one of its entities: a
# second resource joins it without renaming anything. The table name carries `<source>__<entity>`.
@dlt.source(name=SOURCE, max_table_nesting=0)
def knmi_source() -> Iterator[dlt.sources.DltResource]:
    """KNMI hourly observations for a handful of stations, last 30 days."""

    @dlt.resource(
        name=ENTITY,
        table_name=f"{SOURCE}__{ENTITY}",
        write_disposition="merge",
        primary_key=["station_code", "date", "hour"],
        # WW (weather code) and IX (how it was observed) are null in every row of a recent window,
        # so dlt cannot infer a type and drops the columns with a warning. Declare them instead.
        columns={"ww": {"data_type": "bigint"}, "ix": {"data_type": "bigint"}},
    )
    def climate_hourly() -> Iterator[dict]:
        yield from fetch_hourly_observations()

    yield climate_hourly()


source = knmi_source()

pipeline = dlt.pipeline(
    pipeline_name=pipeline_name(SOURCE),
    destination=destination(SOURCE),
    dataset_name=source_dataset(),
)
