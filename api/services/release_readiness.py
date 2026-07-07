"""WP16 release readiness helpers.

These helpers validate a rollout/recovery runbook without touching production
traffic.  The contract is JSON-first so another model or operator can fill the
runbook, run the CLI, and get deterministic gate results before any real
feature-flag or database operation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REQUIRED_ROLLOUT_STAGES = ("internal", "canary", "full")
REQUIRED_MONITORS = (
    "five_xx_rate",
    "query_latency_p95_ms",
    "retrieval_hit_rate",
    "permission_denial_rate",
    "generation_failure_rate",
    "missing_citation_rate",
)
MAX_ROLLBACK_MINUTES = 30
MIN_OLD_DB_READONLY_CYCLES = 2


@dataclass(frozen=True)
class GateResult:
    name: str
    status: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "status": self.status, "message": self.message}


def load_release_plan(path: str | Path) -> dict[str, Any]:
    """Load a WP16 release plan JSON file."""
    try:
        plan = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON release plan") from exc
    if not isinstance(plan, dict):
        raise ValueError(f"{path}: release plan must be a JSON object")
    return plan


def evaluate_release_readiness(plan: dict[str, Any]) -> dict[str, Any]:
    """Evaluate restore, rollback, rollout, monitor, and old-DB gates."""
    gates = [
        _restore_gate(plan.get("restoreDrill")),
        _rollback_gate(plan.get("rollbackDrill")),
        _rollout_gate(plan.get("rollout")),
        _monitor_gate(plan.get("monitors")),
        _old_db_gate(plan.get("oldDatabase")),
        _reports_gate(plan.get("reports")),
    ]
    gate_dicts = [gate.to_dict() for gate in gates]
    return {
        "status": "pass" if all(gate.status == "pass" for gate in gates) else "fail",
        "gates": gate_dicts,
        "summary": {
            "passed": sum(1 for gate in gates if gate.status == "pass"),
            "failed": sum(1 for gate in gates if gate.status == "fail"),
            "total": len(gates),
        },
    }


def run_release_readiness_from_json(path: str | Path) -> dict[str, Any]:
    """Load and evaluate a release plan JSON file."""
    return evaluate_release_readiness(load_release_plan(path))


def _restore_gate(value: Any) -> GateResult:
    drill = value if isinstance(value, dict) else {}
    missing = [
        field
        for field in (
            "databaseRestored",
            "objectStorageRestored",
            "rowCountsMatch",
            "hashesMatch",
            "referencesValid",
        )
        if drill.get(field) is not True
    ]
    if missing:
        return GateResult("restore", "fail", f"restore drill missing or failed: {', '.join(missing)}")
    return GateResult("restore", "pass", "database/object restore, row counts, hashes, and references verified")


def _rollback_gate(value: Any) -> GateResult:
    drill = value if isinstance(value, dict) else {}
    flags = drill.get("featureFlags")
    api = drill.get("apiRollback")
    elapsed = drill.get("elapsedMinutes")
    if not isinstance(flags, dict) or not flags:
        return GateResult("rollback", "fail", "feature flag rollback map is required")
    if any(flag_value not in {"old", "v1", False} for flag_value in flags.values()):
        return GateResult("rollback", "fail", "all feature flags must be set back to old/v1/false in rollback drill")
    if api is not True:
        return GateResult("rollback", "fail", "API rollback drill must be explicitly successful")
    if not isinstance(elapsed, int | float) or elapsed > MAX_ROLLBACK_MINUTES:
        return GateResult("rollback", "fail", f"rollback must finish within {MAX_ROLLBACK_MINUTES} minutes")
    return GateResult("rollback", "pass", f"rollback drill completed in {elapsed} minutes")


def _rollout_gate(value: Any) -> GateResult:
    rollout = value if isinstance(value, dict) else {}
    stages = rollout.get("stages")
    if not isinstance(stages, list):
        return GateResult("rollout", "fail", "rollout.stages must list internal/canary/full stages")
    stage_names = [stage.get("name") for stage in stages if isinstance(stage, dict)]
    if tuple(stage_names) != REQUIRED_ROLLOUT_STAGES:
        return GateResult("rollout", "fail", "rollout stages must be ordered: internal -> canary -> full")
    for stage in stages:
        if not isinstance(stage, dict):
            return GateResult("rollout", "fail", "each rollout stage must be an object")
        if stage.get("approved") is not True:
            return GateResult("rollout", "fail", f"stage {stage.get('name')} is not approved")
        traffic = stage.get("trafficPercent")
        if not isinstance(traffic, int | float) or traffic < 0 or traffic > 100:
            return GateResult("rollout", "fail", f"stage {stage.get('name')} has invalid trafficPercent")
    if stages[0]["trafficPercent"] != 0 or not 0 < stages[1]["trafficPercent"] < 100 or stages[2]["trafficPercent"] != 100:
        return GateResult("rollout", "fail", "traffic must be internal=0, canary between 0 and 100, full=100")
    return GateResult("rollout", "pass", "rollout stages and traffic percentages are valid")


def _monitor_gate(value: Any) -> GateResult:
    monitors = value if isinstance(value, dict) else {}
    missing = [name for name in REQUIRED_MONITORS if name not in monitors]
    if missing:
        return GateResult("monitors", "fail", f"missing monitors: {', '.join(missing)}")
    failed = []
    for name in REQUIRED_MONITORS:
        item = monitors.get(name)
        if not isinstance(item, dict):
            failed.append(f"{name}: invalid")
            continue
        actual = item.get("actual")
        threshold = item.get("threshold")
        direction = item.get("direction", "lte")
        if not isinstance(actual, int | float) or not isinstance(threshold, int | float):
            failed.append(f"{name}: actual/threshold required")
        elif direction == "gte" and actual < threshold:
            failed.append(f"{name}: {actual} < {threshold}")
        elif direction != "gte" and actual > threshold:
            failed.append(f"{name}: {actual} > {threshold}")
    if failed:
        return GateResult("monitors", "fail", "; ".join(failed))
    return GateResult("monitors", "pass", "5xx/latency/retrieval/permission/generation/citation monitors are within thresholds")


def _old_db_gate(value: Any) -> GateResult:
    old_db = value if isinstance(value, dict) else {}
    if old_db.get("mode") != "readonly":
        return GateResult("old_database", "fail", "old database must be planned as readonly")
    cycles = old_db.get("retentionReleaseCycles")
    if not isinstance(cycles, int) or cycles < MIN_OLD_DB_READONLY_CYCLES:
        return GateResult("old_database", "fail", f"old database must be retained for at least {MIN_OLD_DB_READONLY_CYCLES} release cycles")
    if old_db.get("deleteScheduled") is True:
        return GateResult("old_database", "fail", "old database must not be scheduled for immediate deletion")
    return GateResult("old_database", "pass", f"old database readonly retention is {cycles} release cycles")


def _reports_gate(value: Any) -> GateResult:
    reports = value if isinstance(value, dict) else {}
    missing = [
        field
        for field in (
            "launchReport",
            "restoreReport",
            "retirementDecision",
        )
        if not reports.get(field)
    ]
    if missing:
        return GateResult("reports", "fail", f"missing required report entries: {', '.join(missing)}")
    return GateResult("reports", "pass", "launch, restore, and retirement decision report entries exist")
