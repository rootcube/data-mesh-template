"""Minimal .env editing that keeps comments and ordering intact."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path


def update_env_file(path: Path, updates: Mapping[str, str]) -> Path:
    """Set `KEY=value` lines in a dotenv file: replace existing keys in place, append new ones.

    Values are written unquoted (the repo convention: `just`, Docker and python-dotenv then all
    read the same bytes). Existing comments and unrelated lines are left untouched.
    """
    lines = path.read_text().splitlines() if path.exists() else []
    pending = dict(updates)
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in pending:
            lines[index] = f"{key}={pending.pop(key)}"
    if pending:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend(f"{key}={value}" for key, value in pending.items())
    path.write_text("\n".join(lines) + "\n")
    return path
