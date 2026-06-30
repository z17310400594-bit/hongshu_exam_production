"""P3 golden-set runner backed by the live V2 service layer.

P3 is the bridge between static acceptance samples and real business cases:
JSONL records describe the user question, expected result, and V2 action to run.
The runner executes those actions against a configured database engine, then
delegates scoring/difference classification to the WP15 acceptance helpers.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.engine import Engine

from api.auth import AuthorizationError
from api.services.acceptance import evaluate_acceptance_cases, load_jsonl
from api.services.question_bank import get_paper_questions
from api.services.v2_api import (
    evaluate_eligibility_v2,
    get_certificate_detail,
    get_certificate_exam_events_v2,
    search_knowledge,
)


def run_p3_golden_jsonl(engine: Engine, path: str) -> dict[str, Any]:
    """Load P3 JSONL cases, run V2 actions, and return an acceptance report."""
    return evaluate_p3_golden_cases(engine, load_jsonl(path))


def evaluate_p3_golden_cases(engine: Engine, cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Run each P3 case and score the resulting V2 output."""
    evaluated_cases = []
    for case in cases:
        action = str(case.get("action") or "")
        params = _object(case.get("params"))
        v2_result = run_p3_action(engine, action=action, params=params)
        evaluated = dict(case)
        evaluated["v2Result"] = v2_result
        evaluated.setdefault("oldResult", _legacy_placeholder(case))
        evaluated_cases.append(evaluated)

    report = evaluate_acceptance_cases(evaluated_cases)
    report["caseIds"] = [str(case.get("id")) for case in evaluated_cases]
    return report


def run_p3_action(engine: Engine, *, action: str, params: dict[str, Any]) -> dict[str, Any]:
    """Run one named P3 action and normalize the result for acceptance scoring."""
    try:
        if action == "certificate_detail":
            raw = get_certificate_detail(
                engine,
                certificate_code=str(params["certificateCode"]),
                as_of=_date_or_none(params.get("asOf")),
            )
            return {
                "certificateCode": raw["code"],
                "name": raw["name"],
                "aliasCount": len(raw.get("aliases", [])),
            }

        if action == "exam_event":
            raw = get_certificate_exam_events_v2(
                engine,
                certificate_code=str(params["certificateCode"]),
                exam_year=_int_or_none(params.get("examYear")),
                as_of=_date_or_none(params.get("asOf")),
            )
            selected = _object(raw.get("selectedEvent"))
            certificate = _object(raw.get("certificate"))
            raw_phases = selected.get("phases")
            phases: list[dict[str, Any]] = [
                item for item in raw_phases if isinstance(item, dict)
            ] if isinstance(raw_phases, list) else []
            return {
                "certificateCode": certificate.get("code"),
                "eventCode": selected.get("code"),
                "phaseCount": len(phases),
                "firstPhaseStart": phases[0].get("startsOn") if phases else None,
            }

        if action == "eligibility":
            return evaluate_eligibility_v2(
                engine,
                certificate_code=str(params["certificateCode"]),
                principal_type=str(params.get("principalType", "org")),
                principal_code=str(params.get("principalCode", "org_teaching_materials")),
                as_of=_date(params.get("asOf")),
                region_code=str(params.get("regionCode", "CN")),
                qualification_level=_optional_str(params.get("qualificationLevel")),
                degree_level_code=_optional_str(params.get("degreeLevelCode")),
                major_category_code=_optional_str(params.get("majorCategoryCode")),
                education_type_code=_optional_str(params.get("educationTypeCode")),
                total_work_months=_int_or_none(params.get("totalWorkMonths")),
                relevant_work_months=_int_or_none(params.get("relevantWorkMonths")),
                admission_date=_date_or_none(params.get("admissionDate")),
            )

        if action == "knowledge_search":
            raw = search_knowledge(
                engine,
                principal_type=str(params.get("principalType", "org")),
                principal_code=str(params.get("principalCode", "org_teaching_materials")),
                query=str(params.get("query", "")),
                collection_codes=_str_list(params.get("collectionCodes")),
                knowledge_point_codes=_str_list(params.get("knowledgePointCodes")),
                asset_types=_str_list(params.get("assetTypes")),
                top_k=int(params.get("topK", 8)),
                as_of=_date_or_none(params.get("asOf")),
            )
            raw_items = raw.get("items")
            items: list[dict[str, Any]] = [
                item for item in raw_items if isinstance(item, dict)
            ] if isinstance(raw_items, list) else []
            citations = [
                {
                    "assetCode": item.get("assetCode"),
                    "fragmentCode": item.get("fragmentCode"),
                    "title": item.get("assetTitle"),
                }
                for item in items
            ]
            return {
                "decision": "found" if items else "insufficient_data",
                "itemCount": len(items),
                "citations": citations,
            }

        if action == "question_bank":
            raw = get_paper_questions(
                engine,
                paper_code=str(params["paperCode"]),
                principal_type=str(params.get("principalType", "org")),
                principal_code=str(params.get("principalCode", "org_teaching_materials")),
            )
            raw_questions = raw.get("questions")
            questions: list[dict[str, Any]] = [
                item for item in raw_questions if isinstance(item, dict)
            ] if isinstance(raw_questions, list) else []
            paper = _object(raw.get("paper"))
            source_asset = _object(paper.get("sourceAsset"))
            return {
                "questionCode": questions[0].get("questionNo") if questions else None,
                "itemCount": len(questions),
                "citations": [
                    {
                        "assetCode": source_asset.get("code"),
                        "title": source_asset.get("title"),
                    }
                ],
            }

    except AuthorizationError as exc:
        return {
            "statusCode": exc.status_code,
            "error": {"code": "ACCESS_DENIED", "message": "Access denied"},
        }
    except ValueError as exc:
        return {
            "decision": "insufficient_data",
            "reason": str(exc),
        }

    raise ValueError(f"unknown P3 action: {action}")


def _legacy_placeholder(case: dict[str, Any]) -> dict[str, Any]:
    """Use expected structured fields as the legacy placeholder for P3 batch 001.

    Batch 001 is V2-vs-golden, not real old-API dual-read yet.  Later batches can
    replace this with true oldResult captures.
    """
    expected = _object(case.get("expected"))
    return {
        key: expected[key]
        for key in (
            "decision",
            "certificateCode",
            "matchedRuleCode",
            "eventCode",
            "questionCode",
            "statusCode",
            "itemCount",
        )
        if key in expected
    }


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _optional_str(value: Any) -> str | None:
    return None if value is None else str(value)


def _date(value: Any) -> date:
    parsed = _date_or_none(value)
    if parsed is None:
        raise ValueError("date value is required")
    return parsed


def _date_or_none(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _str_list(value: Any) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValueError("expected list")
    return [str(item) for item in value]
