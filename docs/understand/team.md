---
icon: material/account-group-outline
---

# Team

A Team is the human ownership and accountability unit. It is a group of people responsible
for building, operating and supporting one or more Projects.

A Team owns one or more Projects, and a Project has exactly one owning Team. Teams may align
with departments, domains or product teams; they exist for governance, onboarding, support
routing and accountability. They do not structure technical resources: there is no database,
role or warehouse per Team. Isolation is the Project's job.

## In this repo

One file per team under `terraform/config/teams/`:

```yaml title="terraform/config/teams/platform.yaml"
organisation: "example"
code: "platform"
name: "Platform Team"
type: "team"
desc: "Central platform engineering team responsible for infrastructure and shared services"
owners:
  - "platform-admin@example.com"
```

`organisation` refers to the organisation file name. Projects refer to the team the same way
(`team: "platform"` in `projects/example.yaml`), and `just tf-validate-config` fails when a
project names a team that has no file.

The `owners` list is where the platform's ownership rules land: every Project has exactly one
owning Team, and every Team designates who answers for it. The starter records that here and
nowhere else; there is no automated escalation or support path wired to it.

## In Snowflake

Nothing. Terraform loads `terraform/config/teams/` (see `terraform/modules/config`) so that
projects can reference a team, but no Snowflake object carries the team name, and so no team
appears in [Naming](../reference/naming.md). Ownership is visible through the Project's objects
instead: whoever holds `RL_EXAMPLE_PRD__ENG` is the platform team.

Next: [Project](project.md).
