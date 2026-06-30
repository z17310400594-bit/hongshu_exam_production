"""P6 operations evidence tests."""

from __future__ import annotations

import json
import subprocess
import sys

from api.services.ops_evidence import compare_restore_manifests, summarize_api_samples


def _manifest(*, question_rows: int = 3, question_hash: str = "hash-a", invalid_refs: int = 0) -> dict:
    return {
        "tables": {
            "assessment.question": {"status": "present", "rowCount": question_rows, "sha256": question_hash},
            "generation.citation": {"status": "present", "rowCount": 1, "sha256": "hash-citation"},
        },
        "referenceChecks": {
            "generation_citation_fragment": {"status": "checked", "invalidCount": invalid_refs},
        },
    }


def test_compare_restore_manifests_passes_when_counts_hashes_and_refs_match():
    report = compare_restore_manifests(_manifest(), _manifest())

    assert report["rowCountsMatch"] is True
    assert report["hashesMatch"] is True
    assert report["referencesValid"] is True
    assert report["rowDiffs"] == []
    assert report["hashDiffs"] == []


def test_compare_restore_manifests_reports_row_hash_and_reference_failures():
    report = compare_restore_manifests(
        _manifest(),
        _manifest(question_rows=2, question_hash="hash-b", invalid_refs=1),
    )

    assert report["rowCountsMatch"] is False
    assert report["hashesMatch"] is False
    assert report["referencesValid"] is False
    assert report["rowDiffs"][0]["table"] == "assessment.question"
    assert report["hashDiffs"] == ["assessment.question"]
    assert report["referenceFailures"][0]["name"] == "generation_citation_fragment"


def test_summarize_api_samples_calculates_release_monitors():
    report = summarize_api_samples(
        [
            {
                "route": "/api/v2/knowledge/search",
                "statusCode": 200,
                "latencyMs": 120,
                "retrievalHit": True,
                "requiresCitation": True,
                "citationCount": 1,
            },
            {
                "route": "/api/v2/generations",
                "category": "generation",
                "statusCode": 200,
                "latencyMs": 450,
                "generationStatus": "succeeded",
                "requiresCitation": True,
                "citationCount": 1,
            },
            {
                "route": "/api/v2/generations",
                "category": "generation",
                "statusCode": 200,
                "latencyMs": 220,
                "generationStatus": "failed",
                "requiresCitation": True,
                "citationCount": 0,
            },
            {
                "route": "/api/v2/knowledge/search",
                "statusCode": 403,
                "latencyMs": 80,
                "retrievalHit": False,
            },
            {
                "route": "/api/v2/certificates",
                "statusCode": 503,
                "latencyMs": 900,
            },
        ]
    )

    monitors = report["monitors"]
    assert report["sampleCount"] == 5
    assert monitors["query_latency_p95_ms"]["actual"] == 900
    assert monitors["five_xx_rate"]["actual"] == 0.2
    assert monitors["retrieval_hit_rate"]["actual"] == 0.5
    assert monitors["permission_denial_rate"]["actual"] == 0.2
    assert monitors["generation_failure_rate"]["actual"] == 0.5
    assert monitors["missing_citation_rate"]["actual"] == 1 / 3


def test_p6_ops_cli_summarizes_api_samples(tmp_path):
    sample_path = tmp_path / "samples.jsonl"
    sample_path.write_text(
        "\n".join(
            [
                json.dumps({"route": "/api/v2/knowledge/search", "statusCode": 200, "latencyMs": 100, "retrievalHit": True}),
                json.dumps({"route": "/api/v2/generations", "statusCode": 200, "latencyMs": 200, "category": "generation"}),
            ]
        ),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [sys.executable, "scripts/p6_ops.py", "summarize-api-samples", "--input", str(sample_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0, proc.stderr
    report = json.loads(proc.stdout)
    assert report["sampleCount"] == 2
    assert report["monitors"]["query_latency_p95_ms"]["actual"] == 200
