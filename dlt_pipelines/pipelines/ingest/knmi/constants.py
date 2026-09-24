"""Constants for the KNMI ingest pipeline."""

from datetime import UTC, datetime

KNMI_UURGEGEVENS_URL = "https://www.daggegevens.knmi.nl/klimatologie/uurgegevens"

# A handful of KNMI stations (De Bilt, Leeuwarden, Eelde, Twenthe, Eindhoven, Volkel, Maastricht),
# keeping volumes small: 7 stations x 24 hours x DAYS_BACK days.
STATIONS = (260, 270, 280, 290, 370, 375, 380)

# The API rejects requests that span too many rows; fetch in chunks of this many days.
DAYS_BACK = 30
CHUNK_DAYS = 10

# Nothing before this date is ever fetched, whatever DAYS_BACK says: keeps loads small and fast.
START_DATE = datetime(2026, 1, 1, tzinfo=UTC)
