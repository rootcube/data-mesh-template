"""Snowflake connection settings shared by dbt, dlt, Dagster and the setup script.

Everything reads the same SNOWFLAKE_* variables plus ENVIRONMENT (see .env.example); `just` and
.envrc load them from .env. Key-pair authentication only: `just snowflake setup` creates the key
pair and registers the public key on your user.

Layers map to schemas of the project database (DB_<PROJECT>_<ENV>): `_<LAYER>` in every
environment except `dev`, where each developer works in personal schemas prefixed with their
SNOWFLAKE_SCHEMA (`<PREFIX>_<LAYER>`), so several people share one development database.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, fields
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from cryptography.hazmat.primitives import serialization

if TYPE_CHECKING:
    from dagster_snowflake import SnowflakeResource
    from snowflake.connector import SnowflakeConnection

ENV_PREFIX = "SNOWFLAKE_"
APPLICATION = "DATA_MESH_STARTER"
ENVIRONMENT_VAR = "ENVIRONMENT"
PERSONAL_ENVIRONMENTS = ("dev", "dummy")


@dataclass(frozen=True)
class SnowflakeSettings:
    """A connection to one project database, as read from the SNOWFLAKE_* environment variables."""

    account: str = ""
    user: str = ""
    private_key_path: str = ""
    private_key_passphrase: str = ""
    role: str = ""
    warehouse: str = ""
    database: str = ""
    schema: str = ""
    environment: str = "dev"

    _REQUIRED: ClassVar[tuple[str, ...]] = ("account", "user", "private_key_path", "role", "warehouse", "database")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> SnowflakeSettings:
        """Build settings from `env` (default: os.environ). Unset or blank variables keep the field default."""
        source = os.environ if env is None else env
        values: dict[str, str] = {}
        for field in fields(cls):
            if field.name == "environment":
                continue
            raw = source.get(f"{ENV_PREFIX}{field.name.upper()}", "")
            if raw and raw.strip():
                values[field.name] = raw.strip()
        environment = source.get(ENVIRONMENT_VAR, "").strip().lower()
        if environment:
            values["environment"] = environment
        return cls(**values)

    @property
    def is_personal(self) -> bool:
        """Development runs in personal schemas; every other environment shares the layer schemas."""
        return self.environment in PERSONAL_ENVIRONMENTS

    def schema_for_layer(self, layer_code: str) -> str:
        """The schema a layer lives in: `_<LAYER>`, or `<SNOWFLAKE_SCHEMA>_<LAYER>` in dev."""
        layer = layer_code.strip("_").upper()
        if self.is_personal and self.schema:
            return f"{self.schema.upper()}_{layer}"
        return f"_{layer}"

    def env_name(self, field_name: str) -> str:
        return f"{ENV_PREFIX}{field_name.upper()}"

    _CREDENTIALS: ClassVar[tuple[str, ...]] = ("account", "user", "private_key_path")

    def missing(self) -> list[str]:
        """Environment variable names that are required but not set."""
        return [self.env_name(name) for name in self._REQUIRED if not getattr(self, name)]

    def missing_credentials(self) -> list[str]:
        """Only what is needed to connect at all (no role, warehouse or database)."""
        return [self.env_name(name) for name in self._CREDENTIALS if not getattr(self, name)]

    def key_path(self) -> Path:
        return Path(self.private_key_path).expanduser()

    def private_key_der(self) -> bytes:
        """The private key as unencrypted PKCS#8 DER, the form the Snowflake connector accepts."""
        password = self.private_key_passphrase.encode() if self.private_key_passphrase else None
        key = serialization.load_pem_private_key(self.key_path().read_bytes(), password=password)
        return key.private_bytes(
            serialization.Encoding.DER,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )

    def connection_kwargs(self) -> dict[str, Any]:
        """Keyword arguments for snowflake.connector.connect (key-pair / JWT authentication)."""
        kwargs: dict[str, Any] = {
            "account": self.account,
            "user": self.user,
            "private_key": self.private_key_der(),
            "role": self.role,
            "warehouse": self.warehouse,
            "database": self.database,
            # In dev SNOWFLAKE_SCHEMA is a prefix (DBT_INFO), not a schema: leave the session's schema unset.
            "schema": "" if self.is_personal else self.schema,
            "application": APPLICATION,
        }
        return {k: v for k, v in kwargs.items() if v}

    def connect(self, **overrides: Any) -> SnowflakeConnection:
        import snowflake.connector

        return snowflake.connector.connect(**{**self.connection_kwargs(), **overrides})

    def dlt_credentials(self) -> dict[str, str]:
        """Credentials for dlt.destinations.snowflake(credentials=...)."""
        creds = {
            "host": self.account,
            "username": self.user,
            "private_key_path": str(self.key_path()) if self.private_key_path else "",
            "private_key_passphrase": self.private_key_passphrase,
            "role": self.role,
            "warehouse": self.warehouse,
            "database": self.database,
        }
        return {k: v for k, v in creds.items() if v}

    def dagster_resource(self) -> SnowflakeResource:
        """A dagster_snowflake resource for Python assets that query Snowflake directly."""
        from dagster_snowflake import SnowflakeResource

        return SnowflakeResource(
            account=self.account,
            user=self.user,
            private_key_path=str(self.key_path()),
            private_key_password=self.private_key_passphrase or None,
            role=self.role,
            warehouse=self.warehouse,
            database=self.database,
            schema=None if self.is_personal else (self.schema or None),
        )
