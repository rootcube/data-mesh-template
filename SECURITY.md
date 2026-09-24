# Security policy

## Reporting a vulnerability

Please do not open a public issue for a security problem.

Report it privately through GitHub's
[private vulnerability reporting](https://github.com/rootcube/data-mesh-template/security/advisories/new),
which is enabled for this repository. If that does not work for you, email
[info@rootcube.com](mailto:info@rootcube.com) with "security" in the subject.

Include what you found, how to reproduce it and, if you can, the impact you expect. You will get an
acknowledgement within five working days and a follow-up once the report has been assessed.

## Scope

This repository is a starter template: the code runs in your own Snowflake account with your own
credentials. Things that are in scope:

- Anything that makes the tooling leak or store credentials (the `.env` handling, the key-pair
  setup in `scripts/snowflake.py`, the Terraform provider configuration).
- Grants provisioned by `terraform/` that give a role more than the platform model describes.
- Dependencies with known vulnerabilities that Dependabot has not caught.

Out of scope: the security of your Snowflake account, the KNMI API, and the upstream tools
(Dagster, dlt, dbt, Terraform); report those to their maintainers.

## Supported versions

Only the latest release on `main` receives fixes.
