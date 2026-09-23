---
icon: material/lifebuoy
---

# Troubleshooting

**`just: command not found`**
:   Install it: `brew install just` or `winget install --id Casey.Just -e`, then open a new shell.

**`uv` installed by `just init` but still not found**
:   The installer puts it in `~/.local/bin`. Open a new shell, or add that directory to your
    `PATH`, and run `just init` again.

**The browser does not open during `just snowflake setup`**
:   Copy the URL the connector prints into a browser yourself, or use
    `just snowflake setup --auth password`.

**`Insufficient privileges` when registering the key**
:   Your account does not let users set their own key. Send `~/.snowflake/keys/<account>__<user>.pub`
    to your platform administrator and fill in `.env` by hand; see
    [Snowflake authentication](snowflake-auth.md#when-registration-is-not-allowed).

**`JWT token is invalid` on `just snowflake check`**
:   The key in `.env` does not match the key registered on the user. Run `just snowflake setup`
    again and let it re-register the existing key.

**`Object does not exist, or operation cannot be performed` in dbt or dlt**
:   Usually a wrong role or database in `.env`, or a role you have not been granted.
    `just snowflake check` shows what you are connected as; the values should be
    `RL_<PROJECT>_DEV__ENG` and `DB_<PROJECT>_DEV`. Your administrator can list your grants
    with `just tf output -json user_role_grants`.

**dbt builds into `DBT_STG` instead of `DBT_<NAME>_STG`**
:   `SNOWFLAKE_SCHEMA` is empty in `.env`; `dbt/profiles.yml` then falls back to `DBT`. Set it
    to your prefix (`DBT_<NAME>`), the same value `just snowflake setup` proposes.

**Everything lands in `_STG`, `_SRC`, ... while you expected personal schemas**
:   `ENVIRONMENT` in `.env` is not `dev`. On a laptop it should be; `tst`, `acc` and `prd` are
    for deployed service users.

**Quoted values in `.env`**
:   `just` and Docker pass quotes literally, which breaks identifiers and file paths. Write
    `SNOWFLAKE_ROLE=RL_EXAMPLE_DEV__ENG`, never `SNOWFLAKE_ROLE="RL_EXAMPLE_DEV__ENG"`.

**Dagster code location `dbt_example` fails to load**
:   It parses the dbt project on load. Run `just dbt parse` to see the real error; most often
    `dbt deps` has not run yet (`just dbt-all deps`).

**Port 3000 already in use**
:   `just stop`, then `just start` again. Or run on another port: `just port=3001 start`.

**`int__generic__holiday` fails with a package error**
:   This Python model needs the Anaconda terms accepted on the Snowflake account (an `ORGADMIN`
    does that once, see [Snowflake provisioning](../administration/snowflake-provisioning.md)).
    Until then, disable the model in `dbt/dbt_example/dbt_project.yml`:

    ```yaml
    models:
      dbt_common:
        03_int:
          generic:
            int__generic__holiday:
              +enabled: false
    ```

**`just pre-commit` fails with `terraform: command not found`**
:   The `terraform fmt` hook needs the Terraform binary when it runs on all files. Install
    Terraform, or rely on the git hook, which only fires the Terraform hooks for changed `.tf`
    and `terraform/config/` files.

**Windows: scripts are disabled on this system**
:   PowerShell's execution policy. Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
    once, in a PowerShell you own.
