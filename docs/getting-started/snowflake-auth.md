---
icon: material/key-variant
---

# Snowflake authentication

Everything in this repo (dbt, dlt, Dagster, the helper scripts) authenticates to Snowflake with
a **key pair**: no passwords in files, no MFA prompts on every run. Setting that up takes one
interactive login.

```bash
just sf setup
```

## What happens

The script asks for your account identifier (`<organization>-<account>`) and your login, then
walks through four steps:

1. **One-time interactive login.** Your browser opens on the Snowflake login page (SSO if the
   account has it, otherwise username, password and MFA). Prefer the terminal? Use
   `just sf setup --auth password`, which asks for your password and an MFA passcode
   (or sends a push notification when you leave it empty).
2. **Key pair.** An RSA 2048 key pair is written to `~/.snowflake/keys/<account>__<user>.p8`
   (private, owner-only permissions) and `<account>__<user>.pub`. Add `--passphrase` to encrypt
   the private key, `--key-name` to pick another file name.
3. **Registration.** The public key is set on your own user with
   `ALTER USER ... SET RSA_PUBLIC_KEY`. Snowflake lets every user do this for themselves unless
   an account policy says otherwise. When the slot already holds this key, the script says so
   and skips it; when it holds another one (registered from another machine?), it warns and
   asks before replacing it (default No: copy that machine's key files to
   `~/.snowflake/keys` instead, or use `--slot 2`).
4. **Context, verification and `.env`.** You confirm role, warehouse, database and the prefix
   of your personal schemas. Role, warehouse and database come from the project roles granted
   to you (see [Pointing `.env` at a project](#pointing-env-at-a-project)), never from the
   session you logged in with; without a project role they stay empty, and the script tells
   you to ask your administrator and then run `just sf context`. The prefix defaults to
   `DBT_<USERNAME>` (`DBT_USERNAME` for `username@example.com`, or the `schema_prefix` of your
   file under `terraform/config/users/`): the prefix Terraform created your schemas with, so
   keep it. The prompt asks again for a prefix that is not letters, digits and `_` starting
   with a letter, or that is the bare placeholder `DBT`; a `tst`, `acc` or `prd` role gets no
   prefix. Press Enter to keep a default, or type the
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
so there is one place to look when a connection fails. Values are written bare, or in single
quotes when they hold special characters (a passphrase, say); `just` and python-dotenv strip
those quotes. `.env` and the private key are readable by you only (mode 600, or an owner-only
ACL on Windows).

!!! tip "Fewer questions"
    `--account` and `--user` skip the first two prompts, `--yes` skips the context confirmation
    and takes the defaults from your project roles; `just sf check` shows what was written.

## What the values mean

| Variable | Meaning |
|----------|---------|
| `ENVIRONMENT` | `dev`: you work in personal schemas. `prd` (and `tst`, `acc` once enabled) use the shared `_<LAYER>` schemas and are meant for deployed service users, not laptops. |
| `SNOWFLAKE_ROLE` | Your engineer role, `RL_<PROJECT>_DEV__ENG`. |
| `SNOWFLAKE_DATABASE` | The project's development database, `DB_<PROJECT>_DEV`, shared by every engineer. |
| `SNOWFLAKE_WAREHOUSE` | The project's default warehouse, `WH_<PROJECT>_DEV`. |
| `SNOWFLAKE_SCHEMA` | The prefix of your personal schemas, which Terraform provisions for you. dlt loads into `<prefix>_SRC` (through its stage `<prefix>_SRC.ST_DEFAULT`); dbt builds `<prefix>_STG`, `<prefix>_INT`, `<prefix>_MRT` and `<prefix>_EXP`, seeds `<prefix>_REF`, run metadata `<prefix>_MTD`, stored test failures `<prefix>_TMP`. |

## Pointing `.env` at a project

`setup` derives your role, warehouse and database from the project roles granted to your user
(`RL_<PROJECT>_<ENV>__<PURPOSE>`), preferring the engineer role in development, and proposes a
personal schema prefix `DBT_<USERNAME>`. When a project is provisioned later, or when you move to
another one, rerun only that part; it connects with your key pair, so there is no login:

```bash
just sf context            # lists your project roles, asks, verifies, writes .env
just sf context --yes      # takes the defaults without asking
just sf context --role RL_OTHER_DEV__ENG
```

Restart `just start` afterwards: Dagster reads `.env` when it launches and injects those values
into every run, so values exported in your shell never reach a run.

## Check it

```bash
just sf check
```

connects with the key pair and prints your organization, account, user, role, warehouse,
database and schema, the schemas that already exist in the database, and the layer schemas
you will write to (`DBT_USERNAME_SRC, DBT_USERNAME_STG, ... (dev)`). Ad-hoc SQL works the same
way:

```bash
just sf query "SELECT CURRENT_USER(), CURRENT_ROLE()"
```

## Rotating or re-running

`setup` is safe to run again. It offers to keep an existing key (and just re-register it) or to
generate a new one. A new key replaces the old files only once Snowflake has accepted it; the
old ones stay as `.p8.bak` and `.pub.bak`. Snowflake holds two key slots per user; `--slot 2`
registers into `RSA_PUBLIC_KEY_2`, so you can rotate without a gap.

## When registration is not allowed

If the registration step fails with an insufficient-privileges error, an account policy blocks users from
setting their own key. The script stops there and does not write `.env`. Then:

1. Send your public key, `~/.snowflake/keys/<account>__<user>.pub`, to your platform
   administrator, who registers it for you (see [Onboarding](../administration/onboarding.md)).
2. Fill in the Snowflake block of `.env` by hand: `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER` (exactly
   as `CURRENT_USER()` returns it), `SNOWFLAKE_PRIVATE_KEY_PATH` (the absolute path of the
   `.p8` file), your role, warehouse, database and `SNOWFLAKE_SCHEMA=DBT_<USERNAME>`.
3. Run `just sf check`.

Next: [First run](first-run.md).
