---
icon: material/test-tube
---

# Snowflake Trial Account setup

The fastest way to see the whole starter run end to end is a free Snowflake trial: you are
`ACCOUNTADMIN` there, so one command bootstraps the account, provisions the `example` project
and sets up your own key pair. Budget about fifteen minutes, most of it waiting for Snowflake.

## 1. Sign up

1. Go to [signup.snowflake.com](https://signup.snowflake.com/) and fill in the form. Any
   edition works; **Enterprise** is the default and fine (on Standard the bootstrap skips the one
   Enterprise-only account setting, `PERIODIC_DATA_REKEYING`). Pick a cloud and region close to
   you; the region does not matter for the starter.
2. Open the activation mail and choose a **username** and **password**. The username becomes
   your Snowflake login (`CURRENT_USER()` returns it uppercased, `USERNAME` for `username`). Write
   both down; the bootstrap asks for them.
3. Log in to Snowsight once. Trial accounts enforce multi-factor authentication for people:
   Snowsight asks you to enrol with an authenticator app (Duo, Google Authenticator, or any
   TOTP app) at the first login. Finish that before running the bootstrap, which logs in with
   your password and then needs a passcode or a push from that app.

## 2. Find the organization and account name

The bootstrap asks for the two parts of the account identifier separately, because Terraform's
Snowflake provider takes them as two settings: the **organization name** and the **account
name** within it. In Snowsight, open the account menu at the bottom left, hover over the
account and click **Copy account identifier**; it looks like `ABCDEFG-XY12345`, organization
before the dash, account after it. Or run this in a worksheet:

```sql
SELECT CURRENT_ORGANIZATION_NAME(), CURRENT_ACCOUNT_NAME();
```

The locator from the activation mail (`xy12345.eu-central-1`) is not what you need here.

## 3. Install the tools

`just` and git. Terraform (1.5 or newer) is needed too, but `just setup` installs it for you
when it is missing (through tfenv on Homebrew, winget on Windows).

=== "macOS / Linux"

    ```bash
    brew install just git
    ```

=== "Windows"

    ```powershell
    winget install --id Casey.Just -e
    winget install --id Git.Git -e
    ```

## 4. Bootstrap

```bash
git clone git@github.com:rootcube/data-mesh-template.git && cd data-mesh-template
just setup
```

`just setup` runs `just init` (uv, the virtual environment, `.env`, dbt packages) and then asks
whether the account is fresh or already provisioned. Answer `1` (fresh): that is
`just sf bootstrap`, which installs Terraform if missing and asks for the organization name, the
account name, your username, your password and an MFA passcode (leave it empty for a push
notification), then:

1. logs in to `<organization>-<account>` and switches to `ACCOUNTADMIN`;
2. lists the account parameters of `terraform/modules/snowflake/account_settings.sql` (UTC, ISO
   weeks and date formats, a few security defaults) and applies them when you confirm
   (`--account-settings ask|apply|skip`, default `ask`);
3. generates `~/.snowflake/keys/terraform.p8`, asking for an optional passphrase (or for the
   passphrase of an existing encrypted key), and runs `terraform/modules/snowflake/init.sql`
   with its public key: `TERRAFORM_USER` with the system roles `SYSADMIN`, `SECURITYADMIN` and
   `USERADMIN`, `WH_PLATFORM_PROVISIONING`, `DB_PLATFORM_PROVISIONING` and the resource monitor;
4. generates a key pair for your own user and registers it with `ALTER USER ... SET RSA_PUBLIC_KEY`.
   It always asks for a passphrase and warns first: this key signs in as a user holding
   `ACCOUNTADMIN`, so give it one, and use a separate login without `ACCOUNTADMIN` for daily work;
5. writes `terraform/config/users/local/<you>.yaml` (the `engineer` role in `development` on every
   project under `terraform/config/projects/`; `users/local/` is git-ignored), puts the
   `TF_VAR_SNOWFLAKE_*` block in `.env`
   and runs `terraform init` and `terraform apply`. Read the plan and answer `yes`; it creates
   the databases, schemas, roles and warehouses of the `example` project in `development` and
   `production`, grants you `RL_EXAMPLE_DEV__ENG` and creates your personal schemas
   (`DBT_<USERNAME>_SRC`, `DBT_<USERNAME>_STG`, ...) in `DB_EXAMPLE_DEV`;
6. connects with your key pair, proposes `RL_EXAMPLE_DEV__ENG`, `WH_EXAMPLE_DEV`,
   `DB_EXAMPLE_DEV` and a personal schema prefix (`DBT_<USERNAME>`), verifies the login and writes
   `.env`, readable by you only (as are the private keys).

`just sf bootstrap --yes` runs the same without the wizard, applies the account parameters,
auto-approves the Terraform plan and skips the context confirmation. Rerunning `just setup` is safe: the prompts offer the organization, account and user from your
`.env` as defaults (Enter keeps them), `account_settings.sql` and `init.sql` are idempotent, the
script offers to keep existing keys and skips registering a key the user already holds (another
key there is replaced only when you confirm), and Terraform applies only the difference.

## 5. Check and run

```bash
just sf check   # user, role, warehouse, database and your personal layer schemas
just start             # Dagster UI on http://localhost:3000
```

Then follow [First run](../getting-started/first-run.md): materialize the KNMI load and build
the dbt models.

!!! note "Python models need the Anaconda terms"
    `dbt_common` ships one Snowpark model, `int__common__holiday` (in `03_int/common`), that
    imports the `holidays` package. Accept the Anaconda terms once in Snowsight (**Admin > Billing & Terms**, as
    `ORGADMIN`) or disable the model; see
    [Snowflake provisioning](snowflake-provisioning.md#python-models-need-anaconda-packages).

## What is different from a real account

| Trial | Real account |
|-------|--------------|
| Your login holds `ACCOUNTADMIN`, so one person does bootstrap, provisioning and engineering | An administrator bootstraps and provisions ([Snowflake provisioning](snowflake-provisioning.md)); engineers only run `just sf setup` |
| Password plus MFA is the only login | Usually SSO; `just sf setup` opens the browser instead |
| Terraform state is a local `terraform.tfstate` | Move it to a remote backend before a second administrator applies |
| The account expires after 30 days, with everything in it | Nothing expires; `just tf clean` removes what Terraform created, databases and data included, after you type the account name ([State and teardown](snowflake-provisioning.md#state-and-teardown)) |

The user file the bootstrap wrote sits in `terraform/config/users/local/`, which git ignores,
because its login exists in this account only. Move it up to `terraform/config/users/` and
commit it if you want the grant to survive a later `terraform apply` from another checkout;
delete it when the trial is over.
