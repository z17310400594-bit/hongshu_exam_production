#!/usr/bin/env python
"""Run WP16 rollout/recovery/rollback readiness gates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.services.release_readiness import run_release_readiness_from_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="WP16 release readiness gate runner")
    parser.add_argument("plan", help="Path to WP16 release plan JSON")
    parser.add_argument("--allow-fail", action="store_true", help="Print the report but return 0 even if gates fail")
    args = parser.parse_args(argv)

    report = run_release_readiness_from_json(args.plan)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if args.allow_fail or report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
