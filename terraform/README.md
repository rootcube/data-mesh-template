# Snowflake provisioning

Terraform turns the YAML under `config/` into Snowflake objects, following the platform's
conceptual model: **Organisation** > **Team** > **Project** > **Environment** > { **Layers**,
**Roles**, **Computes** }, plus **Users** who may assume project roles. Only platform
administrators run this; engineers never need Terraform.

## What one project becomes

For every project and each of its environments (`config/projects/<project>.yaml`):

| Concept | Snowflake object | Example |
|---------|------------------|---------|
| Project × Environment | database `DB_<PROJECT>_<ENV>` | `DB_EXAMPLE_DEV`, `DB_EXAMPLE_PRD` |
| Layer | schema `_<LAYER>` in that database | `_SRC`, `_STG`, `_INT`, `_MRT`, `_EXP`, `_REF`, `_MTD`, `_TMP` |
| Role | account role `RL_<PROJECT>_<ENV>__<PURPOSE>` with grants per layer | `RL_EXAMPLE_DEV__ENG`, `RL_EXAMPLE_PRD__TFM` |
| Compute | warehouse `WH_<PROJECT>_<ENV>[__<COMPUTE>_<SIZE>]` | `WH_EXAMPLE_DEV` |
| dlt load files | the default internal stage `ST_DEFAULT` of every source layer schema, shared and personal (`stages.tf`) | `DB_EXAMPLE_DEV._SRC.ST_DEFAULT`, `DB_EXAMPLE_DEV.DBT_USERNAME_SRC.ST_DEFAULT` |
| User | role grants (and optionally the user itself) | `username@example.com` gets `RL_EXAMPLE_DEV__ENG` |
| User × role with a `personal` block | a schema `<PREFIX>_<LAYER>` per layer in the listed environments (`personal.tf`) | `DBT_USERNAME_SRC`, `DBT_USERNAME_STG`, ... in `DB_EXAMPLE_DEV` |

Development is shared: engineers work in personal schemas `<PREFIX>_<LAYER>` (for example
`DBT_USERNAME_STG`) of `DB_<PROJECT>_DEV`. Terraform creates them for every user who holds the
engineer role in `dev` (its `personal` block in `config/roles/engineer.yaml`) and grants the role
the block's privileges on them; the engineer role cannot create schemas itself. `<PREFIX>` is the
user file's `schema_prefix`, or `DBT_` plus the login before the `@` with non-alphanumerics as
`_`, uppercased (`DBT_USERNAME` for `username@example.com`).
`just tf output -json personal_schemas` lists them per login. The privileges go to the shared
role, so engineers can read and write each other's personal schemas. The other environments only
use the provisioned `_<LAYER>` schemas.

Terraform connects as `TERRAFORM_USER` through Snowflake's system roles (`providers.tf`), so every
object gets the owner Snowflake recommends: `SYSADMIN` creates and owns databases, schemas,
stages and warehouses, `SECURITYADMIN` the roles and every grant, `USERADMIN` the users. Every
project and platform role is granted to `SYSADMIN`.

## One-time bootstrap

On a fresh account (a trial works) one command does everything below plus your own key pair
and `.env`; it needs the organization name, the account name and the password of a user holding
`ACCOUNTADMIN`:

```bash
just setup            # = just init + a one-question wizard; answer 1 (fresh) for just sf bootstrap
```

It generates `~/.snowflake/keys/terraform.p8`, runs `init.sql` with that public key, registers
a key pair on your own user, writes a `config/users/<you>.yaml` (engineer in development on
every project) unless one lists your login, warns about user files whose login the account does
not have (Terraform would fail on their grants), writes the `TF_VAR_*` block to `.env`, runs
`terraform init` and `terraform apply` (you confirm the plan; `just sf bootstrap --yes` auto-approves) and ends
like `just sf setup`. Rerunning it is safe: the prompts default to the values already in
`.env`, `init.sql` is idempotent, existing keys are kept when you say so, and Terraform applies
only the difference. Objects Terraform would create that already exist (an account provisioned
from another checkout: `just setup` answer 3, or `--existing ask|sync|wipe`) are either synced
into the state and handed to their `SYSADMIN`, `SECURITYADMIN` or `USERADMIN` owner with
`GRANT OWNERSHIP ... COPY CURRENT GRANTS`, or wiped first.

The manual equivalent, for accounts where you do not hold `ACCOUNTADMIN` yourself:

1. Generate a key pair for the Terraform service user; the command prints the public key body:

    ```bash
    just sf keygen terraform
    ```

2. Open `modules/snowflake/init.sql`, uncomment the `RSA_PUBLIC_KEY` line in the `ALTER USER`
   block of `TERRAFORM_USER` and paste the public key body, then run the whole script as
   `ACCOUNTADMIN` in Snowsight. It sets the account parameters below, creates `TERRAFORM_USER`
   with the system roles `SYSADMIN` (its default role), `SECURITYADMIN` and `USERADMIN`, the
   warehouse `WH_PLATFORM_PROVISIONING` and the database `DB_PLATFORM_PROVISIONING` (both owned
   by `SYSADMIN`, usable by `USERADMIN`) and a resource monitor. It drops
   `RL_PLATFORM_PROVISIONING`, the custom role earlier versions provisioned with; what that role
   still owned falls to `ACCOUNTADMIN`, and `just sf bootstrap` syncs or wipes it.
   The script is idempotent; rerun it after edits. If the user already holds a key in
   `RSA_PUBLIC_KEY` (another administrator's machine), use `RSA_PUBLIC_KEY_2` for the second one.

3. Put the provider settings in `.env` (the block at the bottom of `.env.example`):

    ```dotenv
    TF_VAR_SNOWFLAKE_ORGANIZATION=<organization>
    TF_VAR_SNOWFLAKE_ACCOUNT=<account>
    TF_VAR_SNOWFLAKE_USER=TERRAFORM_USER
    TF_VAR_SNOWFLAKE_PRIVATE_KEY_PATH=~/.snowflake/keys/terraform.p8
    ```

4. Initialize and check the configuration:

    ```bash
    just tf init
    just tf-validate-config
    just tf plan
    ```

The account parameters `init.sql` sets (users and sessions can still override most of them):
`TIMEZONE = 'UTC'` and `TIMESTAMP_TYPE_MAPPING = 'TIMESTAMP_NTZ'`; ISO weeks starting on Monday
(`WEEK_START = 1`, `WEEK_OF_YEAR_POLICY = 0`); ISO 8601 output formats for `DATE`, `TIME` and the
`TIMESTAMP` types; AES-256 for files `PUT` into internal stages (`CLIENT_ENCRYPTION_KEY_SIZE`);
`REQUIRE_STORAGE_INTEGRATION_FOR_STAGE_CREATION` and `_OPERATION` and
`PREVENT_UNLOAD_TO_INLINE_URL`; a four-hour `STATEMENT_TIMEOUT_IN_SECONDS`;
`ALLOW_CLIENT_MFA_CACHING` and `ENABLE_UNREDACTED_QUERY_SYNTAX_ERROR`; and
`PERIODIC_DATA_REKEYING`, which needs Enterprise Edition and is skipped with a message on Standard.

## Configuration

One YAML file per object, validated against the JSON schemas in `config/_validation/schemas/`
(`just tf-validate-config`, also a pre-commit hook and a CI step).

| Folder | Holds | Notes |
|--------|-------|-------|
| `organisations/` | the organisation | one file |
| `teams/` | teams that own projects | `organisation` refers to the organisation file name |
| `projects/` | one file per project | `team`, `environments`, `layers`, `computes`, `roles`; `"*"` means all enabled |
| `environments/` | dev, tst, acc, prd (and sandbox) | `disabled: true` hides an environment everywhere |
| `layers/` | source, reference, staging, integration, mart, expose, metadata, temporary, ... | codes become schema names |
| `roles/` | project roles (engineer, analyst, ingest, transform) and global roles | privileges per compute, database, layer and environment |
| `computes/` | warehouse profiles and sizes | `default` has no suffix |
| `users/` | who may assume which project roles | see onboarding below |

A new project is a copy of `projects/example.yaml` with its own `code`; `just tf plan` shows the
databases, schemas, roles and warehouses it adds.

## Onboarding a person

1. Add `config/users/<name>.yaml`:

    ```yaml
    login: "username@example.com"
    name: "Username"
    type: "person"
    create: false        # true creates the user with a one-time password
    roles:
      - project: example
        role: engineer
        environments: [development]
    ```

2. `just tf apply`. Besides the grants, this creates the person's personal schemas
   (`DBT_USERNAME_SRC`, `DBT_USERNAME_STG`, ... with the stage `DBT_USERNAME_SRC.ST_DEFAULT`),
   so it has to happen before their first dlt load or dbt run. For created users, hand out the
   password from `just tf output -json initial_passwords`.

3. The person runs `just sf setup`, which logs in once, registers a key pair and writes
   their `.env` with `SNOWFLAKE_ROLE=RL_EXAMPLE_DEV__ENG`, `SNOWFLAKE_DATABASE=DB_EXAMPLE_DEV`,
   `SNOWFLAKE_WAREHOUSE=WH_EXAMPLE_DEV` and their personal schema prefix, `DBT_USERNAME`.

A different prefix is `schema_prefix: DBT_OTHER` in the user file plus a `just tf apply`.
`just sf setup` proposes it from that file; a `.env` that already holds `SNOWFLAKE_SCHEMA` needs
the new value by hand.

System users for deployed environments (the transform and ingest roles) are created by hand:
`CREATE USER <login> TYPE = SERVICE`, then `just sf keygen <login>` and
`ALTER USER <login> SET RSA_PUBLIC_KEY = '...'`. Grant them `RL_<PROJECT>_<ENV>__TFM` or
`__ING` through a `create: false` user file with the same `roles` list.

!!! note "If a person cannot register their own key"
    `ALTER USER ... SET RSA_PUBLIC_KEY` on your own user is allowed by default. If an account
    policy blocks it, register the `.pub` file for them as `SECURITYADMIN`.

## Differences from rootcube/platform

This folder is a port of the platform repository's Terraform with four additions, kept small
so they can flow back upstream:

- `config/users/` and `users.tf`: role grants to logins (and optional user creation).
- `personal` on a role and `personal.tf`: personal schemas per user holding the role (the
  engineer role in dev), with the user file's optional `schema_prefix`.
- `privileges.database` on a role: extra database privileges per environment on top of the
  implicit `USAGE` (none of the shipped roles needs any).
- `config/layers/metadata.yaml` (`_MTD`): where dbt writes run metadata.

The provider is Snowflake only; the dbt Cloud, GitHub and Kubernetes providers of the platform
repository are not part of the starter.

## Python models need Anaconda packages

`dbt_common` ships a Python (Snowpark) model, `int__generic__holiday`, that imports the
`holidays` package from the Snowflake Anaconda channel. An `ORGADMIN` accepts the Anaconda terms
once per account (Snowsight: Admin > Billing & Terms). Without that, disable the model in the
consuming project:

```yaml
models:
  dbt_common:
    03_int:
      generic:
        int__generic__holiday:
          +enabled: false
```

## State and teardown

State is local (`terraform.tfstate`, git-ignored). Move it to a remote backend before several
administrators share the configuration. `just tf destroy` removes everything Terraform created;
the bootstrap objects from `init.sql` stay.
