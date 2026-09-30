"""The Terraform YAML validator (terraform/config/_validation/validate_configs.py).

It is a script, not a package, so it is loaded from its path. Every test builds a small config
tree under tmp_path: one that passes, then one broken tree per rule, since a validator that only
ever sees a valid repository proves nothing.
"""

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATION_DIR = REPO_ROOT / "terraform" / "config" / "_validation"


def load_validator() -> ModuleType:
    """Import validate_configs.py by path; it lives outside any package."""
    spec = importlib.util.spec_from_file_location("validate_configs", VALIDATION_DIR / "validate_configs.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = load_validator()


def base_configs() -> dict[str, dict[str, Any]]:
    """The smallest schema-valid config tree: one of everything, wired up correctly."""
    return {
        "organisations": {"example": {"code": "EXAMPLE", "name": "Example Organisation"}},
        "teams": {
            "platform": {"organisation": "example", "code": "platform", "name": "Platform", "type": "team"},
        },
        "environments": {
            "development": {"letter": "d", "code": "dev", "name": "Development", "required": True},
        },
        "layers": {
            "source": {"code": "src", "name": "Source", "type": "input", "required": True},
            "mart": {"code": "mrt", "name": "Mart", "type": "output"},
        },
        "accesses": {"read": {"code": "read", "name": "Read", "privileges": ["USAGE", "SELECT ON TABLES"]}},
        "computes": {"default": {"code": "", "name": "Default", "sizes": ["xs"], "required": True}},
        "roles": {
            "engineer": {"code": "eng", "name": "Engineer", "type": "person", "level": "project", "required": True},
            "analyst": {"code": "anl", "name": "Analyst", "type": "person", "level": "project"},
        },
        "projects": {
            "example": {
                "team": "platform",
                "code": "example",
                "name": "Example Project",
                "environments": ["development"],
                "layers": ["source", "mart"],
                "computes": ["default"],
                "roles": ["engineer", "analyst"],
            },
        },
        "users": {
            "username_example": {
                "login": "username@example.com",
                "roles": [{"project": "example", "role": "engineer", "environments": ["development"]}],
            },
        },
    }


def write_configs(root: Path, configs: dict[str, dict[str, Any]]) -> Path:
    """Write {type: {key: content}} as <root>/<type>/<key>.yaml; a key may contain a sub-folder."""
    for config_type, files in configs.items():
        for key, content in files.items():
            path = root / config_type / f"{key}.yaml"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(yaml.safe_dump(content), encoding="utf-8")
    return root


def write_stack(root: Path, project: str, environment: str, stack_vars: dict[str, str] | None = None) -> Path:
    """Write the Atmos stack manifest terraform/stacks/projects/<project>/<environment>.yaml next to config/."""
    path = root / "stacks" / "projects" / project / f"{environment}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    stack_vars = stack_vars or {"project": project, "environment": environment}
    path.write_text(yaml.safe_dump({"import": ["catalog/snowflake-project"], "vars": stack_vars}), encoding="utf-8")
    return path


def config_dir(tmp_path: Path, **changes: dict[str, Any]) -> Path:
    """The base tree with one config type replaced or extended, e.g. projects={"example": {...}}.

    The base project's one stack manifest (example/dev) is written too.
    """
    configs = base_configs()
    for config_type, files in changes.items():
        configs[config_type].update(files)
    write_stack(tmp_path, "example", "dev")
    return write_configs(tmp_path / "config", configs)


def project(**changes: Any) -> dict[str, Any]:
    """The base project with some keys changed."""
    return {**base_configs()["projects"]["example"], **changes}


# --- Schema validation ------------------------------------------------------


def test_the_base_tree_passes_every_check(tmp_path: Path) -> None:
    assert validator.validate_all_configs(config_dir(tmp_path), VALIDATION_DIR) is True


def test_schema_validation_rejects_an_unknown_property(tmp_path: Path) -> None:
    configs = config_dir(tmp_path, projects={"example": project(typo="unexpected")})
    assert validator.validate_schema(configs, VALIDATION_DIR) is False


def test_schema_validation_rejects_a_missing_required_property(tmp_path: Path) -> None:
    configs = config_dir(tmp_path, roles={"analyst": {"code": "anl", "name": "Analyst", "type": "person"}})
    assert validator.validate_schema(configs, VALIDATION_DIR) is False


# --- Cross references -------------------------------------------------------


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"layers": ["source", "typo"]}, "Non-existent layer keys: typo"),
        ({"environments": ["typo"]}, "Non-existent environment keys: typo"),
        ({"computes": ["typo"]}, "Non-existent compute keys: typo"),
        ({"roles": ["engineer", "anlyst"]}, "Non-existent project role keys: anlyst"),
        ({"team": "typo"}, "Non-existent team reference: 'typo'"),
        ({"code": "other"}, "Code 'other' differs from the file name 'example'"),
    ],
)
def test_a_project_reference_that_does_not_exist_is_an_error(
    tmp_path: Path, changes: dict[str, Any], message: str
) -> None:
    configs = config_dir(tmp_path, projects={"example": project(**changes)})
    is_valid, errors, _ = validator.validate_cross_references(configs)
    assert is_valid is False
    assert errors == [f"  [projects/example]: {message}"]


@pytest.mark.parametrize(
    ("config_type", "key", "message"),
    [
        ("layers", "mart", "Disabled layer keys: mart"),
        ("roles", "analyst", "Disabled role keys: analyst"),
    ],
)
def test_a_project_reference_that_is_disabled_is_a_warning(
    tmp_path: Path, config_type: str, key: str, message: str
) -> None:
    disabled = {key: {**base_configs()[config_type][key], "disabled": True}}
    configs = config_dir(tmp_path, **{config_type: disabled})
    is_valid, errors, warnings = validator.validate_cross_references(configs)
    assert (is_valid, errors) == (True, [])
    assert warnings == [f"  [projects/example]: {message}"]


def test_a_role_reference_that_does_not_exist_is_an_error(tmp_path: Path) -> None:
    engineer = {**base_configs()["roles"]["engineer"], "privileges": {"layers": {"typo": {"development": "read"}}}}
    is_valid, errors, _ = validator.validate_cross_references(config_dir(tmp_path, roles={"engineer": engineer}))
    assert is_valid is False
    assert errors == ["  [roles/engineer]: Non-existent layer keys in privileges: typo"]


def test_stage_privileges_outside_an_input_layer_are_an_error(tmp_path: Path) -> None:
    mart = {**base_configs()["layers"]["mart"], "privileges": {"read": ["READ ON STAGES"]}}
    is_valid, errors, _ = validator.validate_cross_references(config_dir(tmp_path, layers={"mart": mart}))
    assert is_valid is False
    assert "Stage or file format privileges on a output layer" in errors[0]


# --- User references --------------------------------------------------------


@pytest.mark.parametrize(
    ("assignment", "message"),
    [
        ({"project": "typo", "role": "engineer"}, "Non-existent project 'typo'"),
        ({"project": "example", "role": "typo"}, "Non-existent role 'typo'"),
        ({"project": "example", "role": "engineer", "environments": ["typo"]}, "Non-existent environment keys: typo"),
    ],
)
def test_a_broken_role_assignment_is_an_error(tmp_path: Path, assignment: dict[str, Any], message: str) -> None:
    user = {"login": "username@example.com", "roles": [assignment]}
    is_valid, errors, _ = validator.validate_user_references(config_dir(tmp_path, users={"username_example": user}))
    assert is_valid is False
    assert errors == [f"  [users/username_example]: {message}"]


def test_a_broken_assignment_in_a_disabled_user_file_is_a_warning(tmp_path: Path) -> None:
    user = {"login": "username@example.com", "disabled": True, "roles": [{"project": "typo", "role": "engineer"}]}
    configs = config_dir(tmp_path, users={"username_example": user})
    is_valid, errors, warnings = validator.validate_user_references(configs)
    assert (is_valid, errors) == (True, [])
    assert warnings == ["  [users/username_example]: Non-existent project 'typo'"]


def test_two_user_files_with_the_same_name_are_an_error(tmp_path: Path) -> None:
    # Terraform keys users by file name alone, so a sub-folder does not make them distinct.
    configs = config_dir(tmp_path, users={"team/username_example": base_configs()["users"]["username_example"]})
    assert validator.duplicate_user_files(configs) == {
        "username_example": ["users/team/username_example.yaml", "users/username_example.yaml"]
    }
    is_valid, errors, _ = validator.validate_user_references(configs)
    assert is_valid is False
    assert "Several user files with this file name" in errors[-1]


# --- Required configurations ------------------------------------------------


@pytest.mark.parametrize("config_type", ["layers", "environments", "computes", "roles"])
def test_required_and_disabled_at_once_is_an_error(tmp_path: Path, config_type: str) -> None:
    key = next(iter(base_configs()[config_type]))
    broken = {key: {**base_configs()[config_type][key], "required": True, "disabled": True}}
    is_valid, errors = validator.validate_required_not_disabled(config_dir(tmp_path, **{config_type: broken}))
    assert is_valid is False
    assert errors == [f"  [{config_type}/{key}]: Configuration is both required and disabled"]


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"layers": ["mart"]}, "Missing required layers: source"),
        ({"environments": []}, "Missing required environments: development"),
        ({"computes": []}, "Missing required computes: default"),
        ({"roles": ["analyst"]}, "Missing required roles: engineer"),
    ],
)
def test_a_project_leaving_out_a_required_config_is_an_error(
    tmp_path: Path, changes: dict[str, Any], message: str
) -> None:
    configs = config_dir(tmp_path, projects={"example": project(**changes)})
    is_valid, errors = validator.validate_mandatory_configs(configs)
    assert is_valid is False
    assert errors == [f"  [projects/example]: {message}"]


def test_a_wildcard_covers_every_required_config(tmp_path: Path) -> None:
    wildcards = project(layers="*", environments="*", computes="*", roles="*")
    is_valid, errors = validator.validate_mandatory_configs(config_dir(tmp_path, projects={"example": wildcards}))
    assert (is_valid, errors) == (True, [])


# --- Stack manifests (terraform/stacks/projects) ----------------------------


def test_a_project_environment_without_a_stack_manifest_is_an_error(tmp_path: Path) -> None:
    configs = config_dir(tmp_path)
    (tmp_path / "stacks" / "projects" / "example" / "dev.yaml").unlink()
    is_valid, errors = validator.validate_stacks(configs)
    assert is_valid is False
    assert errors == ["  [stacks/projects/example/dev.yaml]: Missing: projects/example.yaml lists environment dev"]


def test_a_stack_manifest_no_project_environment_asks_for_is_an_error(tmp_path: Path) -> None:
    configs = config_dir(tmp_path)
    write_stack(tmp_path, "example", "prd")
    is_valid, errors = validator.validate_stacks(configs)
    assert is_valid is False
    assert errors == [
        "  [stacks/projects/example/prd.yaml]: No project in config/projects lists this environment (or it is disabled)"
    ]


def test_stack_manifest_vars_must_match_its_path(tmp_path: Path) -> None:
    configs = config_dir(tmp_path)
    write_stack(tmp_path, "example", "dev", {"project": "example", "environment": "prd"})
    is_valid, errors = validator.validate_stacks(configs)
    assert is_valid is False
    assert errors == ["  [stacks/projects/example/dev.yaml]: vars must be `project: example` and `environment: dev`"]


# --- Service users ----------------------------------------------------------

SERVICE_KEY = (
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAu1SU1LfVLPHCozMxH2Mo4lgOEePzNm0tRgeLezV6ffAt0gunVTLw7onLRnrq0IDAQAB"
)


def service_user(**changes: Any) -> dict[str, Any]:
    """A service user holding the transform role in development, with `changes` applied (None removes a key)."""
    user = {
        "login": "EXAMPLE_DEV_TRANSFORM",
        "type": "service",
        "rsa_public_key": SERVICE_KEY,
        "roles": [{"project": "example", "role": "transform", "environments": ["development"]}],
        **changes,
    }
    return {key: value for key, value in user.items() if value is not None}


def with_service_user(tmp_path: Path, user: dict[str, Any]) -> Path:
    """The base tree plus a system role `transform` in the project and the given user file `svc`."""
    transform = {"code": "tfm", "name": "Transform", "type": "system", "level": "project"}
    return config_dir(
        tmp_path,
        roles={"transform": transform},
        projects={"example": project(roles=["engineer", "analyst", "transform"])},
        users={"svc": user},
    )


def test_a_service_user_with_its_key_passes(tmp_path: Path) -> None:
    assert validator.validate_all_configs(with_service_user(tmp_path, service_user()), VALIDATION_DIR) is True


@pytest.mark.parametrize(
    "changes",
    [
        {"rsa_public_key": None},  # Terraform creates it with this key, so it is required
        {"login": "example_dev_transform"},  # upper case only
        {"create": True},  # persons only
        {"email": "svc@example.com"},
    ],
)
def test_a_service_user_breaking_the_schema_is_rejected(tmp_path: Path, changes: dict[str, Any]) -> None:
    configs = with_service_user(tmp_path, service_user(**changes))
    assert validator.validate_schema(configs, VALIDATION_DIR) is False


def test_a_person_with_a_public_key_is_rejected(tmp_path: Path) -> None:
    person = {**base_configs()["users"]["username_example"], "rsa_public_key": SERVICE_KEY}
    assert validator.validate_schema(config_dir(tmp_path, users={"username_example": person}), VALIDATION_DIR) is False


def test_a_service_user_holding_a_person_role_is_an_error(tmp_path: Path) -> None:
    user = service_user(roles=[{"project": "example", "role": "engineer"}])
    is_valid, errors, _ = validator.validate_user_references(with_service_user(tmp_path, user))
    assert is_valid is False
    assert errors == [
        "  [users/svc]: Service users hold system roles only; 'engineer' is not one (type: system in config/roles)"
    ]
