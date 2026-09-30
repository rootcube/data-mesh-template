"""One-off: split the pre-Atmos Terraform state into one state per Atmos stack (`just tf-split-state`).

Before Atmos, terraform/ was one root module with one local state, terraform/terraform.tfstate, for
every project and environment. The components under terraform/components kept that module's resource
addresses: snowflake-project filters the configuration to one project and environment, and every
for_each key starts with `<project>_<environment>_` (or `<user>_<project>_<environment>_`). So each
resource instance only moves to the state of its stack, with `terraform state mv -state -state-out`
(the local-state form of the command). Data sources stay behind; the next plan reads them again.

    just tf-split-state --dry-run   # which stack gets what, nothing moves
    just tf-split-state

The original is kept as terraform/terraform.tfstate.pre-atmos, and nothing moves while a stack state
exists already. `just tf plan --all` then reports no changes in every stack. Delete this script once
no checkout has a pre-Atmos state left.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
TF_DIR = ROOT / "terraform"
CONFIG_DIR = TF_DIR / "config"
OLD_STATE = TF_DIR / "terraform.tfstate"
KEPT_STATE = TF_DIR / "terraform.tfstate.pre-atmos"
# The resources of the account component; every other one belongs to a project stack.
ACCOUNT_ADDRESSES = ("module.platform_role", "random_password.user", "snowflake_user.person")


@dataclasses.dataclass(frozen=True)
class Stack:
    """One component instance: its Atmos stack and Terraform workspace, the project and environment key it covers."""

    name: str
    workspace: str
    component: str
    project: str | None = None
    environment: str | None = None

    @property
    def state_path(self) -> Path:
        """Where the local backend keeps the state of this workspace."""
        return TF_DIR / "components" / self.component / "terraform.tfstate.d" / self.workspace / "terraform.tfstate"


def shown(path: Path) -> str:
    """A path as printed: relative to the repository, forward slashes on every platform."""
    return path.relative_to(ROOT).as_posix()


def config_keys(folder: str, nested: bool = True) -> dict[str, dict[str, Any]]:
    """The YAML files under config/<folder>, keyed as terraform/modules/config keys them."""
    base = CONFIG_DIR / folder
    keyed: dict[str, dict[str, Any]] = {}
    for path in sorted(base.rglob("*.yaml")):
        key = path.relative_to(base).with_suffix("").as_posix() if nested else path.stem
        keyed[key] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return keyed


def atmos_stacks() -> list[Stack]:
    """Every component instance Atmos knows, with the environment code of its stack mapped to its key."""
    described = subprocess.run(
        ["atmos", "describe", "stacks", "--format", "json", "--sections", "vars,workspace"],
        cwd=ROOT,
        capture_output=True,
        encoding="utf-8",
        check=True,
    ).stdout
    environment_key = {str(env.get("code")): key for key, env in config_keys("environments").items()}
    stacks = []
    for name, stack in json.loads(described).items():
        for component, section in stack["components"]["terraform"].items():
            variables = section.get("vars", {})
            code = variables.get("environment")
            project, environment = variables.get("project"), environment_key.get(code, code)
            stacks.append(Stack(name, section["workspace"], component, project, environment))
    return stacks


def movable_addresses(state: dict[str, Any]) -> list[str]:
    """The addresses to move: each module instance as a whole, each resource instance outside a module."""
    addresses: list[str] = []
    for resource in state["resources"]:
        if resource["mode"] != "managed":
            continue
        if module := resource.get("module"):
            addresses.append(module.split(".module.")[0])
            continue
        for instance in resource["instances"]:
            key = instance.get("index_key")
            index = "" if key is None else f"[{json.dumps(key)}]"
            addresses.append(f"{resource['type']}.{resource['name']}{index}")
    return list(dict.fromkeys(addresses))


def stack_of(address: str, stacks: list[Stack], users: set[str]) -> Stack | None:
    """The one stack an address belongs to, or None when no stack or more than one matches."""
    if address.startswith(ACCOUNT_ADDRESSES):
        matches = [s for s in stacks if s.component == "snowflake-account"]
    else:
        key = re.search(r'\["([^"]+)"\]', address)
        matches = [s for s in stacks if key and s.project and covers(s, key[1], users)]
    return matches[0] if len(matches) == 1 else None


def covers(stack: Stack, key: str, users: set[str]) -> bool:
    """Whether a for_each key is one of the stack's: `<project>_<env>_...` or `<user>_<project>_<env>_...`."""
    prefix = f"{stack.project}_{stack.environment}_"
    return key.startswith(prefix) or any(key.startswith(f"{user}_{prefix}") for user in users)


def split(state: dict[str, Any], stacks: list[Stack], users: set[str]) -> tuple[dict[Stack, list[str]], list[str]]:
    """The addresses per stack, and the addresses no single stack claims."""
    moves: dict[Stack, list[str]] = {}
    unassigned: list[str] = []
    for address in movable_addresses(state):
        stack = stack_of(address, stacks, users)
        if stack is None:
            unassigned.append(address)
        else:
            moves.setdefault(stack, []).append(address)
    return moves, unassigned


def initialize(stack: Stack) -> None:
    """`atmos terraform init` before any state lands, so Terraform records the component's backend first.

    A component's first init next to existing workspace states offers to migrate them onto themselves,
    a question an unattended plan cannot answer.
    """
    subprocess.run(
        ["atmos", "terraform", "init", stack.component, "-s", stack.name],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        check=True,
    )


def move(address: str, target: Path, workdir: Path) -> None:
    """Move one address from the old state into `target`, backups into the throwaway `workdir`."""
    subprocess.run(
        [
            "terraform",
            "state",
            "mv",
            f"-state={OLD_STATE}",
            f"-state-out={target}",
            f"-backup={workdir / 'state.backup'}",
            f"-backup-out={workdir / 'state-out.backup'}",
            address,
            address,
        ],
        cwd=workdir,
        capture_output=True,
        encoding="utf-8",
        check=True,
    )


def refusal(moves: dict[Stack, list[str]]) -> str | None:
    """Why the split must not run, if it must not."""
    if KEPT_STATE.exists():
        return f"{shown(KEPT_STATE)} exists already: the state was split before."
    existing = [shown(s.state_path) for s in moves if s.state_path.exists()]
    if existing:
        return "These stack states exist already, so they were split or applied before: " + ", ".join(existing)
    return None


def run(moves: dict[Stack, list[str]]) -> None:
    """Initialize each component, keep the original state, then move every address into its stack's state."""
    for stack in {s.component: s for s in moves}.values():
        initialize(stack)
    shutil.copy2(OLD_STATE, KEPT_STATE)
    with tempfile.TemporaryDirectory() as tmp:
        for stack, addresses in moves.items():
            stack.state_path.parent.mkdir(parents=True, exist_ok=True)
            for number, address in enumerate(addresses, 1):
                print(f"  {stack.workspace}: {number}/{len(addresses)} {address}", flush=True)
                move(address, stack.state_path, Path(tmp))
    OLD_STATE.unlink()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="show which stack gets what, move nothing")
    args = parser.parse_args(argv)
    if not OLD_STATE.exists():
        print(f"No pre-Atmos state at {shown(OLD_STATE)}; nothing to split.")
        return 0
    state = json.loads(OLD_STATE.read_text(encoding="utf-8"))
    moves, unassigned = split(state, atmos_stacks(), set(config_keys("users", nested=False)))
    for stack, addresses in moves.items():
        print(f"{stack.workspace:<16} {len(addresses):>4} addresses -> {shown(stack.state_path)}")
    if unassigned:
        print("No single stack claims these, so nothing moves (a stack manifest missing under terraform/stacks?):")
        print("\n".join(f"  {address}" for address in unassigned))
        return 1
    if args.dry_run:
        return 0
    if reason := refusal(moves):
        print(f"{reason} Nothing moves.")
        return 1
    try:
        run(moves)
    except subprocess.CalledProcessError as exc:
        print(exc.stdout + exc.stderr)
        print(
            f"The split stopped halfway. To start over: copy {shown(KEPT_STATE)} back to "
            f"{shown(OLD_STATE)}, then delete {shown(KEPT_STATE)} and "
            "terraform/components/*/terraform.tfstate.d/."
        )
        return 1
    print(f"Done; the original is {shown(KEPT_STATE)}. Next: `just tf plan --all` shows no changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
