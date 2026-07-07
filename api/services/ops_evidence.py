"""P6 operations evidence helpers.

These helpers collect and compare local evidence for production hardening:
database restore checks, reference integrity checks, and API monitor samples.
They are intentionally deterministic so an execution agent can run them before
touching real rollout switches.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

CRITICAL_TABLES = (
    "core.certificate",
    "core.exam_subject",
    "knowledge.collection",
    "knowledge.asset",
    "knowledge.asset_version",
    "knowledge.fragment",
    "knowledge.knowledge_point",
    "knowledge.fragment_knowledge_point",
    "policy.document",
    "policy.document_version",
    "policy.clause",
    "policy.eligibility_rule",
    "policy.eligibility_rule_evidence",
    "assessment.paper",
    "assessment.question",
    "assessment.question_knowledge_point",
    "content.product",
    "content.product_version",
    "content.chapter",
    "content.chapter_knowledge_point",
    "generation.run",
    "generation.citation",
    "generation.output",
)

DEFAULT_MONITOR_THRESHOLDS = {
    "five_xx_rate": {"threshold": 0.001, "direction": "lte"},
    "query_latency_p95_ms": {"threshold": 500, "direction": "lte"},
    "retrieval_hit_rate": {"threshold": 0.9, "direction": "gte"},
    "permission_denial_rate": {"threshold": 0.05, "direction": "lte"},
    "generation_failure_rate": {"threshold": 0.01, "direction": "lte"},
    "missing_citation_rate": {"threshold": 0, "direction": "lte"},
}

_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")


def build_database_manifest(engine: Engine, *, tables: tuple[str, ...] = CRITICAL_TABLES) -> dict[str, Any]:
    """Build a row-count/hash manifest for critical V2 tables."""
    manifest_tables: dict[str, dict[str, Any]] = {}
    with engine.connect() as conn:
        for table_name in tables:
            if not _table_exists(conn=conn, table_name=table_name):
                manifest_tables[table_name] = {"status": "missing", "rowCount": None, "sha256": None}
                continue
            row_texts = [
                row.row_json
                for row in conn.execute(
                    text(f"SELECT to_jsonb(t)::text AS row_json FROM {_qualified_table(table_name)} AS t ORDER BY to_jsonb(t)::text")
                )
            ]
            manifest_tables[table_name] = {
                "status": "present",
                "rowCount": len(row_texts),
                "sha256": _sha256_lines(row_texts),
            }
        reference_checks = _reference_checks(conn)

    return {
        "generatedAt": datetime.now(UTC).isoformat(),
        "criticalTables": list(tables),
        "tables": manifest_tables,
        "referenceChecks": reference_checks,
    }


def compare_restore_manifests(source: dict[str, Any], restored: dict[str, Any]) -> dict[str, Any]:
    """Compare source/restored manifests for P6 restore gates."""
    source_tables = _table_map(source)
    restored_tables = _table_map(restored)
    table_names = sorted(set(source_tables) | set(restored_tables))
    row_diffs = []
    hash_diffs = []
    missing_tables = []
    for table_name in table_names:
        source_row = source_tables.get(table_name)
        restored_row = restored_tables.get(table_name)
        if source_row is None or restored_row is None:
            missing_tables.append(table_name)
            continue
        if source_row.get("rowCount") != restored_row.get("rowCount"):
            row_diffs.append(
                {
                    "table": table_name,
                    "source": source_row.get("rowCount"),
                    "restored": restored_row.get("rowCount"),
                }
            )
        if source_row.get("sha256") != restored_row.get("sha256"):
            hash_diffs.append(table_name)

    reference_failures = [
        {"name": name, "invalidCount": item.get("invalidCount")}
        for name, item in _reference_map(restored).items()
        if item.get("invalidCount") != 0
    ]
    return {
        "rowCountsMatch": not row_diffs and not missing_tables,
        "hashesMatch": not hash_diffs and not missing_tables,
        "referencesValid": not reference_failures,
        "tableCount": len(table_names),
        "rowDiffs": row_diffs,
        "hashDiffs": hash_diffs,
        "missingTables": missing_tables,
        "referenceFailures": reference_failures,
    }


def summarize_api_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize API smoke/performance samples into WP16/P6 monitor metrics."""
    total = len(samples)
    latencies: list[float] = []
    for sample in samples:
        latency = _number(sample.get("latencyMs"))
        if latency is not None:
            latencies.append(latency)
    five_xx = sum(1 for sample in samples if _status_code(sample) >= 500)
    permission_denied = sum(1 for sample in samples if sample.get("permissionDenied") is True or _status_code(sample) == 403)

    retrieval_samples = [sample for sample in samples if isinstance(sample.get("retrievalHit"), bool)]
    retrieval_hits = sum(1 for sample in retrieval_samples if sample.get("retrievalHit") is True)

    generation_samples = [
        sample
        for sample in samples
        if sample.get("category") == "generation" or "generation" in str(sample.get("route", ""))
    ]
    generation_failures = sum(
        1
        for sample in generation_samples
        if sample.get("generationStatus") == "failed" or _status_code(sample) >= 500
    )

    citation_required = [sample for sample in samples if sample.get("requiresCitation") is True]
    missing_citations = sum(1 for sample in citation_required if int(sample.get("citationCount") or 0) <= 0)

    monitors = {
        "five_xx_rate": _monitor(_rate(five_xx, total), "five_xx_rate"),
        "query_latency_p95_ms": _monitor(_percentile(latencies, 95), "query_latency_p95_ms"),
        "retrieval_hit_rate": _monitor(_rate(retrieval_hits, len(retrieval_samples), empty_default=1.0), "retrieval_hit_rate"),
        "permission_denial_rate": _monitor(_rate(permission_denied, total), "permission_denial_rate"),
        "generation_failure_rate": _monitor(_rate(generation_failures, len(generation_samples)), "generation_failure_rate"),
        "missing_citation_rate": _monitor(_rate(missing_citations, len(citation_required)), "missing_citation_rate"),
    }
    return {
        "sampleCount": total,
        "latencyCount": len(latencies),
        "generationSampleCount": len(generation_samples),
        "citationRequiredCount": len(citation_required),
        "monitors": monitors,
    }


def load_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: JSON object required")
    return value


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    samples = []
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        item = json.loads(stripped)
        if not isinstance(item, dict):
            raise ValueError(f"{path}:{line_number}: JSON object required")
        samples.append(item)
    return samples


def write_json_report(value: dict[str, Any], path: str | Path | None) -> str:
    rendered = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
    if path is not None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(rendered + "\n", encoding="utf-8")
    return rendered


def _reference_checks(conn: Any) -> dict[str, dict[str, Any]]:
    checks = {
        "generation_citation_fragment": """
            SELECT count(*) AS invalid_count
              FROM generation.citation c
              LEFT JOIN knowledge.fragment f ON f.id = c.fragment_id
             WHERE f.id IS NULL
        """,
        "fragment_knowledge_point": """
            SELECT count(*) AS invalid_count
              FROM knowledge.fragment_knowledge_point fkp
              LEFT JOIN knowledge.fragment f ON f.id = fkp.fragment_id
              LEFT JOIN knowledge.knowledge_point kp ON kp.id = fkp.kp_id
             WHERE f.id IS NULL OR kp.id IS NULL
        """,
        "question_knowledge_point": """
            SELECT count(*) AS invalid_count
              FROM assessment.question_knowledge_point qkp
              LEFT JOIN assessment.question q ON q.id = qkp.question_id
              LEFT JOIN knowledge.knowledge_point kp ON kp.id = qkp.kp_id
             WHERE q.id IS NULL OR kp.id IS NULL
        """,
        "chapter_knowledge_point": """
            SELECT count(*) AS invalid_count
              FROM content.chapter_knowledge_point ckp
              LEFT JOIN content.chapter c ON c.id = ckp.chapter_id
              LEFT JOIN knowledge.knowledge_point kp ON kp.id = ckp.kp_id
             WHERE c.id IS NULL OR kp.id IS NULL
        """,
    }
    results: dict[str, dict[str, Any]] = {}
    for name, statement in checks.items():
        try:
            invalid_count = conn.execute(text(statement)).scalar_one()
        except Exception as exc:  # pragma: no cover - defensive for partial dev DBs
            results[name] = {"status": "error", "invalidCount": None, "message": type(exc).__name__}
            continue
        results[name] = {"status": "checked", "invalidCount": int(invalid_count)}
    return results


def _table_exists(*, conn: Any, table_name: str) -> bool:
    return bool(conn.execute(text("SELECT to_regclass(:table_name) IS NOT NULL"), {"table_name": table_name}).scalar_one())


def _qualified_table(table_name: str) -> str:
    parts = table_name.split(".")
    if len(parts) != 2 or not all(_IDENTIFIER.fullmatch(part) for part in parts):
        raise ValueError(f"Unsafe table name: {table_name}")
    return ".".join(f'"{part}"' for part in parts)


def _sha256_lines(lines: list[str]) -> str:
    digest = hashlib.sha256()
    for line in lines:
        digest.update(line.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _table_map(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    tables = manifest.get("tables")
    return tables if isinstance(tables, dict) else {}


def _reference_map(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    checks = manifest.get("referenceChecks")
    return checks if isinstance(checks, dict) else {}


def _number(value: Any) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    return None


def _status_code(sample: dict[str, Any]) -> int:
    value = sample.get("statusCode")
    return int(value) if isinstance(value, int) else 0


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil((percentile / 100) * len(ordered)) - 1)
    return ordered[index]


def _rate(numerator: int, denominator: int, *, empty_default: float = 0.0) -> float:
    if denominator <= 0:
        return empty_default
    return numerator / denominator


def _monitor(actual: float, name: str) -> dict[str, Any]:
    threshold = DEFAULT_MONITOR_THRESHOLDS[name]
    return {
        "actual": actual,
        "threshold": threshold["threshold"],
        "direction": threshold["direction"],
    }
