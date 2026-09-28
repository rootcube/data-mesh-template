"""Fetch hourly weather observations from the KNMI `uurgegevens` endpoint.

API docs: https://www.daggegevens.knmi.nl/klimatologie/uurgegevens (free, no authentication).
Records come back as JSON dicts with the KNMI field names: `station_code`, `date`, `hour` and
the meteorological codes (T = temperature in 0.1 C, FH = wind speed in 0.1 m/s, RH = hourly
precipitation in 0.1 mm, Q = global radiation in J/cm2, ...).
"""

import logging
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

from dlt.sources.helpers import requests as dlt_requests

from dlt_pipelines.pipelines.ingest.knmi.constants import (
    CHUNK_DAYS,
    DAYS_BACK,
    KNMI_UURGEGEVENS_URL,
    START_DATE,
    STATIONS,
)

LOGGER = logging.getLogger(__name__)
DATE_FORMAT = "%Y%m%d"


class NoRecordsError(RuntimeError):
    """Every chunk of the window came back empty: a wrong station list, or an API that changed.

    Raised instead of logged because nothing downstream notices an empty load: dlt reports the
    load package as LOADED, the Dagster materialization carries no row count, and `has_data` on
    the staging model still passes on the rows of the previous load.
    """


def date_chunks(start: datetime, end: datetime, days: int) -> Iterator[tuple[str, str]]:
    """Yield (chunk_start, chunk_end) as YYYYMMDD strings covering start..end inclusive."""
    current = start
    while current <= end:
        chunk_end = min(current + timedelta(days=days - 1), end)
        yield current.strftime(DATE_FORMAT), chunk_end.strftime(DATE_FORMAT)
        current = chunk_end + timedelta(days=1)


def load_window(now: datetime, days_back: int = DAYS_BACK) -> tuple[datetime, datetime]:
    """The dates to fetch: the last `days_back` days, never earlier than START_DATE.

    Raises ValueError when the window is empty (START_DATE after `now`), which would otherwise
    fetch nothing at all: `date_chunks` yields no chunk and no HTTP call is made.
    """
    start = max(now - timedelta(days=days_back), START_DATE)
    if start > now:
        raise ValueError(f"empty load window: START_DATE {start:%Y-%m-%d} is after {now:%Y-%m-%d}")
    return start, now


def fetch_hourly_observations(days_back: int = DAYS_BACK) -> Iterator[dict]:
    """Yield one dict per station per hour for the last `days_back` days (from START_DATE at the earliest).

    An empty chunk is a warning, a run without a single row is a NoRecordsError.
    """
    start, end = load_window(datetime.now(tz=UTC), days_back)
    stations = ":".join(str(code) for code in STATIONS)  # the API separates station codes with ':'

    total = 0
    for chunk_start, chunk_end in date_chunks(start, end, CHUNK_DAYS):
        LOGGER.info("KNMI hourly: fetching %s..%s for stations %s", chunk_start, chunk_end, stations)
        response = dlt_requests.get(
            KNMI_UURGEGEVENS_URL,
            params={"stns": stations, "start": chunk_start, "end": chunk_end, "fmt": "json"},
            timeout=120,
        )
        response.raise_for_status()
        records = response.json()
        if not records:
            LOGGER.warning("KNMI hourly: no rows for %s..%s, stations %s", chunk_start, chunk_end, stations)
        total += len(records)
        yield from records
    if not total:
        raise NoRecordsError(
            f"KNMI returned no rows for stations {stations} between {start:%Y-%m-%d} and {end:%Y-%m-%d}"
        )
    LOGGER.info("KNMI hourly: fetched %d rows", total)
