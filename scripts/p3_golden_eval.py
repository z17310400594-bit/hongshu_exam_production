#!/usr/bin/env python
"""Run P3 golden cases against the live V2 service layer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.config import settings  # noqa: E402
from api.services.p3_golden import run_p3_golden_jsonl  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P3 golden-set runner")
    parser.add_argument("cases", help="Path to P3 golden JSONL cases")
    parser.add_argument("--database-url", default=settings.database_url, help="Override database URL")
    parser.add_argument("--output", help="Optional path to write JSON report")
    parser.add_argument("--allow-fail", action="store_true", help="Return 0 even if gates fail")
    args = parser.parse_args(argv)

    report = run_p3_golden_jsonl(create_engine(args.database_url), args.cases)
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if args.allow_fail or report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
