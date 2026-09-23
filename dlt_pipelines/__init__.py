"""dlt ingestion pipelines, one folder per source under pipelines/ingest/<source>/.

Each source exposes a module-level `source` and `pipeline` in pipelines.py and a defs.yaml that
Dagster's dlt component turns into assets (loaded by src/orchestrator/locations/dlt). The same
objects run standalone through `just dlt run <source>`.
"""
