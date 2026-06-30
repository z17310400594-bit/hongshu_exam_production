from __future__ import annotations

from api.services.acceptance import evaluate_acceptance_cases, load_jsonl
from api.services.p3_golden import run_p3_action


def test_p3_batch001_cases_load():
    cases = load_jsonl("docs/implementation/evaluation/p3_golden_cases.batch001.jsonl")

    assert len(cases) == 10
    assert {case["action"] for case in cases} >= {
        "certificate_detail",
        "exam_event",
        "eligibility",
        "knowledge_search",
        "question_bank",
    }


def test_acceptance_supports_p3_status_code_and_item_count_expectations():
    report = evaluate_acceptance_cases(
        [
            {
                "id": "SEC",
                "category": "permission",
                "oldResult": {"statusCode": 403},
                "v2Result": {"statusCode": 403},
                "expected": {"statusCode": 403, "forbiddenTerms": ["secret body"]},
            },
            {
                "id": "SEARCH",
                "category": "knowledge_search",
                "oldResult": {"decision": "found", "itemCount": 1},
                "v2Result": {
                    "decision": "found",
                    "itemCount": 1,
                    "citations": [{"assetCode": "A1"}],
                },
                "expected": {
                    "decision": "found",
                    "itemCount": 1,
                    "citationAssetCodes": ["A1"],
                    "requiresCitation": True,
                },
            },
        ]
    )

    assert report["status"] == "pass"
    assert report["metrics"]["structuredCorrect"] == 2


def test_p3_unknown_action_fails_with_stable_message():
    try:
        run_p3_action(None, action="unknown", params={})  # type: ignore[arg-type]
    except ValueError as exc:
        assert "unknown P3 action" in str(exc)
    else:
        raise AssertionError("expected ValueError")
