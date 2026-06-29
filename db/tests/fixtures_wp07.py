"""WP07 fixtures — exam events, phases, and score rules."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine


def seed_exam_event(
    engine: Engine,
    *,
    code: str,
    certificate_code: str = "c_constructor_1",
    exam_year: int = 2026,
    region_code: str = "CN",
    status: str = "scheduled",
) -> dict[str, Any]:
    with engine.begin() as conn:
        row = conn.execute(
            text("""
                INSERT INTO assessment.exam_event (
                    code, certificate_id, exam_year, region_code, status
                )
                SELECT :code, id, :exam_year, :region_code, :status
                  FROM core.certificate
                 WHERE code = :certificate_code
                RETURNING id, code, certificate_id, exam_year, region_code, status
            """),
            {
                "code": code,
                "certificate_code": certificate_code,
                "exam_year": exam_year,
                "region_code": region_code,
                "status": status,
            },
        ).fetchone()
    if row is None:
        raise ValueError("certificate not found")
    return dict(row._mapping)


def seed_exam_phase(
    engine: Engine,
    *,
    event_id: int,
    phase_type: str,
    starts_on: str,
    ends_on: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    with engine.begin() as conn:
        row = conn.execute(
            text("""
                INSERT INTO assessment.exam_phase (
                    exam_event_id, phase_type, starts_on, ends_on, note
                )
                VALUES (:event_id, :phase_type, :starts_on, :ends_on, :note)
                RETURNING id, exam_event_id, phase_type, starts_on, ends_on, note
            """),
            {
                "event_id": event_id,
                "phase_type": phase_type,
                "starts_on": starts_on,
                "ends_on": ends_on,
                "note": note,
            },
        ).fetchone()
    if row is None:
        raise RuntimeError("exam phase insert failed")
    return dict(row._mapping)


def seed_subject_score_rule(
    engine: Engine,
    *,
    event_id: int,
    subject_code: str = "subj_constructor_mgmt",
    full_mark: Decimal | int | str = 100,
    pass_mark: Decimal | int | str = 60,
) -> dict[str, Any]:
    with engine.begin() as conn:
        row = conn.execute(
            text("""
                INSERT INTO assessment.subject_score_rule (
                    exam_event_id, subject_id, full_mark, pass_mark
                )
                SELECT :event_id, id, :full_mark, :pass_mark
                  FROM core.exam_subject
                 WHERE code = :subject_code
                RETURNING id, exam_event_id, subject_id, full_mark, pass_mark
            """),
            {
                "event_id": event_id,
                "subject_code": subject_code,
                "full_mark": Decimal(str(full_mark)),
                "pass_mark": Decimal(str(pass_mark)),
            },
        ).fetchone()
    if row is None:
        raise ValueError("subject not found")
    return dict(row._mapping)
