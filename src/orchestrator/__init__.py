"""Orchestration package: Dagster code locations (src/orchestrator/locations), shared Snowflake
settings (src/orchestrator/resources) and small utilities. dlt pipelines live in the top-level
`dlt_pipelines` package and dbt projects under `dbt/`."""

import warnings

# The Snowflake connector ships a vendored `requests` whose version check predates urllib3 2.x
# and warns "urllib3 (...) or chardet (...)/charset_normalizer (...) doesn't match a supported
# version!" on every import. The connector works with it; nothing to act on.
warnings.filterwarnings("ignore", message=r"urllib3 \(", module=r"snowflake\.connector\.vendored\.requests")
