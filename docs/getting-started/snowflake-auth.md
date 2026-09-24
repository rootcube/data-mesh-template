---
icon: material/key-variant
---

# Snowflake authentication

Everything in this repo (dbt, dlt, Dagster, the helper scripts) authenticates to Snowflake with
a **key pair**: no passwords in files, no MFA prompts on every run. Setting that up takes one
interactive login.

```bash
just snowflake setup
```

## What happens

The script asks for your account identifier (`<organization>-<account>`) and your login, then
walks through four steps:

1. **One-time interactive login.** Your browser opens on the Snowflake login page (SSO if the
   account has it, otherwise username, password and MFA). Prefer the terminal? Use
   `just snowflake setup --auth password`, which asks for your password and an MFA passcode
   (or sends a push notification when you leave it empty).
2. **Key pair.** An RSA 2048 key pair is written to `~/.snowflake/keys/<account>__<user>.p8`
   (private, owner-only permissions) and `<account>__<user>.pub`. Add `--passphrase` to encrypt
   the private key, `--key-name` to pick another file name.
3. **Registration.** The public key is set on your own user with
   `ALTER USER ... SET RSA_PUBLIC_KEY`. Snowflake lets every user do this for themselves unless
   an account policy says otherwise.
4. **Context, verification and `.env`.** You confirm role, warehouse, database and the prefix
   of your personal schemas. The defaults are your user's default role, warehouse and database
   in Snowflake, falling back to what `.env` already holds, and `DBT_<USERNAME>` for the prefix
   (`DBT_USERNAME` for `username@example.com`). Press Enter to keep a default, or type the
   values your administrator gave you. A fresh connection with the key proves it works, then
   the script writes everything to `.env`:

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

`dbt/profiles.yml`, the dlt destination and the Dagster resources all read exactly these
variables (`SnowflakeSettings` in `src/orchestrator/resources/snowflake.py` is the one reader),
so there is one place to look when a connection fails. Values are written without quotes; keep
it that way when you edit by hand.

!!! tip "Fewer questions"
    `--account` and `--user` skip the first two prompts, `--yes` skips the context confirmation.
    Use `--yes` only when your user's defaults in Snowflake are already the right role,
    warehouse and database; `just snowflake check` shows what was written.

## What the values mean

| Variable | Meaning |
|----------|---------|
| `ENVIRONMENT` | `dev`: you work in personal schemas. `prd` (and `tst`, `acc` once enabled) use the shared `_<LAYER>` schemas and are meant for deployed service users, not laptops. |
| `SNOWFLAKE_ROLE` | Your engineer role, `RL_<PROJECT>_DEV__ENG`. |
| `SNOWFLAKE_DATABASE` | The project's development database, `DB_<PROJECT>_DEV`, shared by every engineer. |
| `SNOWFLAKE_WAREHOUSE` | The project's default warehouse, `WH_<PROJECT>_DEV`. |
| `SNOWFLAKE_SCHEMA` | The prefix of your personal schemas. dlt loads into `<prefix>_SRC`; dbt builds `<prefix>_STG`, `<prefix>_INT`, `<prefix>_MRT` and `<prefix>_EXP`, seeds `<prefix>_REF`, run metadata `<prefix>_MTD`, stored test failures `<prefix>_TMP`. |

## Pointing `.env` at a project

`setup` derives your role, warehouse and database from the project roles granted to your user
(`RL_<PROJECT>_<ENV>__<PURPOSE>`), preferring the engineer role in development, and proposes a
personal schema prefix `DBT_<USERNAME>`. When a project is provisioned later, or when you move to
another one, rerun only that part; it connects with your key pair, so there is no login:

```bash
just snowflake context            # lists your project roles, asks, verifies, writes .env
just snowflake context --yes      # takes the defaults without asking
just snowflake context --role RL_OTHER_DEV__ENG
```

Restart `just start` afterwards: Dagster reads `.env` when it launches and injects those values
into every run, so values exported in your shell never reach a run.

## Check it

```bash
just snowflake check
```

connects with the key pair and prints your organization, account, user, role, warehouse,
database and schema, the schemas that already exist in the database, and the layer schemas
you will write to (`DBT_USERNAME_SRC, DBT_USERNAME_STG, ... (dev)`). Ad-hoc SQL works the same
way:

```bash
just snowflake query "SELECT CURRENT_USER(), CURRENT_ROLE()"
```

## Rotating or re-running

`setup` is safe to run again. It offers to keep an existing key (and just re-register it) or to
generate a new one. Snowflake holds two key slots per user; `--slot 2` registers into
`RSA_PUBLIC_KEY_2`, so you can rotate without a gap.

## When registration is not allowed

If the registration step fails with an insufficient-privileges error, an account policy blocks users from
setting their own key. The script stops there and does not write `.env`. Then:

1. Send your public key, `~/.snowflake/keys/<account>__<user>.pub`, to your platform
   administrator, who registers it for you (see [Onboarding](../administration/onboarding.md)).
2. Fill in the Snowflake block of `.env` by hand: `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER` (exactly
   as `CURRENT_USER()` returns it), `SNOWFLAKE_PRIVATE_KEY_PATH` (the absolute path of the
   `.p8` file), your role, warehouse, database and `SNOWFLAKE_SCHEMA=DBT_<USERNAME>`.
3. Run `just snowflake check`.

Next: [First run](first-run.md).
