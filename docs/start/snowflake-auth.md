---
icon: material/key-variant
---

# Snowflake authentication

Everything in this repo (dbt, dlt, Dagster, the helper scripts) authenticates to Snowflake with a
**key pair**: no passwords in files, no MFA prompt on every run. Setting that up costs one
interactive login.

```bash
just sf setup
```

## What happens

The script asks for your account identifier (`<organization>-<account>`) and your login, then
walks through four steps:

1. **One-time interactive login.** Your browser opens on the Snowflake login page (SSO if the
   account has it, otherwise username, password and MFA). Prefer the terminal? Use
   `just sf setup --auth password`, which asks for your password and an MFA passcode, or sends a
   push notification when you leave the passcode empty.
2. **Key pair.** An RSA 2048 key pair is written to `~/.snowflake/keys/<account>__<user>.p8`
   (private, owner-only permissions) and `<account>__<user>.pub`. Add `--passphrase` to encrypt
   the private key, `--key-name` to pick another file name.
3. **Registration.** The public key is set on your own user with
   `ALTER USER ... SET RSA_PUBLIC_KEY`. Snowflake lets every user do this for themselves unless
   an account policy says otherwise. When the slot already holds this key, the script says so and
   skips it. When it holds another one it asks first: yes by default for a key this run generated
   (a rotation), no by default for an unexpected one (registered from another machine? copy that
   machine's key files to `~/.snowflake/keys` instead, or use `--slot 2`).
4. **Context, verification and `.env`.** You confirm role, warehouse, database and the prefix of
   your personal schemas. The first three come from the project roles granted to you (see
   [Pointing `.env` at a project](#pointing-env-at-a-project)), never from the session you logged
   in with; without a project role they stay empty, and the script tells you to ask your
   administrator and then run `just sf context`. The prefix defaults to `DBT_<USERNAME>`
   (`DBT_USERNAME` for `username@example.com`), or to the `schema_prefix` of your file under
   `terraform/config/users/`: the prefix Terraform created your schemas with, so keep it. The
   prompt asks again for a prefix that is not letters, digits and `_` starting with a letter, or
   that is the bare placeholder `DBT`; a `tst`, `acc` or `prd` role gets no prefix. Press Enter to
   keep a default. A fresh connection with the new key proves it works, and then the script writes
   `.env`:

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
variables (`SnowflakeSettings` in `src/orchestrator/resources/snowflake.py` is the one reader), so
a failed connection has one place to look. What each value means, and how a prefix turns into
schema names: [Environment variables](../reference/environment-variables.md). `.env` and the
private key are readable by you only (mode 600, or an owner-only ACL on Windows).

!!! tip "Fewer questions"
    `--account` and `--user` skip the first two prompts; `--yes` skips the context confirmation
    and takes the defaults from your project roles.

## Check it

```bash
just sf check
```

connects with the key pair and prints your organization, account, user, role, warehouse, database
and schema, the schemas that already exist in the database, and the layer schemas you will write
to (`DBT_USERNAME_SRC, DBT_USERNAME_STG, ... (dev)`). Ad-hoc SQL works the same way:

```bash
just sf query "SELECT CURRENT_USER(), CURRENT_ROLE()"
```

## Pointing `.env` at a project

`setup` derives your role, warehouse and database from the project roles granted to your user
(`RL_<PROJECT>_<ENV>__<PURPOSE>`), preferring the engineer role in development. When a project is
provisioned later, or when you move to another one, rerun only that part. It connects with your
key pair, so there is no login:

```bash
just sf context            # lists your project roles, asks, verifies, writes .env
just sf context --yes      # takes the defaults without asking
just sf context --role RL_OTHER_DEV__ENG
```

Restart `just start` afterwards: Dagster reads `.env` when it launches and injects those values
into every run, so a value exported in your shell never reaches a run.

## Rotating or re-running

`setup` is safe to run again. It offers to keep an existing key (and only re-register it) or to
generate a new one. A new key replaces the old files once Snowflake has accepted it; the old ones
stay behind as `.p8.bak` and `.pub.bak`. Snowflake holds two key slots per user, and `--slot 2`
registers into `RSA_PUBLIC_KEY_2`, which is how you rotate without a gap.

Replacing the key in the slot it already uses is the normal rotation, so step 3 says which key it
is about to overwrite and defaults to yes. The warning about another machine (default no) is only
for a key this run did not generate.

`just sf keygen <name> --force` rotates a service user's key the same way: the pair it replaces
stays as `.p8.bak` and `.pub.bak`, and Snowflake keeps signing that user in with the old public
key until you register the new one.

## When registration is not allowed

If the registration step fails with an insufficient-privileges error, an account policy blocks
users from setting their own key. The script stops there and does not write `.env`. Then:

1. Send your public key, `~/.snowflake/keys/<account>__<user>.pub`, to your platform
   administrator, who registers it for you (see [Onboarding](../operate/onboarding.md)).
2. Fill in the Snowflake block of `.env` by hand: `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER` (exactly
   as `CURRENT_USER()` returns it), `SNOWFLAKE_PRIVATE_KEY_PATH` (the absolute path of the `.p8`
   file), your role, warehouse, database and `SNOWFLAKE_SCHEMA=DBT_<USERNAME>`.
3. Run `just sf check`.

Next: [First run](first-run.md).
