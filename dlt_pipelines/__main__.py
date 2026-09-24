"""Run dlt pipelines outside Dagster.

    uv run python -m dlt_pipelines list
    uv run python -m dlt_pipelines run knmi [--full-refresh]

Every pipelines/ingest/<source>/pipelines.py exposes a module-level `source` and `pipeline`;
`run` imports that module and calls `pipeline.run(source)`.
"""

from __future__ import annotations

import argparse
import importlib
import pkgutil
import sys

import dlt_pipelines.pipelines.ingest as ingest_pkg


def discover() -> dict[str, str]:
    """Map source name -> module path for every package under pipelines/ingest."""
    return {
        module.name: f"{ingest_pkg.__name__}.{module.name}.pipelines"
        for module in pkgutil.iter_modules(ingest_pkg.__path__)
        if module.ispkg
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m dlt_pipelines",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("list", help="list the available ingest pipelines")
    run = subcommands.add_parser("run", help="run one ingest pipeline")
    run.add_argument("source", help="source name, see `list`")
    run.add_argument(
        "--full-refresh",
        action="store_true",
        help="drop the source's tables and state in the destination before loading",
    )
    args = parser.parse_args(argv)

    sources = discover()
    if args.command == "list":
        for name, module in sorted(sources.items()):
            print(f"{name:<12} {module}")
        return 0

    if args.source not in sources:
        parser.error(f"unknown source {args.source!r}; available: {', '.join(sorted(sources))}")
    module = importlib.import_module(sources[args.source])
    refresh = "drop_sources" if args.full_refresh else None
    load_info = module.pipeline.run(module.source, refresh=refresh)
    print(load_info)
    return 0


if __name__ == "__main__":
    sys.exit(main())
