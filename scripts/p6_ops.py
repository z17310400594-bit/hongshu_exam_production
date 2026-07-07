#!/usr/bin/env python
"""P6 operations evidence CLI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.config import settings  # noqa: E402
from api.services.ops_evidence import (  # noqa: E402
    build_database_manifest,
    compare_restore_manifests,
    load_json,
    load_jsonl,
    summarize_api_samples,
    write_json_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P6 operations evidence runner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    manifest_parser = subparsers.add_parser("db-manifest", help="Build a critical-table database manifest")
    manifest_parser.add_argument("--output", help="Optional path to write JSON manifest")

    compare_parser = subparsers.add_parser("compare-restore", help="Compare source/restored database manifests")
    compare_parser.add_argument("--source", required=True, help="Source manifest JSON")
    compare_parser.add_argument("--restored", required=True, help="Restored manifest JSON")
    compare_parser.add_argument("--output", help="Optional path to write JSON comparison")

    samples_parser = subparsers.add_parser("summarize-api-samples", help="Summarize API samples into monitor metrics")
    samples_parser.add_argument("--input", required=True, help="JSONL API sample file")
    samples_parser.add_argument("--output", help="Optional path to write JSON summary")

    args = parser.parse_args(argv)

    if args.command == "db-manifest":
        engine = create_engine(settings.database_url)
        try:
            report = build_database_manifest(engine)
        finally:
            engine.dispose()
        print(write_json_report(report, args.output))
        return 0

    if args.command == "compare-restore":
        report = compare_restore_manifests(load_json(args.source), load_json(args.restored))
        print(write_json_report(report, args.output))
        return 0 if report["rowCountsMatch"] and report["hashesMatch"] and report["referencesValid"] else 1

    if args.command == "summarize-api-samples":
        report = summarize_api_samples(load_jsonl(args.input))
        print(write_json_report(report, args.output))
        return 0

    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
