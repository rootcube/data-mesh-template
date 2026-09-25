"""Snowflake connection settings shared by dbt, dlt, Dagster and the setup script.

Everything reads the same SNOWFLAKE_* variables plus ENVIRONMENT (see .env.example); `just` and
.envrc load them from .env. Key-pair authentication only: `just sf setup` creates the key
pair and registers the public key on your user.

Layers map to schemas of the project database (DB_<PROJECT>_<ENV>): `_<LAYER>` in every
environment except `dev`, where each developer works in personal schemas prefixed with their
SNOWFLAKE_SCHEMA (`<PREFIX>_<LAYER>`), so several people share one development database. A blank
SNOWFLAKE_SCHEMA in dev falls back to the prefix `DBT`, as dbt does (dbt/profiles.yml,
dbt_common.generate_schema_name): nobody provisions `DBT_<LAYER>`, so a missing prefix fails loudly
instead of writing into the shared `_<LAYER>` schemas of the development database.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, ClassVar

from cryptography.hazmat.primitives import serialization

ENV_PREFIX = "SNOWFLAKE_"
APPLICATION = "DATA_MESH_STARTER"
PERSONAL_ENVIRONMENTS = ("dev", "dummy")
PLACEHOLDER_PREFIX = "DBT"  # the dev prefix when SNOWFLAKE_SCHEMA is blank; dbt/profiles.yml defaults to the same


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

    REQUIRED: ClassVar[tuple[str, ...]] = ("account", "user", "private_key_path", "role", "warehouse", "database")
    CREDENTIALS: ClassVar[tuple[str, ...]] = ("account", "user", "private_key_path")

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
        environment = source.get("ENVIRONMENT", "").strip().lower()
        if environment:
            values["environment"] = environment
        return cls(**values)

    @property
    def is_personal(self) -> bool:
        """Development runs in personal schemas; every other environment shares the layer schemas."""
        return self.environment in PERSONAL_ENVIRONMENTS

    def schema_for_layer(self, layer_code: str) -> str:
        """The schema a layer lives in: `_<LAYER>`, or `<SNOWFLAKE_SCHEMA>_<LAYER>` in dev.

        Without SNOWFLAKE_SCHEMA, dev resolves to the unprovisioned `DBT_<LAYER>`, never the shared `_<LAYER>`.
        """
        layer = layer_code.strip("_").upper()
        if self.is_personal:
            return f"{(self.schema or PLACEHOLDER_PREFIX).upper()}_{layer}"
        return f"_{layer}"

    def missing(self, names: tuple[str, ...] = REQUIRED) -> list[str]:
        """Environment variable names among `names` that are not set."""
        return [f"{ENV_PREFIX}{name.upper()}" for name in names if not getattr(self, name)]

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
            # In dev SNOWFLAKE_SCHEMA is a prefix (DBT_USERNAME), not a schema: leave the session's schema unset.
            "schema": "" if self.is_personal else self.schema,
            "application": APPLICATION,
        }
        return {k: v for k, v in kwargs.items() if v}

    def connect(self, **overrides: Any) -> Any:
        """An open snowflake.connector connection (typed Any: the connector's stubs make every cursor optional)."""
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
