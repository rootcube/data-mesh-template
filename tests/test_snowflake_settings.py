from pathlib import Path

from orchestrator.resources.snowflake import SnowflakeSettings


def test_from_env_reads_prefixed_variables() -> None:
    env = {
        "SNOWFLAKE_ACCOUNT": "ORG-ACCOUNT",
        "SNOWFLAKE_USER": "someone",
        "SNOWFLAKE_PRIVATE_KEY_PATH": "/keys/k.p8",
        "SNOWFLAKE_ROLE": "RL_EXAMPLE_DEV__ENG",
        "SNOWFLAKE_WAREHOUSE": "WH_EXAMPLE_DEV",
        "SNOWFLAKE_DATABASE": "DB_EXAMPLE_DEV",
        "SNOWFLAKE_SCHEMA": " analytics ",
        "UNRELATED": "ignored",
    }
    settings = SnowflakeSettings.from_env(env)
    assert settings.account == "ORG-ACCOUNT"
    assert settings.schema == "analytics"
    assert settings.missing() == []


def test_blank_values_keep_defaults_and_show_up_as_missing() -> None:
    settings = SnowflakeSettings.from_env({"SNOWFLAKE_ACCOUNT": "ORG-ACCOUNT", "SNOWFLAKE_SCHEMA": "  "})
    assert settings.schema == ""
    assert settings.environment == "dev"
    assert settings.missing() == [
        "SNOWFLAKE_USER",
        "SNOWFLAKE_PRIVATE_KEY_PATH",
        "SNOWFLAKE_ROLE",
        "SNOWFLAKE_WAREHOUSE",
        "SNOWFLAKE_DATABASE",
    ]


def test_dlt_credentials_drop_empty_values() -> None:
    settings = SnowflakeSettings(account="ORG-ACCOUNT", user="u", private_key_path="/keys/k.p8", role="r")
    creds = settings.dlt_credentials()
    assert creds == {"host": "ORG-ACCOUNT", "username": "u", "private_key_path": "/keys/k.p8", "role": "r"}


def test_layer_schemas_are_personal_in_dev_and_shared_elsewhere() -> None:
    dev = SnowflakeSettings.from_env({"SNOWFLAKE_SCHEMA": "dbt_info", "ENVIRONMENT": "dev"})
    assert dev.schema_for_layer("src") == "DBT_INFO_SRC"
    assert dev.schema_for_layer("_stg") == "DBT_INFO_STG"
    prd = SnowflakeSettings.from_env({"SNOWFLAKE_SCHEMA": "_TMP", "ENVIRONMENT": "PRD"})
    assert prd.environment == "prd"
    assert prd.schema_for_layer("mrt") == "_MRT"


def test_connection_does_not_pass_the_personal_prefix_as_schema(tmp_path: Path) -> None:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key_path = tmp_path / "k.p8"
    key_path.write_bytes(
        rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        )
    )
    dev = SnowflakeSettings(account="a", user="u", private_key_path=str(key_path), schema="DBT_INFO", environment="dev")
    prd = SnowflakeSettings(account="a", user="u", private_key_path=str(key_path), schema="_TMP", environment="prd")
    assert "schema" not in dev.connection_kwargs()
    assert prd.connection_kwargs()["schema"] == "_TMP"
