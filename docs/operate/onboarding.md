---
icon: material/account-plus
---

# Onboarding

How a person or a service user gets access to a project, end to end. A user is a YAML file under
`terraform/config/users/` and Terraform grants it project roles. A person then registers a key
pair for themselves with `just sf setup`; for a service user you register it.

## A person

### 1. Describe the user

Create `terraform/config/users/<name>.yaml`. The file name is only the Terraform key, also in a
sub-folder, so two user files may not share a name; the starter ships one user file under
`terraform/config/users/` to copy from. `just sf bootstrap` writes the file for your own login
to `terraform/config/users/local/<login>.yaml`, which git ignores: that login exists in your
account only.

```yaml
login: "username@example.com"   # exact, as CURRENT_USER() returns it
name: "Username"
create: false                  # true creates the user (a person) with a one-time password
roles:
  - project: example           # file name under config/projects
    role: engineer             # file name under config/roles
    environments:              # environment keys; "*" or omitted = every environment of the project
      - development
```

The fields, from `terraform/config/_validation/schemas/user.schema.json`:

| Field | Required | Meaning |
|-------|----------|---------|
| `login` | yes | Snowflake login name. For SSO accounts this is the existing login. Unless `create` is `true`, the login must exist in the account: `just tf plan --all` checks and stops with a message naming the file otherwise. |
| `name` | no | Display name, stored as the user comment. |
| `email` | no | Only used when creating the user. |
| `create` | no | `false` (default): the login exists already, only the grants are made. `true`: create the user as a person, with a one-time password they must change at first login. Service users are created by hand ([below](#a-service-user)). |
| `schema_prefix` | no | Prefix of the personal schemas (`<PREFIX>_SRC`, ...) and of `SNOWFLAKE_SCHEMA` in `.env`. Default: `DBT_` plus the login before the `@`, non-alphanumerics as `_`, uppercased. |
| `disabled` | no | `true` removes the grants on the next apply, and drops the user if Terraform created it. |
| `roles` | yes | One entry per project role: `project`, `role`, optional `environments`. |

A grant only exists when the role is in the project's `roles` list and the environment in its
`environments` list; other combinations are skipped without an error. For the `example` project
that means `ingest`, `transform` or `engineer` in `development` or `production` (`analyst` is
optional and not listed).
Engineers get `engineer` in `development`, which becomes the account role `RL_EXAMPLE_DEV__ENG`.
That role also inherits `transform` and `ingest` in development, and `analyst` everywhere in a
project that lists it (`privileges.roles` in `terraform/config/roles/engineer.yaml`), so one
grant is enough.

### 2. Apply

```bash
just tf-validate-config
just tf plan --all
just tf apply --all
```

`just tf output snowflake-account -s account -- -json user_role_grants` shows the roles per login,
and `just tf output snowflake-project -s <project>-dev -- -json personal_schemas` the personal
schemas the apply created (step 4). For a
created person, hand out the password from
`just tf output snowflake-account -s account -- -json initial_passwords`; Snowflake
forces a change at the first login.

!!! note "Defaults on the user"
    Terraform sets a default role, warehouse and database only on the users it creates
    (`create: true`): those of their first role assignment. `just sf setup` does not rely on
    them: it derives role, warehouse and database from the project roles granted to the login
    (the engineer role in development first) and never stores a system role such as
    `ACCOUNTADMIN`. A person without a granted project role gets them empty, with a warning
    that points here; once your apply has granted the role, they run `just sf context`.

### 3. What the person runs

```bash
git clone https://github.com/rootcube/data-mesh-template.git && cd data-mesh-template
just init
just sf setup
just sf check
just start
```

`just sf setup` logs in once, registers a key pair on the person's own user, verifies it and
writes their `.env`. Their side of it, step by step and including what lands in `.env`:
[Snowflake authentication](../start/snowflake-auth.md).

### 4. Personal schemas in development

The engineer role has a `personal` block in `terraform/config/roles/engineer.yaml`
(`environments: [dev]`). For every user who holds it there, the apply in step 2 creates one
schema per project layer in `DB_<PROJECT>_DEV` (`terraform/components/snowflake-project/personal.tf`): `DBT_USERNAME_SRC`,
`DBT_USERNAME_REF`, `DBT_USERNAME_STG`, `DBT_USERNAME_INT`, `DBT_USERNAME_MRT`,
`DBT_USERNAME_EXP`, `DBT_USERNAME_MTD` and `DBT_USERNAME_TMP`, plus the person's own load stage
`DBT_USERNAME_SRC.ST_DEFAULT` (`terraform/components/snowflake-project/stages.tf`). `SYSADMIN` owns them like every other
schema; the engineer role gets the privileges of the block's access tier (`access: full`, see
[Access](../understand/access.md)) on them directly (current and future grants), but no
`CREATE SCHEMA`: dlt and dbt use the schemas, they never create them. So the apply has to come
before the person's first dlt load or dbt run.

The prefix is `schema_prefix` from the user file, or `DBT_` plus the login before the `@`, the
same rule `just sf setup` uses to propose `SNOWFLAKE_SCHEMA`. To change it, set
`schema_prefix` and apply, then update `SNOWFLAKE_SCHEMA` in the person's `.env`.

Several engineers share the one development database without stepping on each other. The rule
lives in `SnowflakeSettings.schema_for_layer()` and `dbt_common.generate_schema_name`; every
environment other than `dev` ignores the prefix and uses the provisioned `_<LAYER>` schemas.
The privileges go to the shared engineer role, not to the person, so engineers can technically
read and write each other's personal schemas.

## Key registration fallback

`ALTER USER ... SET RSA_PUBLIC_KEY` on your own user is allowed by default. If an account
policy blocks it, `just sf setup` stops at the registration step with the Snowflake error and does not
write `.env`. Then:

1. The person sends you `~/.snowflake/keys/<account>__<user>.pub`.
2. Register it as `SECURITYADMIN`, with the base64 body of the file (the lines between the
   `-----BEGIN` and `-----END` markers, joined into one string):

    ```sql
    ALTER USER "username@example.com" SET RSA_PUBLIC_KEY = '<public key body>';
    ```

3. The person fills in the Snowflake block of `.env` by hand (account, login, private key
   path, role, warehouse, database and `SNOWFLAKE_SCHEMA=DBT_<USERNAME>`) and runs
   `just sf check`.

`RSA_PUBLIC_KEY_2` is the second slot, for rotating a key without a gap.

## A service user

Deployed environments run dlt and dbt as system users: the `ingest` role
(`RL_<PROJECT>_<ENV>__ING`) for dlt, the `transform` role (`RL_<PROJECT>_<ENV>__TFM`) for dbt.
Terraform creates them, `TYPE = SERVICE` with a key pair and no password, from a user file with
`type: service`:

1. Generate the key pair. `keygen` never logs in; it writes the pair under `~/.snowflake/keys/`
   and prints the public key body:

    ```bash
    just sf keygen EXAMPLE_PRD_TRANSFORM
    ```

2. Describe the user, with that body and the roles it holds:

    ```yaml
    login: "EXAMPLE_PRD_TRANSFORM"
    name: "dbt in example production"
    type: service
    rsa_public_key: "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA..."
    roles:
      - project: example
        role: transform
        environments: [production]
    ```

    The login is upper case, and a service user holds system roles only (`ingest`, `transform`);
    `just tf-validate-config` checks both. The file goes under the git-ignored
    `terraform/config/users/local/` while the key pair is yours alone, and under
    `terraform/config/users/` once administrators share the account
    ([Service users](kubernetes.md#service-users)).
3. `just tf apply --all`: the `account` stack creates the user, the project stack grants the role.

The private key (`~/.snowflake/keys/EXAMPLE_PRD_TRANSFORM.p8`) is what the deployment signs in
with. [Dagster on Kubernetes](kubernetes.md) takes it from there into a Kubernetes secret and
gives each code location this environment; any other runtime needs the same:

```dotenv
ENVIRONMENT=prd
SNOWFLAKE_ACCOUNT=MYORG-MYACCOUNT
SNOWFLAKE_USER=EXAMPLE_PRD_TRANSFORM
SNOWFLAKE_PRIVATE_KEY_PATH=/path/to/EXAMPLE_PRD_TRANSFORM.p8
SNOWFLAKE_PRIVATE_KEY_PASSPHRASE=
SNOWFLAKE_ROLE=RL_EXAMPLE_PRD__TFM
SNOWFLAKE_WAREHOUSE=WH_EXAMPLE_PRD
SNOWFLAKE_DATABASE=DB_EXAMPLE_PRD
SNOWFLAKE_SCHEMA=
```

With `ENVIRONMENT=prd` the layer schemas are the provisioned `_SRC`, `_STG`, ...; dbt puts
anything without a layer into `_TMP`, its fallback when `SNOWFLAKE_SCHEMA` is empty.

!!! note "Warehouse grants of the system roles"
    `ingest` and `transform` receive warehouse privileges on the `default` compute and on their
    own `ingest` and `transform` computes (`privileges.computes` in their role files). Grants are
    only created for computes the project lists. The example project lists both, so they also
    get dedicated warehouses (`WH_EXAMPLE_<ENV>__ING_S` and `__ING_M`, `WH_EXAMPLE_<ENV>__TFM_S`,
    `__TFM_M` and `__TFM_L`); a project with `computes: [default]` runs them on
    `WH_<PROJECT>_<ENV>`.

## Removing access

Set `disabled: true` in the user's file, or delete the file, and `just tf apply --all`. The grants
disappear; a user Terraform created is dropped as well. So are the person's personal schemas in
the development database, with everything in them.
