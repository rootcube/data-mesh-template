---
icon: material/lifebuoy
---

# Troubleshooting

**`just: command not found`**
:   Install it: `brew install just` or `winget install --id Casey.Just -e`, then open a new shell.

**`uv` installed by `just init` but still not found**
:   The installer puts it in `~/.local/bin`. Open a new shell, or add that directory to your
    `PATH`, and run `just init` again.

**The browser does not open during `just sf setup`**
:   Copy the URL the connector prints into a browser yourself, or use
    `just sf setup --auth password`.

**`Insufficient privileges` when registering the key**
:   Your account does not let users set their own key. Send `~/.snowflake/keys/<account>__<user>.pub`
    to your platform administrator and fill in `.env` by hand; see
    [Snowflake authentication](snowflake-auth.md#when-registration-is-not-allowed).

**`JWT token is invalid` on `just sf check`**
:   The key in `.env` does not match the key registered on the user. Run `just sf setup`
    again and let it re-register the existing key.

**`Object does not exist, or operation cannot be performed` in dbt or dlt**
:   Usually a wrong role or database in `.env`, or a role you have not been granted.
    `just sf check` shows what you are connected as; the values should be
    `RL_<PROJECT>_DEV__ENG` and `DB_<PROJECT>_DEV`. Your administrator can list your grants
    with `just tf output -json user_role_grants`.

**`Insufficient privileges to operate on database` on your first load or build**
:   dlt or dbt tried to create a schema, which the engineer role may not do: your personal
    schemas do not exist yet, or `SNOWFLAKE_SCHEMA` in `.env` is not the prefix they were
    created with. Terraform creates them when an administrator applies your
    `terraform/config/users/` file (`just tf output -json personal_schemas` lists them);
    `just sf check` shows which schemas exist. A different prefix needs `schema_prefix` in that
    file and another apply.

**dbt wants `DBT_STG` instead of `DBT_<USERNAME>_STG`**
:   `SNOWFLAKE_SCHEMA` is empty in `.env`; `dbt/profiles.yml` then falls back to `DBT`, a prefix
    nobody has schemas for. Set it to your prefix (`DBT_<USERNAME>`), the same value
    `just sf setup` proposes.

**`FileNotFoundError: .../.venv/bin/dbt` (or "bad interpreter") although the file exists**
:   The checkout was moved or renamed after `.venv` was created; the scripts in it still name
    the old absolute path. Run `just init`: it notices the stale `.venv`, rebuilds it and
    reinstalls the git hook, which stores the same path (its symptom is
    `` `pre-commit` not found. Did you forget to activate your virtualenv? `` on every commit).

**Everything lands in `_STG`, `_SRC`, ... while you expected personal schemas**
:   `ENVIRONMENT` in `.env` is not `dev`. On a laptop it should be; the other environments
    are for deployed service users.

**Quoted values in `.env`**
:   `just` and Docker pass quotes literally, which breaks identifiers and file paths. Write
    `SNOWFLAKE_ROLE=RL_EXAMPLE_DEV__ENG`, never `SNOWFLAKE_ROLE="RL_EXAMPLE_DEV__ENG"`.

**Dagster code location `dbt_example` fails to load**
:   It parses the dbt project on load. Run `just dbt parse` to see the real error; most often
    `dbt deps` has not run yet (`just dbt-all deps`).

**Port 3000 already in use**
:   `just start` stops a previous `dagster dev` of this checkout by itself. When something else
    holds the port, `just stop` frees it, or run on another port: `just port=3001 start`.

**`int__common__holiday` fails with a package error**
:   This Python model needs the Anaconda terms accepted on the Snowflake account (an `ORGADMIN`
    does that once, see [Snowflake provisioning](../administration/snowflake-provisioning.md)).
    Until then, disable the model in `dbt/dbt_example/dbt_project.yml`:

    ```yaml
    models:
      dbt_common:
        03_int:
          common:
            int__common__holiday:
              +enabled: false
    ```

**`just pre-commit` fails with `terraform: command not found`**
:   The `terraform fmt` hook needs the Terraform binary when it runs on all files. Install
    Terraform, or rely on the git hook, which only fires the Terraform hooks for changed `.tf`
    and `terraform/config/` files.

**Windows: scripts are disabled on this system**
:   PowerShell's execution policy. Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
    once, in a PowerShell you own.

**Windows: "No log file available" on a run's stdout/stderr tabs**
:   Dagster only captures a step's output on Windows when `PYTHONLEGACYWINDOWSSTDIO` is set
    (it warns "Compute log capture is disabled" at startup). `just start` sets it, together with
    `PYTHONIOENCODING=utf-8`; set both yourself when you start `dagster dev` another way.
