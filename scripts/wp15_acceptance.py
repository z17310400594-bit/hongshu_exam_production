#!/usr/bin/env python
"""Run WP15 dual-read/golden/security acceptance gates.

Usage examples:

    python scripts/wp15_acceptance.py evaluate docs/implementation/evaluation/wp15_golden_cases.sample.jsonl
    python scripts/wp15_acceptance.py secret-scan api db src .env.example
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.services.acceptance import run_acceptance_from_jsonl, scan_secret_paths  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="WP15 acceptance gate runner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    evaluate_parser = subparsers.add_parser("evaluate", help="score golden JSONL cases")
    evaluate_parser.add_argument("cases", help="Path to JSONL acceptance cases")
    evaluate_parser.add_argument("--allow-fail", action="store_true", help="Print the report but return 0 even if gates fail")

    scan_parser = subparsers.add_parser("secret-scan", help="scan files/directories for obvious secrets")
    scan_parser.add_argument("paths", nargs="+", help="Files or directories to scan")
    scan_parser.add_argument("--allow-findings", action="store_true", help="Print findings but return 0")

    args = parser.parse_args(argv)
    if args.command == "evaluate":
        report = run_acceptance_from_jsonl(args.cases)
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if args.allow_fail or report["status"] == "pass" else 1

    findings = [finding.to_dict() for finding in scan_secret_paths(args.paths)]
    print(json.dumps({"status": "pass" if not findings else "fail", "findings": findings}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if args.allow_findings or not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
