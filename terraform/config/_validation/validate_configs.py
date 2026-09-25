#!/usr/bin/env python3
"""
YAML Configuration Validation Script

Validates YAML configuration files against their JSON schemas.
Supports the split-file configuration structure.

Usage:
    python validate_configs.py           # Validate all configs
    python validate_configs.py --file projects/fundana.yaml  # Validate specific file
"""

import io
import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft7Validator
from jsonschema.exceptions import SchemaError

# Configuration mapping: directory -> schema file
CONFIG_SCHEMA_MAP = {
    "projects": "schemas/project.schema.json",
    "roles": "schemas/role.schema.json",
    "computes": "schemas/compute.schema.json",
    "environments": "schemas/environment.schema.json",
    "layers": "schemas/layer.schema.json",
    "teams": "schemas/team.schema.json",
    "organisations": "schemas/organisation.schema.json",
    "privileges": "schemas/privilege.schema.json",
    "users": "schemas/user.schema.json",
}


def load_yaml(file_path: Path) -> dict:
    """Load and parse a YAML file."""
    with open(file_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_json_schema(schema_path: Path) -> dict:
    """Load and parse a JSON schema file."""
    with open(schema_path, encoding="utf-8") as f:
        return json.load(f)


def validate_yaml_against_schema(yaml_path: Path, schema_path: Path) -> tuple[bool, list[str]]:
    """
    Validate a YAML file against a JSON schema.

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    try:
        data = load_yaml(yaml_path)
    except yaml.YAMLError as e:
        errors.append(f"YAML parsing error: {e}")
        return False, errors

    try:
        schema = load_json_schema(schema_path)
    except json.JSONDecodeError as e:
        errors.append(f"Schema JSON parsing error: {e}")
        return False, errors

    try:
        validator = Draft7Validator(schema)
    except SchemaError as e:
        errors.append(f"Invalid schema: {e}")
        return False, errors

    validation_errors = sorted(validator.iter_errors(data), key=lambda e: e.path)

    for error in validation_errors:
        path = " -> ".join(str(p) for p in error.absolute_path) or "(root)"
        errors.append(f"  [{path}]: {error.message}")

    return len(errors) == 0, errors


def config_key(config_type: str, relative_path: Path) -> str:
    """Terraform's key of a config file: its path under the type folder without .yaml; users by file name alone."""
    if config_type == "users":
        return relative_path.stem
    return relative_path.with_suffix("").as_posix()


def load_all_configs(config_dir: Path) -> dict[str, dict[str, dict]]:
    """
    Load all configuration files from the split structure, sub-folders included (like Terraform).

    Returns:
        Dictionary with keys for each config type
        Each value is a dict mapping the Terraform key (see config_key) to content
    """
    configs = {
        "projects": {},
        "roles": {},
        "computes": {},
        "environments": {},
        "layers": {},
        "teams": {},
        "organisations": {},
        "privileges": {},
        "users": {},
    }

    for config_type in configs.keys():
        type_dir = config_dir / config_type
        if type_dir.exists():
            for yaml_file in sorted(type_dir.rglob("*.yaml")):
                try:
                    content = load_yaml(yaml_file)
                    if content:
                        configs[config_type][config_key(config_type, yaml_file.relative_to(type_dir))] = content
                except yaml.YAMLError:
                    pass  # Errors will be caught during schema validation

    return configs


def validate_cross_references(config_dir: Path) -> tuple[bool, list[str], list[str]]:
    """
    Validate cross-references between configuration files.

    Checks:
    - Projects reference valid environments, layers, computes, and teams
    - Roles reference valid computes, layers, and other roles
    - Non-existent references are errors
    - Disabled references are warnings

    Returns:
        Tuple of (is_valid, list_of_errors, list_of_warnings)
    """
    errors = []
    warnings = []

    # Load all configs from split structure
    configs = load_all_configs(config_dir)

    # Get ALL layer keys (for existence check) and enabled layer keys (for disabled check)
    all_layer_keys = set(configs["layers"].keys())
    enabled_layer_keys = {key for key, cfg in configs["layers"].items() if not cfg.get("disabled", False)}

    # Get ALL environment keys and enabled environment keys
    all_env_keys = set(configs["environments"].keys())
    enabled_env_keys = {key for key, cfg in configs["environments"].items() if not cfg.get("disabled", False)}

    # Get ALL compute keys and enabled compute keys
    all_compute_keys = set(configs["computes"].keys())
    enabled_compute_keys = {key for key, cfg in configs["computes"].items() if not cfg.get("disabled", False)}

    # Get valid team keys from split structure
    valid_team_keys = set(configs["teams"].keys())

    # Get ALL role keys and enabled role keys
    all_role_keys = set(configs["roles"].keys())
    enabled_role_keys = {key for key, cfg in configs["roles"].items() if not cfg.get("disabled", False)}

    # Get valid organisation keys
    valid_org_keys = set(configs["organisations"].keys())

    # Print available references
    print(f" - Valid organisations : {', '.join(sorted(valid_org_keys)) or '(none)'}")
    print(f" - Valid teams         : {', '.join(sorted(valid_team_keys)) or '(none)'}")
    print(f" - Valid environments  : {', '.join(sorted(enabled_env_keys)) or '(none)'}")
    print(f" - Valid layers        : {', '.join(sorted(enabled_layer_keys)) or '(none)'}")
    print(f" - Valid computes      : {', '.join(sorted(enabled_compute_keys)) or '(none)'}")
    print(f" - Valid roles         : {', '.join(sorted(enabled_role_keys)) or '(none)'}")
    print()

    # Validate each project
    for project_key, project in sorted(configs["projects"].items()):
        # Handle wildcards: "*" means all enabled items
        raw_layers = project.get("layers", [])
        raw_envs = project.get("environments", [])
        raw_computes = project.get("computes", [])

        project_layers = enabled_layer_keys if raw_layers == "*" else set(raw_layers)
        project_envs = enabled_env_keys if raw_envs == "*" else set(raw_envs)
        project_computes = enabled_compute_keys if raw_computes == "*" else set(raw_computes)
        project_team = project.get("team")

        project_errors = []
        project_warnings = []

        # Check referenced layers: non-existent = error, disabled = warning
        nonexistent_layers = project_layers - all_layer_keys
        disabled_layers = (project_layers & all_layer_keys) - enabled_layer_keys
        if nonexistent_layers:
            project_errors.append(f"Non-existent layer keys: {', '.join(sorted(nonexistent_layers))}")
        if disabled_layers:
            project_warnings.append(f"Disabled layer keys: {', '.join(sorted(disabled_layers))}")

        # Check referenced environments: non-existent = error, disabled = warning
        nonexistent_envs = project_envs - all_env_keys
        disabled_envs = (project_envs & all_env_keys) - enabled_env_keys
        if nonexistent_envs:
            project_errors.append(f"Non-existent environment keys: {', '.join(sorted(nonexistent_envs))}")
        if disabled_envs:
            project_warnings.append(f"Disabled environment keys: {', '.join(sorted(disabled_envs))}")

        # Check referenced computes: non-existent = error, disabled = warning
        nonexistent_computes = project_computes - all_compute_keys
        disabled_computes = (project_computes & all_compute_keys) - enabled_compute_keys
        if nonexistent_computes:
            project_errors.append(f"Non-existent compute keys: {', '.join(sorted(nonexistent_computes))}")
        if disabled_computes:
            project_warnings.append(f"Disabled compute keys: {', '.join(sorted(disabled_computes))}")

        # Check team reference exists
        if project_team and project_team not in valid_team_keys:
            project_errors.append(f"Non-existent team reference: '{project_team}'")

        # Terraform names every object after the file name, so the code has to match it
        if project.get("code") != project_key:
            project_errors.append(f"Code '{project.get('code')}' differs from the file name '{project_key}'")

        if project_errors or project_warnings:
            if project_errors:
                print(f" ❌ projects/{project_key}")
            else:
                print(f" ⚠️ projects/{project_key}")
            for error in project_errors:
                errors.append(f"  [projects/{project_key}]: {error}")
                print(f"     ❌ {error}")
            for warning in project_warnings:
                warnings.append(f"  [projects/{project_key}]: {warning}")
                print(f"     ⚠️ {warning}")
        else:
            print(f" ✅ projects/{project_key}")

    # Validate each role's privileges
    for role_key, role in sorted(configs["roles"].items()):
        privileges = role.get("privileges", {})
        role_errors = []
        role_warnings = []

        # Check referenced computes in privileges: non-existent = error, disabled = warning
        role_computes = set(privileges.get("computes", {}).keys())
        nonexistent_computes = role_computes - all_compute_keys
        disabled_computes = (role_computes & all_compute_keys) - enabled_compute_keys
        if nonexistent_computes:
            role_errors.append(f"Non-existent compute keys in privileges: {', '.join(sorted(nonexistent_computes))}")
        if disabled_computes:
            role_warnings.append(f"Disabled compute keys in privileges: {', '.join(sorted(disabled_computes))}")

        # Check referenced layers in privileges: non-existent = error, disabled = warning
        role_layers = set(privileges.get("layers", {}).keys())
        nonexistent_layers = role_layers - all_layer_keys
        disabled_layers = (role_layers & all_layer_keys) - enabled_layer_keys
        if nonexistent_layers:
            role_errors.append(f"Non-existent layer keys in privileges: {', '.join(sorted(nonexistent_layers))}")
        if disabled_layers:
            role_warnings.append(f"Disabled layer keys in privileges: {', '.join(sorted(disabled_layers))}")

        # Check referenced roles in privileges: non-existent = error, disabled = warning
        role_refs = set(privileges.get("roles", {}).keys())
        nonexistent_roles = role_refs - all_role_keys
        disabled_roles = (role_refs & all_role_keys) - enabled_role_keys
        if nonexistent_roles:
            role_errors.append(f"Non-existent role keys in privileges: {', '.join(sorted(nonexistent_roles))}")
        if disabled_roles:
            role_warnings.append(f"Disabled role keys in privileges: {', '.join(sorted(disabled_roles))}")

        if role_errors or role_warnings:
            if role_errors:
                print(f" ❌ roles/{role_key}")
            else:
                print(f" ⚠️  roles/{role_key}")
            for error in role_errors:
                errors.append(f"  [roles/{role_key}]: {error}")
                print(f"    ❌ {error}")
            for warning in role_warnings:
                warnings.append(f"  [roles/{role_key}]: {warning}")
                print(f"    ⚠️  {warning}")
        else:
            print(f" ✅ roles/{role_key}")

    # Validate each team's organisation reference
    for team_key, team in sorted(configs["teams"].items()):
        team_errors = []
        team_org = team.get("organisation")

        # Check organisation reference exists
        if team_org and team_org not in valid_org_keys:
            team_errors.append(f"Non-existent organisation reference: '{team_org}'")

        if team_errors:
            print(f" ❌ teams/{team_key}")
            for error in team_errors:
                errors.append(f"  [teams/{team_key}]: {error}")
                print(f"    ❌ {error}")
        else:
            print(f" ✅ teams/{team_key}")

    return len(errors) == 0, errors, warnings


def project_environments(project: dict, configs: dict[str, dict[str, dict]]) -> set[str]:
    """The environment keys Terraform deploys a project to: all enabled ones for "*" or none, else listed enabled."""
    enabled = {key for key, cfg in configs["environments"].items() if not cfg.get("disabled", False)}
    raw = project.get("environments", "*")
    return enabled if raw == "*" else set(raw) & enabled


def project_roles(project: dict, configs: dict[str, dict[str, dict]]) -> set[str]:
    """The role keys Terraform creates for a project: all enabled project roles for "*", else listed plus required."""
    enabled = {
        key for key, cfg in configs["roles"].items() if cfg.get("level") == "project" and not cfg.get("disabled", False)
    }
    required = {key for key in enabled if configs["roles"][key].get("required", False)}
    raw = project.get("roles", [])
    return enabled if raw == "*" else (set(raw) | required) & enabled


def assignment_problems(assignment: dict, configs: dict[str, dict[str, dict]]) -> list[str]:
    """Why a user's role assignment would not (fully) be granted; Terraform skips such grants without an error."""
    project_key, role_key = assignment.get("project"), assignment.get("role")
    project, role = configs["projects"].get(project_key), configs["roles"].get(role_key)
    if project is None:
        return [f"Non-existent project '{project_key}'"]

    problems = []
    if role is None:
        problems.append(f"Non-existent role '{role_key}'")
    elif role.get("level") != "project":
        problems.append(f"Role '{role_key}' is not a project-level role")
    elif role_key not in project_roles(project, configs):
        problems.append(f"Role '{role_key}' is not a role of project '{project_key}'")

    environments = assignment.get("environments", "*")
    if environments == "*":
        return problems
    nonexistent_envs = set(environments) - set(configs["environments"])
    outside_envs = set(environments) - nonexistent_envs - project_environments(project, configs)
    if nonexistent_envs:
        problems.append(f"Non-existent environment keys: {', '.join(sorted(nonexistent_envs))}")
    if outside_envs:
        problems.append(f"Environments not (enabled) in project '{project_key}': {', '.join(sorted(outside_envs))}")
    return problems


def duplicate_user_files(config_dir: Path) -> dict[str, list[str]]:
    """User files that share a file name: Terraform keys users by file name alone, so it fails on them."""
    users_dir = config_dir / "users"
    paths_by_key: dict[str, list[str]] = {}
    for yaml_file in sorted(users_dir.rglob("*.yaml")):
        paths_by_key.setdefault(yaml_file.stem, []).append(f"users/{yaml_file.relative_to(users_dir).as_posix()}")
    return {key: paths for key, paths in paths_by_key.items() if len(paths) > 1}


def validate_user_references(config_dir: Path) -> tuple[bool, list[str], list[str]]:
    """
    Validate the role assignments of every user file and that no two user files share a file name.

    Problems in a disabled user file are warnings, since Terraform ignores that file.

    Returns:
        Tuple of (is_valid, list_of_errors, list_of_warnings)
    """
    errors = []
    warnings = []

    configs = load_all_configs(config_dir)

    for user_key, user in sorted(configs["users"].items()):
        problems = [problem for a in user.get("roles", []) for problem in assignment_problems(a, configs)]
        if not problems:
            print(f" ✅ users/{user_key}")
            continue
        messages, icon = (warnings, "⚠️ ") if user.get("disabled", False) else (errors, "❌")
        print(f" {icon} users/{user_key}")
        for problem in problems:
            messages.append(f"  [users/{user_key}]: {problem}")
            print(f"    {icon} {problem}")

    for user_key, paths in sorted(duplicate_user_files(config_dir).items()):
        error_msg = f"Several user files with this file name: {', '.join(paths)}"
        errors.append(f"  [users/{user_key}]: {error_msg}")
        print(f" ❌ users/{user_key}: {error_msg}")

    return len(errors) == 0, errors, warnings


def validate_mandatory_configs(config_dir: Path) -> tuple[bool, list[str]]:
    """
    Validate that required configurations are included in all projects.

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    # Load all configs from split structure
    configs = load_all_configs(config_dir)

    # Get required layer keys from split structure (only if not disabled)
    required_layer_keys = {
        key for key, cfg in configs["layers"].items() if cfg.get("required", False) and not cfg.get("disabled", False)
    }

    # Get required environment keys (only if not disabled)
    required_env_keys = {
        key
        for key, cfg in configs["environments"].items()
        if cfg.get("required", False) and not cfg.get("disabled", False)
    }

    # Get required compute keys (only if not disabled)
    required_compute_keys = {
        key for key, cfg in configs["computes"].items() if cfg.get("required", False) and not cfg.get("disabled", False)
    }

    # Get required role keys (only project-level roles that are not disabled)
    required_role_keys = {
        key
        for key, cfg in configs["roles"].items()
        if cfg.get("required", False) and not cfg.get("disabled", False) and cfg.get("level") == "project"
    }

    # Get all enabled keys (for wildcard expansion)
    valid_layer_keys = {key for key, cfg in configs["layers"].items() if not cfg.get("disabled", False)}
    valid_env_keys = {key for key, cfg in configs["environments"].items() if not cfg.get("disabled", False)}
    valid_compute_keys = {key for key, cfg in configs["computes"].items() if not cfg.get("disabled", False)}
    valid_role_keys = {
        key for key, cfg in configs["roles"].items() if not cfg.get("disabled", False) and cfg.get("level") == "project"
    }

    # Report what's required
    print(f" - Required environments : {', '.join(sorted(required_env_keys)) or '(none)'}")
    print(f" - Required layers       : {', '.join(sorted(required_layer_keys)) or '(none)'}")
    print(f" - Required computes     : {', '.join(sorted(required_compute_keys)) or '(none)'}")
    print(f" - Required roles        : {', '.join(sorted(required_role_keys)) or '(none)'}")
    print()

    # Validate each project
    for project_key, project in sorted(configs["projects"].items()):
        # Handle wildcards: "*" means all enabled items
        raw_layers = project.get("layers", [])
        raw_envs = project.get("environments", [])
        raw_computes = project.get("computes", [])
        raw_roles = project.get("roles", [])

        project_layers = valid_layer_keys if raw_layers == "*" else set(raw_layers)
        project_envs = valid_env_keys if raw_envs == "*" else set(raw_envs)
        project_computes = valid_compute_keys if raw_computes == "*" else set(raw_computes)
        project_roles = valid_role_keys if raw_roles == "*" else set(raw_roles)

        project_errors = []

        # Check required layers are included
        missing_layers = required_layer_keys - project_layers
        if missing_layers:
            project_errors.append(f"Missing required layers: {', '.join(sorted(missing_layers))}")

        # Check required environments are included
        missing_envs = required_env_keys - project_envs
        if missing_envs:
            project_errors.append(f"Missing required environments: {', '.join(sorted(missing_envs))}")

        # Check required computes are included
        missing_computes = required_compute_keys - project_computes
        if missing_computes:
            project_errors.append(f"Missing required computes: {', '.join(sorted(missing_computes))}")

        # Check required roles are included
        missing_roles = required_role_keys - project_roles
        if missing_roles:
            project_errors.append(f"Missing required roles: {', '.join(sorted(missing_roles))}")

        if project_errors:
            print(f" ❌ projects/{project_key}")
            for error in project_errors:
                errors.append(f"  [projects/{project_key}]: {error}")
                print(f"    {error}")
        else:
            print(f" ✅ projects/{project_key}")

    return len(errors) == 0, errors


def validate_required_not_disabled(config_dir: Path) -> tuple[bool, list[str]]:
    """
    Validate that no configuration is both required and disabled.

    A required config cannot be disabled - this is a logical contradiction.

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    # Load all configs from split structure
    configs = load_all_configs(config_dir)

    # Check each config type for required+disabled conflicts
    config_types_to_check = ["layers", "environments", "computes", "roles"]

    for config_type in config_types_to_check:
        for key, cfg in sorted(configs[config_type].items()):
            is_required = cfg.get("required", False)
            is_disabled = cfg.get("disabled", False)

            if is_required and is_disabled:
                error_msg = "Configuration is both required and disabled"
                errors.append(f"  [{config_type}/{key}]: {error_msg}")
                print(f" ❌ {config_type}/{key}: {error_msg}")
            else:
                print(f" ✅ {config_type}/{key}")

    return len(errors) == 0, errors


def validate_schema(config_dir: Path, validation_dir: Path, specific_file: str | None = None) -> bool:
    """
    Validate all configuration files against their schemas.

    Returns:
        True if all validations pass, False otherwise.
    """
    all_valid = True

    print("\n Schema Validation:")

    for config_type, schema_file in CONFIG_SCHEMA_MAP.items():
        type_dir = config_dir / config_type
        schema_path = validation_dir / schema_file

        if not type_dir.exists():
            print(f" ⚠️  {config_type}/: Directory not found, skipping")
            continue

        if not schema_path.exists():
            print(f" ⚠️  {config_type}/: Schema not found at {schema_file}, skipping")
            continue

        yaml_files = sorted(type_dir.rglob("*.yaml"))
        if not yaml_files:
            print(f" ⚠️  {config_type}/: No YAML files found")
            continue

        # type_valid = True
        for yaml_file in yaml_files:
            file_name = f"{config_type}/{yaml_file.relative_to(type_dir).as_posix()}"
            # Skip if specific file requested and this isn't it
            if specific_file and file_name != specific_file:
                continue

            is_valid, errors = validate_yaml_against_schema(yaml_file, schema_path)

            if is_valid:
                print(f" ✅ {file_name}: Valid")
            else:
                print(f" ❌ {file_name}: Invalid")
                for error in errors:
                    print(f"   {error}")
                # type_valid = False
                all_valid = False

    return all_valid


def validate_all_configs(config_dir: Path, validation_dir: Path, specific_file: str | None = None) -> bool:
    """
    Validate all configuration files against their schemas.

    Returns:
        True if all validations pass, False otherwise.
    """
    all_valid = True

    # Validate schema for all configs
    if not validate_schema(config_dir, validation_dir, specific_file):
        all_valid = False

    # Cross-reference validation (only if not validating a specific file)
    if not specific_file:
        print("\n Cross-Reference Validation:")

        is_valid, errors, warnings = validate_cross_references(config_dir)

        if not is_valid:
            all_valid = False

        # User role assignments and duplicate user file names
        print("\n User Validation:")

        is_valid, errors, warnings = validate_user_references(config_dir)

        if not is_valid:
            all_valid = False

        # Required+Disabled conflict validation
        print("\n Required vs Disabled Validation:")

        is_valid, errors = validate_required_not_disabled(config_dir)

        if not is_valid:
            all_valid = False

        # Required configuration validation
        print("\n Required Configuration Validation:")

        is_valid, errors = validate_mandatory_configs(config_dir)

        if not is_valid:
            all_valid = False

    return all_valid


def main() -> None:
    """Main entry point for CLI usage."""
    import argparse

    # The report prints emoji; a Windows pipe (pre-commit, `| tail`) defaults to cp1252, which cannot encode them.
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Validate YAML configuration files against JSON schemas")
    parser.add_argument(
        "--file",
        "-f",
        type=str,
        help="Specific config file to validate (e.g., projects/fundana.yaml)",
    )
    parser.add_argument(
        "--config-dir",
        "-d",
        type=str,
        default=None,
        help="Path to config directory (defaults to parent of _validation directory)",
    )

    args = parser.parse_args()

    # Determine paths
    # This script is in _validation/, so config_dir is the parent
    validation_dir = Path(__file__).parent

    if args.config_dir:
        config_dir = Path(args.config_dir)
    else:
        config_dir = validation_dir.parent

    if not config_dir.exists():
        print(f"Error: Config directory not found: {config_dir}")
        sys.exit(1)

    print(f"\n Validating configs in: {config_dir}")

    success = validate_all_configs(config_dir, validation_dir, args.file)

    print("\n")
    print("-" * 40)

    if success:
        print("\n ✅ All validations passed!")
        sys.exit(0)
    else:
        print("\n ❌ Some validations failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
