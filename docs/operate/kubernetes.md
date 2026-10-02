---
icon: material/kubernetes
---

# Dagster on Kubernetes

`dagster dev` runs Dagster on your laptop for development. A deployed environment (`prd`, or
`tst` and `acc` when a project has them) runs it on Kubernetes: the official
[Dagster Helm chart](https://docs.dagster.io/deployment/oss/deployment-options/kubernetes/deploying-to-kubernetes),
deployed by Terraform through Atmos like the Snowflake provisioning, one stack per environment
(`terraform/stacks/deployments/dagster/<env>.yaml`, stack `dagster-<env>`). The starter targets a
local [k3d](https://k3d.io) cluster; a hosted cluster is the same stack with another
`kube_context` and image (see [Beyond the laptop](#beyond-the-laptop)).

## What runs

In the namespace `dagster-<env>`:

| Pod | What | Signs in to Snowflake as |
|-----|------|--------------------------|
| `dagster-webserver` | the UI | nobody |
| `dagster-daemon` | schedules, sensors, run queue | nobody |
| `dagster-postgresql-0` | Postgres: runs, event logs, schedules (a persistent volume) | nobody |
| `dlt` | code server of `orchestrator.locations.dlt.definitions` | the ingest service user of `dlt_project` (`RL_<PROJECT>_<ENV>__ING`) |
| `dbt-<project>` | code server of `orchestrator.locations.dbt.dbt_<project>.definitions`, one per project in the environment | that project's transform service user (`RL_<PROJECT>_<ENV>__TFM`) |
| a pod per run | `dagster api execute_run` in the same image | the identity of the location that launched it |

The code locations are named `dlt` and `dbt-<project>` (Kubernetes names allow no `_`); jobs,
schedules and sensors keep the names they have locally. `ENVIRONMENT` is the stack's environment,
so schedules and sensors start **running**: the daily loads and the hourly freshness chain fire by
themselves for as long as the cluster runs, against `DB_<PROJECT>_<ENV>`.

## Prerequisites

Once per machine. uv manages the Python side (the image is built from `uv.lock`), but none of
this is Python:

- **A Docker engine** with BuildKit, for the `Dockerfile`'s cache mounts: Docker Desktop on
  Windows and macOS, Docker Engine from your distribution on Linux. On Windows it needs WSL2:
  `wsl --install --no-distribution` in an administrator shell, then a reboot. Docker Desktop is
  free for personal use and small companies; from 250 people or $10M revenue it needs a paid
  subscription. [Rancher Desktop](https://rancherdesktop.io) is the free alternative
  (`winget install SUSE.RancherDesktop`, or `brew install rancher`), started with *Kubernetes*
  switched off and the *dockerd (moby)* engine.
- **k3d and kubectl**: the local cluster and its CLI.
- **Terraform and Atmos**, as for the [Snowflake provisioning](snowflake-provisioning.md), with
  the `TF_VAR_SNOWFLAKE_*` block in `.env`.

`just install k8s` handles the first two: Docker Desktop on Windows (winget) and macOS
(Homebrew), k3d and kubectl. Docker Desktop asks for administrator rights while it installs;
start it once afterwards to accept its terms, and sign out and in when it asks. On Windows
without WSL2 it installs no Docker engine and prints the WSL2 command instead; run it again after
the reboot. On Linux it points to the Docker Engine install. `just install docker`, `k3d` and
`kubectl` do one each.

## Service users

Every code location signs in with a key pair of a Snowflake service user (`TYPE = SERVICE`, no
password). Terraform creates them from their user file, the project stacks grant their roles:

1. Generate the key pair; `keygen` never logs in, it writes
   `~/.snowflake/keys/<LOGIN>.p8` and `.pub` and prints the public key body:

    ```bash
    just sf keygen EXAMPLE_PRD_INGEST
    just sf keygen EXAMPLE_PRD_TRANSFORM
    ```

2. A user file per service user, with `type: service` and that body:

    ```yaml title="terraform/config/users/local/example_prd_transform.yaml (new file)"
    # yaml-language-server: $schema=../../_validation/schemas/user.schema.json
    login: "EXAMPLE_PRD_TRANSFORM"
    name: "dbt in example production"
    type: service
    rsa_public_key: "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA..."
    roles:
      - project: example
        role: transform
        environments: [production]
    ```

    and the same for `EXAMPLE_PRD_INGEST` with `role: ingest`. Logins are upper case; a service
    user holds system roles only (`just tf-validate-config` checks both). `users/local/` is
    git-ignored, and these files belong there for as long as the key pairs are yours alone:
    whoever applies a checkout creates the service users its user files name, with the public
    keys in them, so a committed file gives every such account a user only you can sign in as.
    Commit them under `config/users/` when several administrators share one account and its
    states ([Stacks and state](snowflake-provisioning.md#stacks-and-state)); a repository that
    others start their own platform from, like the starter itself, carries none.
3. `just tf apply --all`: the `account` stack creates the users, `example-prd` grants the roles.

The private keys stay in `~/.snowflake/keys/`. The Dagster stack reads them from there into one
Kubernetes secret per service user, as write-only values: they reach the cluster, never the
Terraform state.

## Deploy

The Dagster stack is a deployment, not provisioning: it needs its cluster running and the service
users' private keys on the machine. `just tf <command> --all` therefore leaves it out, so the
Snowflake stacks plan and apply on a machine that has neither. `just k8s deploy` applies the
stack, and `just tf plan dagster -s dagster-prd` plans it by name.

```bash
just k8s up        # create (or start) the k3d cluster `dagster`, kube context k3d-dagster
just k8s deploy    # build the image, apply the stack dagster-prd, restart the code servers
just k8s ui        # the webserver on http://localhost:3000, until Ctrl+C
```

`just k8s deploy` builds `dagster-starter:local` from the `Dockerfile`, imports it into the
cluster (`just k8s build` does just that), and applies `dagster` in `dagster-prd` through Atmos,
asking for confirmation as any apply does. The first apply takes a few minutes: the cluster
pulls the chart's images and Postgres initializes its volume. `kubectl -n dagster-prd get pods`
shows them; every pod should be `Running` and ready. Another environment is another stack,
`just k8s deploy dagster-<env>`.

After a code change, `just k8s deploy` again: the image keeps its tag, so the recipe restarts the
code servers to pick up the new build. `just k8s down` stops the cluster and keeps everything in
it, run history included; `k3d cluster delete dagster` removes it all.

## How it fits together

**The image** (`Dockerfile`) keeps the checkout layout under `/app`, since the code finds `dbt/`
and `.dlt/` relative to the repository root, and installs it with uv: the locked dependencies
without the `dev` group, plus the `deploy` group (`dagster-k8s`, `dagster-postgres`, which the run
pods need). It runs `dbt deps` and `dbt parse` when it is built, because the dbt code locations
read `target/manifest.json` when they load and only `dagster dev` parses on the fly. One image
serves every environment. `.dockerignore` is an allowlist: `.env`, keys, Terraform states and
the local Dagster, dlt and DuckDB state never enter the build.

**The stack** (`terraform/components/dagster`) derives everything from `config/`: a code location
per project in the environment, and for each its service user, role, warehouse and database,
passed as the `SNOWFLAKE_*` variables the code reads anyway. The warehouse is the first size of
the location's own compute profile, `ingest` for `dlt` and `transform` for `dbt-<project>`
(`WH_EXAMPLE_PRD__ING_S`, `WH_EXAMPLE_PRD__TFM_S`), when the project lists that profile, and
`WH_<PROJECT>_<ENV>` when it does not. `includeConfigInLaunchedRuns` gives
every run pod the environment, secret and volume of its location. The chart's Postgres gets a
generated password before it first creates its volume. The chart version equals the `dagster`
version in `uv.lock`; upgrade both together.

**Freshness** needs nothing shared between pods but the instance: the freshness job records
what `dbt source freshness` found as observations in the event log (Postgres here), and the sensor
reads them back ([Orchestration](../understand/orchestration.md#schedules-and-sensors)).

## Day to day

| Task | How |
|------|-----|
| Deploy new code | `just k8s deploy` |
| See a run's output | The chart stores no compute logs, so the UI shows none: `kubectl -n dagster-prd get pods` lists the run pods, `kubectl -n dagster-prd logs <pod>` prints one |
| Replace a service user's key | `just sf keygen <LOGIN> --force`, its new public key in the user file, `just tf apply snowflake-account -s account`; then raise `key_revision` in the stack (the key is write-only, so Terraform only sends it again on a new revision) and `just k8s deploy` |
| Add a project | Its stack manifests ([Adding a project](../build/adding-projects.md)), its two service users, `just tf apply --all`, `just k8s deploy`: the stack adds its `dbt-<project>` location |
| Reach the UI | `just k8s ui`; there is no ingress and no login in front of it |

| Symptom | Cause |
|---------|-------|
| `ErrImageNeverPulled` / `ImagePullBackOff` on a code server | The image is not in the cluster: `just k8s build` |
| `No service user ... holds the transform of example` on plan | A code location has no service user in `config/users` for this environment |
| `No private key ~/.snowflake/keys/<LOGIN>.p8` on plan | `just sf keygen <LOGIN>` on this machine, or copy the key here |
| `JWT token is invalid` in a run | The key in the secret is not the one registered on the user: same public key in the user file, then `just tf apply` |

## Beyond the laptop

The stack is cluster-agnostic. For a hosted cluster: push the image to a registry (the
`Image build` CI job builds it but pushes nowhere), set `image` to that repository and a version
tag with `pull_policy: IfNotPresent`, point `kube_context` at the cluster, and move the Terraform
states to a [remote backend](snowflake-provisioning.md#stacks-and-state). Before it serves more
than you: an ingress with authentication in front of the webserver, compute logs in object
storage (`computeLogManager` in the chart), and Postgres outside the cluster or backed up.
