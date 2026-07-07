"""WP16 release readiness gate tests."""

from __future__ import annotations

import json
import subprocess
import sys

from api.services.release_readiness import evaluate_release_readiness


def _valid_plan() -> dict:
    return {
        "restoreDrill": {
            "databaseRestored": True,
            "objectStorageRestored": True,
            "rowCountsMatch": True,
            "hashesMatch": True,
            "referencesValid": True,
        },
        "rollbackDrill": {
            "featureFlags": {
                "USE_CERTIFICATE_API_V2": "old",
                "USE_ELIGIBILITY_API_V2": "old",
            },
            "apiRollback": True,
            "elapsedMinutes": 12,
        },
        "rollout": {
            "stages": [
                {"name": "internal", "trafficPercent": 0, "approved": True},
                {"name": "canary", "trafficPercent": 10, "approved": True},
                {"name": "full", "trafficPercent": 100, "approved": True},
            ]
        },
        "monitors": {
            "five_xx_rate": {"actual": 0, "threshold": 0.001, "direction": "lte"},
            "query_latency_p95_ms": {"actual": 180, "threshold": 500, "direction": "lte"},
            "retrieval_hit_rate": {"actual": 0.96, "threshold": 0.9, "direction": "gte"},
            "permission_denial_rate": {"actual": 0.02, "threshold": 0.05, "direction": "lte"},
            "generation_failure_rate": {"actual": 0, "threshold": 0.01, "direction": "lte"},
            "missing_citation_rate": {"actual": 0, "threshold": 0, "direction": "lte"},
        },
        "oldDatabase": {
            "mode": "readonly",
            "retentionReleaseCycles": 2,
            "deleteScheduled": False,
        },
        "reports": {
            "launchReport": "launch.md",
            "restoreReport": "restore.md",
            "retirementDecision": "decision.md",
        },
    }


def test_release_readiness_passes_for_valid_plan():
    report = evaluate_release_readiness(_valid_plan())

    assert report["status"] == "pass"
    assert report["summary"] == {"passed": 6, "failed": 0, "total": 6}


def test_release_readiness_fails_restore_and_rollback_gates():
    plan = _valid_plan()
    plan["restoreDrill"]["hashesMatch"] = False
    plan["rollbackDrill"]["featureFlags"]["USE_CERTIFICATE_API_V2"] = "v2"

    report = evaluate_release_readiness(plan)
    failed = {gate["name"]: gate["message"] for gate in report["gates"] if gate["status"] == "fail"}

    assert report["status"] == "fail"
    assert "restore" in failed
    assert "rollback" in failed


def test_release_readiness_fails_bad_rollout_monitor_and_old_db():
    plan = _valid_plan()
    plan["rollout"]["stages"][1]["trafficPercent"] = 100
    plan["monitors"]["retrieval_hit_rate"]["actual"] = 0.5
    plan["oldDatabase"]["retentionReleaseCycles"] = 1

    report = evaluate_release_readiness(plan)
    failed = {gate["name"]: gate["message"] for gate in report["gates"] if gate["status"] == "fail"}

    assert report["status"] == "fail"
    assert "rollout" in failed
    assert "monitors" in failed
    assert "old_database" in failed


def test_release_cli_evaluates_sample_plan():
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/wp16_release.py",
            "docs/implementation/release/wp16_release_plan.sample.json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0, proc.stderr
    report = json.loads(proc.stdout)
    assert report["status"] == "pass"
    assert report["summary"]["total"] == 6
