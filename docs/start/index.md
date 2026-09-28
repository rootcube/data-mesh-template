---
icon: material/rocket-launch
---

# Start

From a fresh clone to a Dagster UI loading weather data into schemas that are yours alone. Four
pages, in order:

1. [Prerequisites](prerequisites.md): `just`, git, and what to ask your platform administrator for.
2. [Installation](installation.md): clone the repo, then `just init` for uv, the Python environment and the dbt packages.
3. [Snowflake authentication](snowflake-auth.md): `just sf setup` logs you in once and moves you to a key pair.
4. [First run](first-run.md): `just start`, materialize the KNMI load, build the dbt models.

Stuck at any of them: [Troubleshooting](troubleshooting.md). Turning the starter into your own
platform, example and all: [Making it yours](adopting.md).

!!! info "No Terraform here"
    These pages are for engineers on a platform someone else provisioned. Setting up the Snowflake
    account and onboarding people is [Operate](../operate/index.md). On a fresh account where you
    hold `ACCOUNTADMIN`, `just setup` replaces steps 2 and 3 and provisions the project as well:
    [Snowflake trial account](../operate/snowflake-trial-account-setup.md).

!!! tip "No Snowflake at all"
    `just sf local` skips step 3 entirely: no account, no key pair, just `ENVIRONMENT=local` in
    `.env`. dlt and dbt then build against a DuckDB file in the checkout. See
    [Local only, no Snowflake](installation.md#local-only-no-snowflake).
