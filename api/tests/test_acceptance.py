"""WP15 acceptance gate tests."""

from __future__ import annotations

import json
import subprocess
import sys

from api.services.acceptance import (
    classify_difference,
    evaluate_acceptance_cases,
    scan_secret_text,
)


def test_acceptance_metrics_pass_for_clean_sample():
    report = evaluate_acceptance_cases(
        [
            {
                "id": "ELIG-001",
                "category": "eligibility",
                "oldResult": {"decision": "insufficient_data", "certificateCode": "c_constructor_1"},
                "v2Result": {
                    "decision": "eligible",
                    "certificateCode": "c_constructor_1",
                    "matchedRuleCode": "RULE_01",
                    "citations": [{"assetCode": "POLICY_001"}],
                },
                "expected": {
                    "decision": "eligible",
                    "certificateCode": "c_constructor_1",
                    "matchedRuleCode": "RULE_01",
                    "citationAssetCodes": ["POLICY_001"],
                    "requiresCitation": True,
                    "forbiddenTerms": ["restricted body"],
                },
            }
        ]
    )

    assert report["status"] == "pass"
    assert report["metrics"]["structuredAccuracy"] == 1.0
    assert report["metrics"]["citationAccuracy"] == 1.0
    assert report["metrics"]["restrictedLeakRate"] == 0.0
    assert report["comparisons"][0]["classification"] == "old_wrong"


def test_acceptance_fails_on_missing_citation_and_restricted_leak():
    report = evaluate_acceptance_cases(
        [
            {
                "id": "GEN-LEAK",
                "category": "generation",
                "oldResult": {"status": "succeeded"},
                "v2Result": {"status": "succeeded", "body": "restricted body should not appear"},
                "expected": {
                    "requiresCitation": True,
                    "forbiddenTerms": ["restricted body"],
                },
            }
        ]
    )

    assert report["status"] == "fail"
    assert report["metrics"]["noEvidenceFacts"] == 1
    assert report["metrics"]["restrictedLeakCount"] == 1
    assert report["comparisons"][0]["classification"] == "security_leak"


def test_difference_classification_business_and_data_cases():
    assert (
        classify_difference(
            old_result={},
            v2_result={},
            expected={"ambiguous": True},
        )
        == "business_ambiguous"
    )
    assert (
        classify_difference(
            old_result={},
            v2_result={"decision": "insufficient_data"},
            expected={},
        )
        == "data_missing"
    )
    assert (
        classify_difference(
            old_result={"decision": "eligible"},
            v2_result={"decision": "not_eligible"},
            expected={"decision": "eligible"},
        )
        == "new_wrong"
    )


def test_secret_scan_redacts_key_preview():
    fake_key = "app-" + "abcdefghijklmnopqrstuvwxyz"
    findings = scan_secret_text("sample.env", f"DIFY_API_KEY={fake_key}\n")

    assert len(findings) == 1
    assert findings[0].pattern_name == "dify_app_key"
    assert "abcdefghijklmnopqrstuvwxyz" not in findings[0].preview


def test_acceptance_cli_evaluates_sample_jsonl():
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/wp15_acceptance.py",
            "evaluate",
            "docs/implementation/evaluation/wp15_golden_cases.sample.jsonl",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0, proc.stderr
    report = json.loads(proc.stdout)
    assert report["status"] == "pass"
    assert report["metrics"]["totalCases"] == 3
