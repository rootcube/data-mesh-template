"""The example KNMI source: its load window and what an empty API response does.

`importorskip` keeps this module to itself: deleting `dlt_pipelines/pipelines/ingest/knmi` (the
example content, the first thing an adopter replaces) skips these tests instead of failing
collection for the whole suite. Everything that is not KNMI-specific lives in
tests/test_dlt_pipelines.py.
"""

import logging
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from dlt_pipelines.__main__ import discover

knmi = pytest.importorskip("dlt_pipelines.pipelines.ingest.knmi.source")


def test_discover_finds_knmi() -> None:
    assert discover()["knmi"] == "dlt_pipelines.pipelines.ingest.knmi.pipelines"


def test_load_window_never_starts_before_the_start_date() -> None:
    start, end = knmi.load_window(datetime(2026, 1, 10, tzinfo=UTC), days_back=30)
    assert (start, end) == (datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 10, tzinfo=UTC))
    start, _ = knmi.load_window(datetime(2026, 9, 24, tzinfo=UTC), days_back=30)
    assert start == datetime(2026, 8, 25, tzinfo=UTC)


def test_load_window_refuses_a_window_that_starts_after_it_ends() -> None:
    # START_DATE later than `now`: every chunk would be skipped and nothing fetched at all.
    with pytest.raises(ValueError, match="empty load window"):
        knmi.load_window(datetime(2025, 12, 31, tzinfo=UTC), days_back=30)


def test_a_run_without_a_single_row_fails_instead_of_loading_nothing(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def get(url: str, params: dict[str, str], timeout: int) -> Any:
        """The response an unknown station gets: HTTP 200 and an empty list."""
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: [])

    monkeypatch.setattr(knmi, "dlt_requests", SimpleNamespace(get=get))
    with caplog.at_level(logging.WARNING), pytest.raises(knmi.NoRecordsError, match="no rows"):
        list(knmi.fetch_hourly_observations(days_back=5))
    assert "no rows for" in caplog.text
