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

It generates `~/.snowflake/keys/terraform.p8` (asking for a passphrase, empty for none), lists the
account parameters of `modules/snowflake/account_settings.sql` and applies them when you confirm
(`--account-settings ask|apply|skip`, default `ask`; `--yes` applies, answer 3 skips), runs
`init.sql` with that public key, registers a key pair on your own user (after a passphrase prompt,
since that user holds `ACCOUNTADMIN`), writes a `config/users/local/<you>.yaml` (engineer in development on
every project; `users/local/` is git-ignored, the login exists in your account only) unless a user
file lists your login, warns about user files whose login the account does
not have (Terraform would fail on their grants), writes the `TF_VAR_*` block to `.env`, runs
`terraform init` and `terraform apply` (you confirm the plan; `just sf bootstrap --yes` auto-approves) and ends
like `just sf setup`. Rerunning it is safe: the prompts default to the values already in
`.env`, `init.sql` is idempotent, existing keys are kept when you say so, a key already registered
on a user is replaced only after you confirm (the fingerprints are compared first), and Terraform
applies only the difference. Objects Terraform would create that already exist (an account provisioned
from another checkout: `just setup` answer 3, or `--existing ask|sync|wipe`) are either synced
into the state and handed to their `SYSADMIN`, `SECURITYADMIN` or `USERADMIN` owner with
`GRANT OWNERSHIP ... COPY CURRENT GRANTS`, or wiped first. Objects the state already tracks but
another role owns are handed back the same way, before the plan runs. This happens to an account an
earlier version provisioned: `init.sql` drops that version's `RL_PLATFORM_PROVISIONING`, and
Snowflake gives what it owned to `ACCOUNTADMIN`, where Terraform can no longer change it.

The manual equivalent, for accounts where you do not hold `ACCOUNTADMIN` yourself:

1. Generate a key pair for the Terraform service user; the command prints the public key body:

    ```bash
    just sf keygen terraform
    ```

2. Open `modules/snowflake/init.sql`, uncomment the `RSA_PUBLIC_KEY` line in the `ALTER USER`
   block of `TERRAFORM_USER` and paste the public key body, then run the whole script as
   `ACCOUNTADMIN` in Snowsight. It creates `TERRAFORM_USER`
   with the system roles `SYSADMIN` (its default role), `SECURITYADMIN` and `USERADMIN`, the
   warehouse `WH_PLATFORM_PROVISIONING` and the database `DB_PLATFORM_PROVISIONING` (both owned
   by `SYSADMIN`, usable by `USERADMIN`) and a resource monitor. It drops
   `RL_PLATFORM_PROVISIONING`, the custom role earlier versions provisioned with; what that role
   still owned falls to `ACCOUNTADMIN`, and `just sf bootstrap` syncs or wipes it.
   The script is idempotent; rerun it after edits. If the user already holds a key in
   `RSA_PUBLIC_KEY` (another administrator's machine), use `RSA_PUBLIC_KEY_2` for the second one.
   For the account parameters below, also run `modules/snowflake/account_settings.sql` as
   `ACCOUNTADMIN`; `init.sql` no longer sets them.

3. Put the provider settings in `.env` (the block at the bottom of `.env.example`):

    ```dotenv
    TF_VAR_SNOWFLAKE_ORGANIZATION=<organization>
    TF_VAR_SNOWFLAKE_ACCOUNT=<account>
    TF_VAR_SNOWFLAKE_USER=TERRAFORM_USER
    TF_VAR_SNOWFLAKE_PRIVATE_KEY_PATH=~/.snowflake/keys/terraform.p8
    # Empty unless the key is encrypted; single-quote it when it holds spaces, # or $
    TF_VAR_SNOWFLAKE_PRIVATE_KEY_PASSPHRASE=
    ```

4. Initialize and check the configuration:

    ```bash
    just tf init
    just tf-validate-config
    just tf plan
    ```

The account parameters `modules/snowflake/account_settings.sql` sets (`just sf bootstrap` lists
them and asks first; users and sessions can still override most of them):
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
| `roles/` | project roles (engineer, analyst, ingest, transform) and platform roles (`global/`, disabled) | privileges per compute, database, layer and environment |
| `computes/` | warehouse profiles and sizes | `default` has no suffix |
| `users/` | who may assume which project roles | see onboarding below; the file name is the key, also in a sub-folder; `users/local/` (git-ignored) holds the files `just sf bootstrap` writes for your own account |

A new project is a copy of `projects/example.yaml` with its own `code`; `just tf plan` shows the
databases, schemas, roles and warehouses it adds.

## Onboarding a person

1. Add `config/users/<name>.yaml`:

    ```yaml
    login: "username@example.com"
    name: "Username"
    create: false        # true creates the user (a person) with a one-time password
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

`dbt_common` ships a Python (Snowpark) model, `int__common__holiday` (in `03_int/common`), that
imports the `holidays` package from the Snowflake Anaconda channel. An `ORGADMIN` accepts the
Anaconda terms once per account (Snowsight: Admin > Billing & Terms). Without that, disable the
model in the consuming project:

```yaml
models:
  dbt_common:
    03_int:
      common:
        int__common__holiday:
          +enabled: false
```

## Provider versions

`.terraform.lock.hcl` is committed: it pins the exact provider versions (and their checksums for
Windows, Linux and macOS) that the `~> 2.0` and `~> 3.6` constraints in `providers.tf` resolved
to, so every administrator and CI plan with the same provider. Upgrade deliberately, then review
the plan and commit the lock file:

```bash
just tf init -upgrade
just tf providers lock -platform=windows_amd64 -platform=linux_amd64 -platform=darwin_amd64 -platform=darwin_arm64
just tf plan
```

## Securing the Terraform user

`TERRAFORM_USER` holds `SYSADMIN`, `SECURITYADMIN` and `USERADMIN`: whoever has its private key
controls every object, grant and user in the account. Restrict where it may log in from with a
network policy listing the addresses Terraform runs from (the administrators' networks, a
deployment runner). Run it as `ACCOUNTADMIN`, which owns `TERRAFORM_USER` (`init.sql` creates it).
The policy binds this user only: leaving an address out locks Terraform out from there, not you:

```sql
USE ROLE ACCOUNTADMIN;
CREATE NETWORK POLICY NP_TERRAFORM_USER
  ALLOWED_IP_LIST = ('203.0.113.10', '198.51.100.0/24')
  COMMENT = 'Where Terraform may run from';
ALTER USER TERRAFORM_USER SET NETWORK_POLICY = NP_TERRAFORM_USER;
```

Also encrypt its private key. `just sf bootstrap` asks for a passphrase when it creates
`terraform.p8` and writes it to `.env` as `TF_VAR_SNOWFLAKE_PRIVATE_KEY_PASSPHRASE`, which passes it
to the provider. To encrypt a key that is already registered, re-encrypt it in place so the public
key stays the same, then set that variable yourself:

```bash
openssl pkcs8 -topk8 -v2 aes256 -in ~/.snowflake/keys/terraform.p8 -out ~/.snowflake/keys/terraform.enc.p8
mv ~/.snowflake/keys/terraform.enc.p8 ~/.snowflake/keys/terraform.p8
```

`just sf keygen terraform --force` is not a way to do this: it writes a new key pair, which
Terraform cannot use until an `ACCOUNTADMIN` registers its public key on `TERRAFORM_USER`.

## State and teardown

State is local (`terraform.tfstate`, git-ignored). Move it to a remote backend before several
administrators share the configuration.

Databases carry `prevent_destroy` (`modules/snowflake/database/main.tf`): a plan that would drop
one fails, whether it comes from `just tf destroy` or from removing an environment from a project
(or a project file).

To remove everything this checkout's state tracks on purpose, databases and all their data
included, run `just tf clean`. It lists what goes and asks you to type the account name back. It
then has Terraform destroy everything but the databases, drops the databases as `TERRAFORM_USER`
(`SYSADMIN`, which owns them) and removes them from the state last. A run that stops halfway can
simply be repeated. `just tf apply` provisions everything again afterwards. A dropped database can
be restored with `UNDROP DATABASE` while its Time Travel retention lasts (30 days in `prd`). The
bootstrap objects from `init.sql`, the account parameters and your own key stay.
