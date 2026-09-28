"""Constants for the KNMI ingest pipeline."""

from datetime import UTC, datetime

KNMI_UURGEGEVENS_URL = "https://www.daggegevens.knmi.nl/klimatologie/uurgegevens"

# A handful of KNMI stations (De Bilt, Leeuwarden, Eelde, Twenthe, Eindhoven, Volkel, Maastricht),
# keeping volumes small: 7 stations x 24 hours x DAYS_BACK days.
STATIONS = (260, 270, 280, 290, 370, 375, 380)

DAYS_BACK = 30
# Headroom, not a current constraint: the API rejects a query over roughly 100k rows (measured), and
# the default window is 7 stations x 24 hours x 30 days = ~4.9k rows. Worth keeping because the
# rejection arrives as an HTML "Query Error" page with HTTP 200, so a raised DAYS_BACK would not fail
# on `raise_for_status()` but on `response.json()`.
CHUNK_DAYS = 10

# Nothing before this date is ever fetched, whatever DAYS_BACK says: keeps loads small and fast.
START_DATE = datetime(2026, 1, 1, tzinfo=UTC)
