"""Generate Xi Yao 1 condensed handout chapters with DeepSeek.

Usage:
    python -m scripts.generate_xi_yao_1_condensed_handout --chapters chapter_01 chapter_03
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from api.database import sync_engine
from api.services.condensed_handout import CondensedHandoutError, save_generated_handout_chapter, validate_handout_output
from api.services.condensed_handout_prompt import SYSTEM_PROMPT, build_user_prompt
from api.services.deepseek_client import DeepSeekClientError, chat_json
from api.services.xi_yao_1_ingestion import DEFAULT_SOURCE_DIR, build_evidence_pack


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chapters", nargs="+", default=["chapter_01", "chapter_03"])
    parser.add_argument("--source-dir", default=str(DEFAULT_SOURCE_DIR))
    parser.add_argument("--principal-code", default="org_teaching_materials")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    source_dir = Path(args.source_dir)
    report = []
    for chapter_code in args.chapters:
        item = {"chapter": chapter_code, "status": "pending"}
        try:
            evidence_pack = build_evidence_pack(source_dir, chapter_code=chapter_code)
            item["textbookFragments"] = len(evidence_pack["textbookFragments"])
            item["handoutFragments"] = len(evidence_pack["handoutFragments"])
            item["examEvidence"] = len(evidence_pack["examEvidence"])
            generated, _raw_output, model_name = chat_json(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=build_user_prompt(evidence_pack),
            )
            validate_handout_output(generated)
            if not args.dry_run:
                save_generated_handout_chapter(
                    sync_engine,
                    chapter=generated,
                    principal_code=args.principal_code,
                    model_provider="deepseek",
                    model_name=model_name,
                )
            item["model"] = model_name
            item["reviewWarnings"] = len(generated.get("content", {}).get("reviewWarnings", []))
            item["status"] = "succeeded"
        except (CondensedHandoutError, DeepSeekClientError, ValueError, RuntimeError) as exc:
            item["status"] = "failed"
            item["error"] = f"{type(exc).__name__}: {exc}"
        report.append(item)

    print(json.dumps({"chapters": report}, ensure_ascii=False, indent=2))
    return 0 if all(item["status"] == "succeeded" for item in report) else 1


if __name__ == "__main__":
    raise SystemExit(main())
