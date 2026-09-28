| Step | Command | Catches |
|------|---------|---------|
| Format | `just fmt` | ruff format and lint fixes, `sqlfluff fix models` in every project under `dbt/` |
| Wire-up | `just validate` | Every code location loads: import errors, broken `defs.yaml`, missing `dbt deps`; the dbt locations read the manifest of the last `dbt parse`; the dlt and dbt asset keys still line up |
| Behaviour | `just test`, `just dbt build --select <model>+` | Python unit tests; dbt models, seeds and data tests in your personal schemas |
| What CI does, minus the Terraform CLI | `just check` | `lint` + `typecheck` + `test`, then `dbt parse --target local` in every project (as is, and with `--use-v2-parser`), `dagster definitions validate`, the Terraform YAML validation, the docs fence check and the strict docs build |
