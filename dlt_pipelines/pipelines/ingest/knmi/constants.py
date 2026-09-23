"""Constants for the KNMI ingest pipeline."""

KNMI_UURGEGEVENS_URL = "https://www.daggegevens.knmi.nl/klimatologie/uurgegevens"

# A handful of KNMI stations, keeping volumes small (7 stations x 24 hours x DAYS_BACK days).
# Use "ALL" to pull every station.
STATIONS: dict[int, str] = {
    260: "De Bilt",
    270: "Leeuwarden",
    280: "Eelde",
    290: "Twenthe",
    370: "Eindhoven",
    375: "Volkel",
    380: "Maastricht",
}

# The API rejects requests that span too many rows; fetch in chunks of this many days.
DAYS_BACK = 30
CHUNK_DAYS = 10
