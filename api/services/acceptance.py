"""WP15 acceptance helpers for V2 dual-read comparison and safety gates.

The module is intentionally pure-Python and fixture-driven.  It can score a
small MVP sample in local tests, and the same JSONL contract can later be
filled with the real 100 golden questions before production cutover.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("openai_api_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("dify_app_key", re.compile(r"\bapp-[A-Za-z0-9_-]{20,}\b")),
    ("bearer_token", re.compile(r"\bBearer\s+[A-Za-z0-9._-]{20,}\b")),
    ("assignment_secret", re.compile(r"\b(?:password|secret|api[_-]?key)\s*=\s*['\"]?[^'\"\s#]{8,}", re.IGNORECASE)),
)

DEFAULT_THRESHOLDS: dict[str, float] = {
    "structuredAccuracy": 0.99,
    "citationAccuracy": 0.98,
    "restrictedLeakRate": 0.0,
    "noEvidenceFacts": 0.0,
}


@dataclass(frozen=True)
class SecretFinding:
    path: str
    line_number: int
    pattern_name: str
    preview: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "lineNumber": self.line_number,
            "patternName": self.pattern_name,
            "preview": self.preview,
        }


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    """Load non-empty JSONL records with stable error messages."""
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            record = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: invalid JSONL record") from exc
        if not isinstance(record, dict):
            raise ValueError(f"{path}:{line_number}: JSONL record must be an object")
        records.append(record)
    return records


def evaluate_acceptance_cases(
    cases: list[dict[str, Any]],
    *,
    thresholds: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Score golden cases and classify old/V2 differences.

    Expected record shape:

    ```json
    {
      "id": "ELIG-001",
      "category": "eligibility",
      "oldResult": {"decision": "eligible"},
      "v2Result": {"decision": "eligible", "citations": [...]},
      "expected": {
        "decision": "eligible",
        "certificateCode": "c_constructor_1",
        "citationAssetCodes": ["POLICY_001"],
        "forbiddenTerms": ["restricted body"],
        "requiresCitation": true
      }
    }
    ```
    """
    effective_thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    comparisons: list[dict[str, Any]] = []
    structured_total = 0
    structured_correct = 0
    citation_total = 0
    citation_correct = 0
    restricted_leaks = 0
    no_evidence_facts = 0

    for case in cases:
        case_id = str(case.get("id") or "<missing-id>")
        expected = _object(case.get("expected"))
        old_result = _object(case.get("oldResult"))
        v2_result = _object(case.get("v2Result"))

        structured_expectations = _structured_expectations(expected)
        if structured_expectations:
            structured_total += 1
            if _matches_expected(v2_result, structured_expectations):
                structured_correct += 1

        expected_citation_codes = [str(item) for item in expected.get("citationAssetCodes", [])]
        requires_citation = bool(expected.get("requiresCitation") or expected_citation_codes)
        citations = _citations(v2_result)
        if requires_citation:
            citation_total += 1
            if citations and _citation_codes_match(citations, expected_citation_codes):
                citation_correct += 1
            else:
                no_evidence_facts += 1

        forbidden_terms = [str(item) for item in expected.get("forbiddenTerms", []) if str(item)]
        leaked_terms = _leaked_terms(v2_result, forbidden_terms)
        if leaked_terms:
            restricted_leaks += 1

        classification = classify_difference(
            old_result=old_result,
            v2_result=v2_result,
            expected=expected,
            leaked_terms=leaked_terms,
        )
        comparisons.append(
            {
                "id": case_id,
                "category": case.get("category", "unknown"),
                "classification": classification,
                "v2MatchesExpected": _matches_expected(v2_result, structured_expectations) if structured_expectations else None,
                "oldMatchesExpected": _matches_expected(old_result, structured_expectations) if structured_expectations else None,
                "leakedTerms": leaked_terms,
            }
        )

    structured_accuracy = _ratio(structured_correct, structured_total)
    citation_accuracy = _ratio(citation_correct, citation_total)
    restricted_leak_rate = _ratio(restricted_leaks, len(cases))

    metrics = {
        "totalCases": len(cases),
        "structuredTotal": structured_total,
        "structuredCorrect": structured_correct,
        "structuredAccuracy": structured_accuracy,
        "citationTotal": citation_total,
        "citationCorrect": citation_correct,
        "citationAccuracy": citation_accuracy,
        "restrictedLeakCount": restricted_leaks,
        "restrictedLeakRate": restricted_leak_rate,
        "noEvidenceFacts": no_evidence_facts,
    }
    gates = {
        "structuredAccuracy": structured_accuracy >= effective_thresholds["structuredAccuracy"],
        "citationAccuracy": citation_accuracy >= effective_thresholds["citationAccuracy"],
        "restrictedLeakRate": restricted_leak_rate <= effective_thresholds["restrictedLeakRate"],
        "noEvidenceFacts": no_evidence_facts <= effective_thresholds["noEvidenceFacts"],
    }
    return {
        "status": "pass" if all(gates.values()) else "fail",
        "thresholds": effective_thresholds,
        "metrics": metrics,
        "gates": gates,
        "comparisons": comparisons,
    }


def classify_difference(
    *,
    old_result: dict[str, Any],
    v2_result: dict[str, Any],
    expected: dict[str, Any],
    leaked_terms: list[str] | None = None,
) -> str:
    """Classify a dual-read difference for business review."""
    if leaked_terms:
        return "security_leak"
    if expected.get("ambiguous"):
        return "business_ambiguous"
    if expected.get("dataStatus") == "missing" or v2_result.get("decision") == "insufficient_data":
        return "data_missing"

    structured_expectations = _structured_expectations(expected)
    old_matches = _matches_expected(old_result, structured_expectations) if structured_expectations else old_result == v2_result
    v2_matches = _matches_expected(v2_result, structured_expectations) if structured_expectations else old_result == v2_result

    if v2_matches and old_matches:
        return "match"
    if v2_matches and not old_matches:
        return "old_wrong"
    if old_matches and not v2_matches:
        return "new_wrong"
    return "needs_review"


def scan_secret_text(path: str, text: str) -> list[SecretFinding]:
    """Return likely secret findings in one text blob."""
    findings: list[SecretFinding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for pattern_name, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                findings.append(
                    SecretFinding(
                        path=path,
                        line_number=line_number,
                        pattern_name=pattern_name,
                        preview=_redact(line.strip()),
                    )
                )
    return findings


def scan_secret_paths(paths: list[str | Path]) -> list[SecretFinding]:
    """Scan files/directories for obvious key/token mistakes."""
    findings: list[SecretFinding] = []
    for root in paths:
        path = Path(root)
        if path.is_dir():
            for child in sorted(item for item in path.rglob("*") if item.is_file()):
                findings.extend(_scan_file(child))
        elif path.is_file():
            findings.extend(_scan_file(path))
    return findings


def run_acceptance_from_jsonl(path: str | Path) -> dict[str, Any]:
    """Load a JSONL case file and return a gate report."""
    return evaluate_acceptance_cases(load_jsonl(path))


def _scan_file(path: Path) -> list[SecretFinding]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    return scan_secret_text(str(path), text)


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _structured_expectations(expected: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "decision",
        "certificateCode",
        "matchedRuleCode",
        "eventCode",
        "questionCode",
    )
    return {field: expected[field] for field in fields if field in expected}


def _matches_expected(result: dict[str, Any], expected_fields: dict[str, Any]) -> bool:
    return all(_get_camel_or_snake(result, field) == expected_value for field, expected_value in expected_fields.items())


def _get_camel_or_snake(result: dict[str, Any], field: str) -> Any:
    if field in result:
        return result[field]
    snake = re.sub(r"(?<!^)([A-Z])", r"_\1", field).lower()
    return result.get(snake)


def _citations(result: dict[str, Any]) -> list[dict[str, Any]]:
    citations = result.get("citations")
    if isinstance(citations, list):
        return [item for item in citations if isinstance(item, dict)]
    cards = result.get("cards")
    if not isinstance(cards, list):
        return []
    flattened: list[dict[str, Any]] = []
    for card in cards:
        if isinstance(card, dict) and isinstance(card.get("citations"), list):
            flattened.extend(item for item in card["citations"] if isinstance(item, dict))
    return flattened


def _citation_codes_match(citations: list[dict[str, Any]], expected_codes: list[str]) -> bool:
    if not expected_codes:
        return bool(citations)
    actual = {str(citation.get("assetCode") or citation.get("asset_code") or "") for citation in citations}
    return set(expected_codes).issubset(actual)


def _leaked_terms(result: dict[str, Any], forbidden_terms: list[str]) -> list[str]:
    serialized = json.dumps(result, ensure_ascii=False).lower()
    return [term for term in forbidden_terms if term.lower() in serialized]


def _ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 1.0
    return numerator / denominator


def _redact(text: str) -> str:
    redacted = text
    for _, pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted[:160]
