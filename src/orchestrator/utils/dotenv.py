"""Minimal .env editing that keeps comments and ordering intact.

Every reader has to get the written value back: `just` (dotenv-load) and python-dotenv both strip
single quotes and read what is inside literally, so a value goes in single quotes unless it only
holds characters that need none. Docker's --env-file does not strip quotes and would read a quoted
value with its quotes.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

# Characters every reader takes literally without quotes.
BARE = re.compile(r"[A-Za-z0-9_./:@+,=-]*")
# What single quotes cannot carry for both readers: the quote itself, line breaks, what python-dotenv
# (not `just`) resolves inside them (the escapes \\ and \', and ${VAR}), and a trailing backslash,
# which python-dotenv reads as an escaped closing quote and `just` refuses.
UNQUOTABLE = re.compile(r"['\r\n]|\\[\\']|\\$|\$\{")


def writable(value: str) -> bool:
    """Whether `value` reads back unchanged from .env, for `just` and python-dotenv alike."""
    return UNQUOTABLE.search(value) is None


def env_value(key: str, value: str) -> str:
    """`value` as .env text: bare when that is safe, else in single quotes; ValueError when neither reads back."""
    if BARE.fullmatch(value):
        return value
    if not writable(value):
        raise ValueError(f"{key} holds a quote, line break, ${{ or backslash sequence that .env cannot carry")
    return f"'{value}'"


def update_env_file(path: Path, updates: Mapping[str, str]) -> Path:
    """Set `KEY=value` lines in a dotenv file: replace every line of a key in place, append new keys.

    Existing comments and unrelated lines are left untouched.
    """
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    rendered = {key: f"{key}={env_value(key, value)}" for key, value in updates.items()}
    replaced: set[str] = set()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in rendered:
            lines[index] = rendered[key]
            replaced.add(key)
    appended = [line for key, line in rendered.items() if key not in replaced]
    if appended:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend(appended)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
