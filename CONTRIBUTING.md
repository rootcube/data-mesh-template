# Contributing

Thanks for helping. The documentation site under `docs/` is the source of truth for how this
repository works; this page is the short version with links.

## Before you start

- Open an issue for anything larger than a small fix, so the approach can be discussed first.
- Run the project once: [Getting started](docs/getting-started/index.md). A free Snowflake trial
  is enough, see [Snowflake Trial Account setup](docs/administration/snowflake-trial-account-setup.md).

## Making a change

1. Branch from `main`, named `<type>/<short-topic>` (`feat/knmi-daily-aggregate`,
   `fix/knmi-hour-24-rollover`).
2. Follow the conventions: [Python style](docs/conventions/python-style.md),
   [SQL style](docs/conventions/sql-style.md), the [dbt style guide](docs/conventions/dbt-style-guide.md)
   and [Naming](docs/conventions/naming.md). The guides under `docs/development/` show how to add a
   dlt load, a dbt model or a project.
3. Run the checks before you push. They are the same ones CI runs:

    ```bash
    just fmt        # format Python and SQL
    just check      # lint, typecheck, tests, dbt parse, Dagster definitions, Terraform YAML
    just docs build --strict   # after editing docs/
    ```

    `just pre-commit-install` makes git run them on every commit.

4. Write [conventional commits](docs/conventions/git-workflow.md#commit-messages): `feat:`,
   `fix:`, `docs:`, `chore:`, ... release-please turns them into the changelog and the version,
   so never bump the version by hand.
5. Open a pull request against `main`. CI must be green and every review thread resolved before
   it can be merged; see [Git workflow](docs/conventions/git-workflow.md).

## What to keep in mind

- No credentials in files, ever. `SNOWFLAKE_*` come from `.env`, which is git-ignored.
- No personal names or logins in examples; use `username@example.com` and `DBT_USERNAME`.
- Every dbt model has its `_conf/<model>.yml` with column descriptions and tests, and references
  only the layer directly below.
- Update the affected page under `docs/` in the same pull request when a change alters documented
  behaviour.

## Security issues

See [SECURITY.md](SECURITY.md). Do not open a public issue for those.

## License

By contributing you agree that your contribution is licensed under the [GPL-3.0](LICENSE), like
the rest of the repository.
