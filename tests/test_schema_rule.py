"""The layer-to-schema rule, pinned across its three implementations.

`SnowflakeSettings.schema_for_layer()` is the Python one, `dbt_common.generate_schema_name` the
dbt one, and `dbt_example/sources/src_knmi.yml` spells the same rule out inline because source
YAML cannot call macros. The two dbt ones are rendered here with plain jinja2 against a fake dbt
`target`: neither touches `adapter` or a database, so no dbt runtime is needed.

Not covered: the `default__generate_schema_name` dispatch wrapper (plain jinja2 has no
`dbt_common` namespace), which only delegates to the macro tested here.
"""

from pathlib import Path
from types import SimpleNamespace

import jinja2
import pytest
import yaml

from orchestrator.resources.snowflake import SnowflakeSettings

REPO_ROOT = Path(__file__).resolve().parents[1]
MACRO_FILE = REPO_ROOT / "dbt" / "dbt_common" / "macros" / "generate_schema_name.sql"
SOURCE_FILE = REPO_ROOT / "dbt" / "dbt_example" / "sources" / "src_knmi.yml"

# The dbt target names, which follow ENVIRONMENT (dbt/profiles.yml); dev and local are the personal ones.
ENVIRONMENTS = ["dev", "local", "tst", "prd"]
# SNOWFLAKE_SCHEMA, blank and set: in dev it is the personal prefix, elsewhere it is ignored.
PREFIXES = ["", "DBT_USERNAME"]
# Every layer code the projects use (dbt_project.yml `+schema:`, plus src and mtd).
LAYERS = ["src", "ref", "stg", "int", "mrt", "exp", "mtd", "tmp"]


def dbt_target(environment: str, prefix: str) -> SimpleNamespace:
    """The part of dbt's `target` the schema rule reads."""
    return SimpleNamespace(name=environment, schema=prefix)


def render_macro(custom_schema_name: str | None, environment: str, prefix: str) -> str:
    """`dbt_common.generate_schema_name(custom_schema_name, node)`, rendered with plain jinja2."""
    env = jinja2.Environment(undefined=jinja2.StrictUndefined)
    source = MACRO_FILE.read_text(encoding="utf-8")
    module = env.from_string(source).make_module({"target": dbt_target(environment, prefix)})
    # jinja2 exports the macros of a rendered template into the module namespace.
    macro: jinja2.runtime.Macro = vars(module)["generate_schema_name"]
    return str(macro(custom_schema_name, None))


def render_source_schema(environment: str, prefix: str) -> str:
    """The inline `schema:` expression of the dbt source YAML, read from the file itself."""
    expression = yaml.safe_load(SOURCE_FILE.read_text(encoding="utf-8"))["sources"][0]["schema"]
    env = jinja2.Environment(undefined=jinja2.StrictUndefined)
    return env.from_string(expression).render(target=dbt_target(environment, prefix))


@pytest.mark.parametrize("environment", ENVIRONMENTS)
@pytest.mark.parametrize("prefix", PREFIXES)
def test_macro_resolves_layers_like_schema_for_layer(environment: str, prefix: str) -> None:
    settings = SnowflakeSettings.from_env({"SNOWFLAKE_SCHEMA": prefix, "ENVIRONMENT": environment})
    macro = {layer: render_macro(layer, environment, prefix) for layer in LAYERS}
    assert macro == {layer: settings.schema_for_layer(layer) for layer in LAYERS}


@pytest.mark.parametrize("environment", ENVIRONMENTS)
@pytest.mark.parametrize("prefix", PREFIXES)
def test_source_yaml_resolves_the_source_layer_like_schema_for_layer(environment: str, prefix: str) -> None:
    settings = SnowflakeSettings.from_env({"SNOWFLAKE_SCHEMA": prefix, "ENVIRONMENT": environment})
    assert render_source_schema(environment, prefix) == settings.schema_for_layer("src")


@pytest.mark.parametrize("environment", ENVIRONMENTS)
def test_a_model_without_a_layer_stays_out_of_the_shared_layer_schemas(environment: str) -> None:
    # No `+schema:`, so the rule has no Python counterpart: the macro's own documented fallback.
    personal = environment in ("dev", "local")
    assert render_macro(None, environment, "") == ("DBT" if personal else "_TMP")
    assert render_macro(None, environment, "DBT_USERNAME") == "DBT_USERNAME"
