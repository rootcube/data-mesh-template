---
icon: material/account-plus
---

# Onboarding

How a person or a service user gets access to a project, end to end. Users are YAML files under
`terraform/config/users/`; Terraform grants them project roles. A person then registers a key
pair for themselves with `just snowflake setup`; for a service user you register it.

## A person

### 1. Describe the user

Create `terraform/config/users/<name>.yaml`. The file name is only the Terraform key; the
starter ships one user file under `terraform/config/users/` to copy from:

```yaml
login: "username@example.com"   # exact, as CURRENT_USER() returns it
name: "Username"
type: "person"
create: false                  # true creates the user with a one-time password
roles:
  - project: example           # file name under config/projects
    role: engineer             # file name under config/roles
    environments:              # environment keys; "*" or omitted = every environment of the project
      - development
```

The fields, from `terraform/config/_validation/schemas/user.schema.json`:

| Field | Required | Meaning |
|-------|----------|---------|
| `login` | yes | Snowflake login name. For SSO accounts this is the existing login. |
| `name` | no | Display name, stored as the user comment. |
| `email` | no | Only used when creating the user. |
| `type` | no | `person` (default) or `service`. |
| `create` | no | `false` (default): the login exists already, only the grants are made. `true`: create the user; persons get a one-time password they must change at first login. |
| `disabled` | no | `true` removes the grants on the next apply, and drops the user if Terraform created it. |
| `roles` | yes | One entry per project role: `project`, `role`, optional `environments`. |

A grant only exists when the role is in the project's `roles` list and the environment in its
`environments` list; other combinations are skipped without an error. For the `example` project
that means `ingest`, `transform`, `engineer` or `analyst` in `development` or `production`.
Engineers get `engineer` in `development`, which becomes the account role `RL_EXAMPLE_DEV__ENG`.
That role also inherits `transform` and `ingest` in development and `analyst` everywhere
(`privileges.roles` in `terraform/config/roles/engineer.yaml`), so one grant is enough.

### 2. Apply

```bash
just tf-validate-config
just tf plan
just tf apply
```

`just tf output -json user_role_grants` shows the roles per login. For created persons, hand
out the password from `just tf output -json initial_passwords`; Snowflake forces a change at
the first login.

!!! note "Defaults on the user"
    Terraform sets no default role, warehouse or database on the user. `just snowflake setup`
    proposes whatever Snowflake reports for the login, so tell the person the three names
    (`RL_EXAMPLE_DEV__ENG`, `WH_EXAMPLE_DEV` and `DB_EXAMPLE_DEV` in the starter project), or set
    them once with `ALTER USER ... SET DEFAULT_ROLE = ... DEFAULT_WAREHOUSE = ... DEFAULT_NAMESPACE = ...`.

### 3. What the person runs

```bash
git clone git@github.com:rootcube/data-mesh-template.git && cd data-mesh-template
just init
just snowflake setup
just snowflake check
just start
```

`just snowflake setup` logs in once (browser SSO, or `--auth password`), writes an RSA key pair
to `~/.snowflake/keys/`, registers the public key on the person's own user with
`ALTER USER ... SET RSA_PUBLIC_KEY`, verifies the key-pair login and writes `.env`. The engineer
side of this is [Snowflake authentication](../getting-started/snowflake-auth.md).

### 4. What ends up in their `.env`

```dotenv
ENVIRONMENT=dev
SNOWFLAKE_ACCOUNT=MYORG-MYACCOUNT
SNOWFLAKE_USER=USERNAME@EXAMPLE.COM
SNOWFLAKE_PRIVATE_KEY_PATH=/Users/username/.snowflake/keys/myorg-myaccount__username_example.com.p8
SNOWFLAKE_PRIVATE_KEY_PASSPHRASE=
SNOWFLAKE_ROLE=RL_EXAMPLE_DEV__ENG
SNOWFLAKE_WAREHOUSE=WH_EXAMPLE_DEV
SNOWFLAKE_DATABASE=DB_EXAMPLE_DEV
SNOWFLAKE_SCHEMA=DBT_USERNAME
```

### 5. Personal schemas in development

The engineer role holds `CREATE SCHEMA` on `DB_<PROJECT>_DEV` (`privileges.database.dev` in
`terraform/config/roles/engineer.yaml`). dlt and dbt create `<SNOWFLAKE_SCHEMA>_<LAYER>` schemas
on demand: `DBT_USERNAME_SRC` on the first load, `DBT_USERNAME_STG` and the other layers on the
first `dbt build`, `DBT_USERNAME_MTD` for run metadata. Several engineers share the one
development database without stepping on each other. The rule lives in
`SnowflakeSettings.schema_for_layer()` and `dbt_common.generate_schema_name`; every environment
other than `dev` ignores the prefix and uses the provisioned `_<LAYER>` schemas.

Nothing is provisioned for personal schemas. They are owned by `RL_<PROJECT>_DEV__ENG`, the
role that created them, and anyone with that role can drop them when a person leaves.

## Key registration fallback

`ALTER USER ... SET RSA_PUBLIC_KEY` on your own user is allowed by default. If an account
policy blocks it, `just snowflake setup` stops at the registration step with the Snowflake error and does not
write `.env`. Then:

1. The person sends you `~/.snowflake/keys/<account>__<user>.pub`.
2. Register it as `SECURITYADMIN`, with the base64 body of the file (the lines between the
   `-----BEGIN` and `-----END` markers, joined into one string):

    ```sql
    ALTER USER "username@example.com" SET RSA_PUBLIC_KEY = '<public key body>';
    ```

3. The person fills in the Snowflake block of `.env` by hand (account, login, private key
   path, role, warehouse, database and `SNOWFLAKE_SCHEMA=DBT_<USERNAME>`) and runs
   `just snowflake check`.

`RSA_PUBLIC_KEY_2` is the second slot, for rotating a key without a gap.

## A service user

Deployed environments run dlt and dbt as system users: the `ingest` role
(`RL_<PROJECT>_<ENV>__ING`) for dlt, the `transform` role (`RL_<PROJECT>_<ENV>__TFM`) for dbt.

1. Create the user by hand, as `SECURITYADMIN` (Terraform only creates persons):

    ```sql
    CREATE USER example_prd_transform TYPE = SERVICE COMMENT = 'dbt in example production';
    ```

2. Grant its roles through a user file with `create: false`:

    ```yaml
    login: "example_prd_transform"
    name: "dbt in example production"
    create: false
    roles:
      - project: example
        role: transform
        environments: [production]
    ```

    then `just tf apply`.
3. Generate a key pair and register it. `keygen` never logs in; it writes the pair under
   `~/.snowflake/keys/` and prints the public key body:

    ```bash
    just snowflake keygen example_prd_transform
    ```

    Then, as `SECURITYADMIN`:

    ```sql
    ALTER USER example_prd_transform SET RSA_PUBLIC_KEY = '<public key body>';
    ```

4. The deployment gets the private key (`~/.snowflake/keys/example_prd_transform.p8`) and this
   environment:

    ```dotenv
    ENVIRONMENT=prd
    SNOWFLAKE_ACCOUNT=MYORG-MYACCOUNT
    SNOWFLAKE_USER=example_prd_transform
    SNOWFLAKE_PRIVATE_KEY_PATH=/path/to/example_prd_transform.p8
    SNOWFLAKE_PRIVATE_KEY_PASSPHRASE=
    SNOWFLAKE_ROLE=RL_EXAMPLE_PRD__TFM
    SNOWFLAKE_WAREHOUSE=WH_EXAMPLE_PRD
    SNOWFLAKE_DATABASE=DB_EXAMPLE_PRD
    SNOWFLAKE_SCHEMA=
    ```

    With `ENVIRONMENT=prd` the layer schemas are the provisioned `_SRC`, `_STG`, ...; dbt puts
    anything without a layer into `_TMP`, the profile's default when `SNOWFLAKE_SCHEMA` is
    empty.

!!! note "Warehouse grants of the system roles"
    `ingest` and `transform` receive warehouse privileges on the `default` compute and on their
    own `ingest` and `transform` computes (`privileges.computes` in their role files). Grants are
    only created for computes the project lists, so with `computes: [default]` they use
    `WH_EXAMPLE_<ENV>`; add `ingest` and `transform` to the project to give them dedicated
    warehouses (`WH_EXAMPLE_<ENV>__ING_S`, `WH_EXAMPLE_<ENV>__TFM_S`).

## Removing access

Set `disabled: true` in the user's file, or delete the file, and `just tf apply`. The grants
disappear; a user Terraform created is dropped as well. Personal schemas in the development
database stay until someone with `RL_<PROJECT>_DEV__ENG` drops them.
