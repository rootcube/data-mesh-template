from dlt_pipelines.__main__ import discover


def test_discover_finds_knmi() -> None:
    assert discover()["knmi"] == "dlt_pipelines.pipelines.ingest.knmi.pipelines"
