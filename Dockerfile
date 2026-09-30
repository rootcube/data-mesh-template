# syntax=docker/dockerfile:1
# The code location image of the Kubernetes deployment (terraform/components/dagster): every code
# location and every run pod it launches runs this. `just k8s build` builds it as dagster-starter:local.
#
# The checkout layout stays as it is: the code finds dbt/, .dlt/ and pyproject.toml relative to the
# repository root (src/orchestrator/utils/paths.py), so the project is installed editable in /app.
# One image for every environment; ENVIRONMENT and the Snowflake identity come from the deployment.
FROM ghcr.io/astral-sh/uv:0.12.21-python3.13-trixie-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1 \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# The locked dependencies first, without the project, so a code change reuses this layer. `deploy`
# adds dagster-k8s and dagster-postgres: the run pods load the instance the Helm chart configures.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --group deploy

COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --group deploy

ENV PATH="/app/.venv/bin:$PATH" \
    DLT_PROJECT_DIR=/app \
    DLT_DATA_DIR=/app/.dlt/data \
    DBT_PROFILES_DIR=/app/dbt

# The dbt packages, and the manifest the dbt code locations read when they load: `dagster dev` makes
# them on the fly, a deployment does not. Parsed with the prd target and no credentials (parsing
# does not connect); the asset keys do not depend on the target.
RUN python scripts/dbt_all.py deps --quiet \
    && python scripts/dbt_all.py parse --target prd --quiet

# Not root. The code writes into its checkout: dbt's target/ per run (and dbt/.user.yml), dlt's
# pipeline folders, and the definitions state Dagster keeps under src/orchestrator/defs/.
RUN groupadd --system --gid 999 dagster \
    && useradd --system --gid 999 --uid 999 --create-home dagster \
    && mkdir -p /app/.dlt/data \
    && chown -R dagster:dagster /app/dbt /app/.dlt /app/src/orchestrator/defs
USER dagster
