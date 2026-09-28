"""Check that a titled code fence in the docs really quotes the file it names.

A fence whose `title="..."` names a repository file has to reproduce a piece of that file
exactly: the body, with the fence's own indentation and every line's trailing whitespace
removed, must appear as one consecutive run of lines in the file. Blank lines around the
body are ignored, nothing else is.

Skipped:

- a title with a parenthetical annotation (`(excerpt)`, `(condensed)`, `(abridged)`,
  `(pattern)`, `(example)`, `(new file)`, ...): the block is an illustration, not a copy;
- a body that is a `--8<--` snippet include: it cannot drift;
- a title that is not a path, such as `Fact template`. A title counts as a path when it
  holds a slash or ends in one of the source extensions below.

Run: `uv run python scripts/check_doc_fences.py`. Failures print as `path:line: reason`.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
OPEN_FENCE = re.compile(r"^(?P<indent> *)(?P<ticks>`{3,})(?P<info>.*)$")
TITLE = re.compile(r'title="(?P<title>[^"]*)"')
ANNOTATED = re.compile(r"\([^()]*\)\s*$")
EXTENSIONS = {".cfg", ".csv", ".ini", ".json", ".md", ".py", ".sh", ".sql", ".tf", ".toml", ".txt", ".yaml", ".yml"}


def fences(text: str) -> Iterator[tuple[int, str, list[str]]]:
    """Yield (1-based line number of the opening fence, its info string, its body lines)."""
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        opening = OPEN_FENCE.match(lines[index])
        if opening is None:
            index += 1
            continue
        closing = re.compile(rf"^ *{opening['ticks']}`* *$")
        indent = len(opening["indent"])
        body: list[str] = []
        cursor = index + 1
        while cursor < len(lines) and not closing.match(lines[cursor]):
            body.append(lines[cursor][indent:])
            cursor += 1
        yield index + 1, opening["info"], body
        index = cursor + 1


def looks_like_path(title: str) -> bool:
    return "/" in title or Path(title).suffix in EXTENSIONS


def trimmed(body: list[str]) -> list[str]:
    lines = [line.rstrip() for line in body]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return lines


def mismatch(source: list[str], quoted: list[str]) -> str | None:
    """Why `quoted` is not a consecutive run of lines in `source`, or None when it is."""
    starts = (i for i, line in enumerate(source) if line == quoted[0])
    if any(source[i : i + len(quoted)] == quoted for i in starts):
        return None
    missing = next((line for line in quoted if line and line not in source), None)
    if missing is not None:
        return f"line not in the file: {missing.strip()!r}"
    return "every line is in the file, but not as one consecutive block"


def check(page: Path) -> list[str]:
    problems: list[str] = []
    name = page.relative_to(ROOT).as_posix()
    for line, info, body in fences(page.read_text(encoding="utf-8")):
        title_match = TITLE.search(info)
        if title_match is None:
            continue
        title = title_match["title"].strip()
        if ANNOTATED.search(title) or not looks_like_path(title):
            continue
        if any(entry.lstrip().startswith("--8<--") for entry in body):
            continue
        target = ROOT / title
        quoted = trimmed(body)
        if not target.is_file():
            problems.append(f"{name}:{line}: no such file: {title} (annotate the title if it is an illustration)")
        elif not quoted:
            problems.append(f"{name}:{line}: empty fence titled {title}")
        else:
            reason = mismatch([entry.rstrip() for entry in target.read_text(encoding="utf-8").splitlines()], quoted)
            if reason is not None:
                problems.append(f"{name}:{line}: does not quote {title} verbatim: {reason}")
    return problems


def main() -> int:
    problems = [problem for page in sorted(DOCS.rglob("*.md")) for problem in check(page)]
    for problem in problems:
        print(problem)
    if problems:
        print(f"\n{len(problems)} titled fence(s) out of sync. Use a `--8<--` include, or annotate the title.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
