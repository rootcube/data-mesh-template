"""The one-off split of the pre-Atmos Terraform state into one state per stack (scripts/split_state.py).

A synthetic state in the shape `terraform show`'s file format has: module instances keyed
`<project>_<environment>_...` or `<user>_<project>_<environment>_...`, root resources, a data source.
"""

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "split_state.py"


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("split_state", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["split_state"] = module
    spec.loader.exec_module(module)
    return module


script = load_script()

ACCOUNT = script.Stack("account", "account", "snowflake-account")
DEV = script.Stack("example-dev", "example-dev", "snowflake-project", "example", "development")
PRD = script.Stack("example-prd", "example-prd", "snowflake-project", "example", "production")
STACKS = [ACCOUNT, DEV, PRD]
USERS = {"admin", "username_example"}


def resource(kind: str, name: str, keys: list[Any], module: str | None = None, mode: str = "managed") -> dict[str, Any]:
    """A resource entry of a state file, with one instance per key."""
    entry: dict[str, Any] = {"mode": mode, "type": kind, "name": name, "instances": [{"index_key": k} for k in keys]}
    if module:
        entry["module"] = module
    return entry


DATABASE = 'module.database["example_development_database"]'
STATE = {
    "resources": [
        resource("snowflake_database", "this", [None], module=DATABASE),
        resource("snowflake_execute", "drop_public_schema", [None], module=DATABASE),
        resource(
            "snowflake_grant_privileges_to_account_role",
            "tables_all",
            [0],
            module='module.access_role_grant["example_production_access_role_mart_read"]',
        ),
        resource(
            "snowflake_schema", "this", [None], module='module.personal_schema["admin_example_development_source"]'
        ),
        resource("snowflake_stage_internal", "default", ["example_production_schema_source"]),
        resource("snowflake_grant_account_role", "user", ["admin_example_development_engineer"]),
        resource("random_password", "user", ["username_example"]),
        resource("snowflake_users", "existing", [0], mode="data"),
    ]
}


def test_movable_addresses_are_module_instances_and_root_resource_instances() -> None:
    assert script.movable_addresses(STATE) == [
        'module.database["example_development_database"]',
        'module.access_role_grant["example_production_access_role_mart_read"]',
        'module.personal_schema["admin_example_development_source"]',
        'snowflake_stage_internal.default["example_production_schema_source"]',
        'snowflake_grant_account_role.user["admin_example_development_engineer"]',
        'random_password.user["username_example"]',
    ]


def test_every_address_goes_to_the_stack_its_key_names() -> None:
    moves, unassigned = script.split(STATE, STACKS, USERS)
    assert unassigned == []
    assert moves == {
        DEV: [
            'module.database["example_development_database"]',
            'module.personal_schema["admin_example_development_source"]',
            'snowflake_grant_account_role.user["admin_example_development_engineer"]',
        ],
        PRD: [
            'module.access_role_grant["example_production_access_role_mart_read"]',
            'snowflake_stage_internal.default["example_production_schema_source"]',
        ],
        ACCOUNT: ['random_password.user["username_example"]'],
    }


@pytest.mark.parametrize(
    "address",
    [
        'module.database["other_development_database"]',  # a project without a stack manifest
        'module.personal_schema["stranger_example_development_source"]',  # a user no config/users file names
        "snowflake_stage_internal.default",  # no key at all
    ],
)
def test_an_address_no_single_stack_claims_is_left_unassigned(address: str) -> None:
    assert script.stack_of(address, STACKS, USERS) is None


def test_the_account_stack_takes_platform_roles_and_created_users() -> None:
    for address in ('module.platform_role["administrator"]', 'snowflake_user.person["username_example"]'):
        assert script.stack_of(address, STACKS, USERS) == ACCOUNT


def test_nothing_moves_when_a_stack_state_exists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(script, "ROOT", tmp_path)
    monkeypatch.setattr(script, "TF_DIR", tmp_path / "terraform")
    monkeypatch.setattr(script, "KEPT_STATE", tmp_path / "terraform" / "terraform.tfstate.pre-atmos")
    assert script.refusal({DEV: ["x"]}) is None
    DEV.state_path.parent.mkdir(parents=True)
    DEV.state_path.write_text("{}")
    assert "terraform/components/snowflake-project/terraform.tfstate.d/example-dev" in script.refusal({DEV: ["x"]})


def test_run_initializes_each_component_before_any_state_moves(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    old = tmp_path / "terraform" / "terraform.tfstate"
    old.parent.mkdir()
    old.write_text("{}")
    monkeypatch.setattr(script, "TF_DIR", tmp_path / "terraform")
    monkeypatch.setattr(script, "OLD_STATE", old)
    monkeypatch.setattr(script, "KEPT_STATE", tmp_path / "terraform" / "terraform.tfstate.pre-atmos")
    calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", lambda args, **kwargs: calls.append(args[:3]))
    script.run({DEV: ["a"], PRD: ["b"], ACCOUNT: ["c"]})
    assert calls == [
        ["atmos", "terraform", "init"],  # snowflake-project, once for both of its stacks
        ["atmos", "terraform", "init"],  # snowflake-account
        ["terraform", "state", "mv"],
        ["terraform", "state", "mv"],
        ["terraform", "state", "mv"],
    ]
    assert not old.exists()
    assert (tmp_path / "terraform" / "terraform.tfstate.pre-atmos").read_text() == "{}"
