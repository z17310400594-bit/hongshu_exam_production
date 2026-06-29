"""Exam event service — WP07 MVP schedule and score lookup."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Engine


def _to_number(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def get_exam_events(
    engine: Engine,
    *,
    certificate_code: str,
    region_code: str = "CN",
    exam_year: int | None = None,
    as_of: date | None = None,
) -> dict[str, Any]:
    """Return exam events with phases and score rules for one certificate.

    If `exam_year` is omitted, selection is deterministic:
    current calendar year first, then nearest future year, then latest history.
    """
    today = as_of or date.today()
    with engine.connect() as conn:
        cert = conn.execute(
            text("""
                SELECT id, code, name, category_code
                  FROM core.certificate
                 WHERE code = :certificate_code
                   AND status = 'active'
            """),
            {"certificate_code": certificate_code},
        ).fetchone()
        if cert is None:
            raise ValueError("certificate not found")

        event_filter = ""
        event_params = {
            "certificate_id": cert.id,
            "region_code": region_code,
        }
        if exam_year is not None:
            event_filter = "AND exam_year = :exam_year"
            event_params["exam_year"] = exam_year

        event_rows = conn.execute(
            text(f"""
                SELECT id, code, exam_year, region_code, status
                  FROM assessment.exam_event
                 WHERE certificate_id = :certificate_id
                   AND region_code = :region_code
                   {event_filter}
                 ORDER BY exam_year DESC, code
            """),
            event_params,
        ).fetchall()

        if not event_rows:
            return {
                "certificate": dict(cert._mapping),
                "selectedEvent": None,
                "events": [],
            }

        event_ids = [row.id for row in event_rows]
        phase_rows = conn.execute(
            text("""
                SELECT exam_event_id, phase_type, starts_on, ends_on, note
                  FROM assessment.exam_phase
                 WHERE exam_event_id IN :event_ids
                 ORDER BY starts_on, phase_type
            """).bindparams(bindparam("event_ids", expanding=True)),
            {"event_ids": tuple(event_ids)},
        ).fetchall()
        score_rows = conn.execute(
            text("""
                SELECT
                    ssr.exam_event_id,
                    s.code AS subject_code,
                    s.name AS subject_name,
                    ssr.full_mark,
                    ssr.pass_mark
                  FROM assessment.subject_score_rule ssr
                  JOIN core.exam_subject s ON s.id = ssr.subject_id
                 WHERE ssr.exam_event_id IN :event_ids
                 ORDER BY s.code
            """).bindparams(bindparam("event_ids", expanding=True)),
            {"event_ids": tuple(event_ids)},
        ).fetchall()

    phases_by_event: dict[int, list[dict[str, Any]]] = {event_id: [] for event_id in event_ids}
    for row in phase_rows:
        phases_by_event[row.exam_event_id].append(
            {
                "phaseType": row.phase_type,
                "startsOn": row.starts_on.isoformat(),
                "endsOn": row.ends_on.isoformat() if row.ends_on else None,
                "note": row.note,
            }
        )

    scores_by_event: dict[int, list[dict[str, Any]]] = {event_id: [] for event_id in event_ids}
    for row in score_rows:
        scores_by_event[row.exam_event_id].append(
            {
                "subjectCode": row.subject_code,
                "subjectName": row.subject_name,
                "fullMark": _to_number(row.full_mark),
                "passMark": _to_number(row.pass_mark),
            }
        )

    events = [
        {
            "id": row.id,
            "code": row.code,
            "examYear": row.exam_year,
            "regionCode": row.region_code,
            "status": row.status,
            "phases": phases_by_event[row.id],
            "scoreRules": scores_by_event[row.id],
        }
        for row in event_rows
    ]

    selected = _select_event(events, requested_year=exam_year, current_year=today.year)
    return {
        "certificate": dict(cert._mapping),
        "selectedEvent": selected,
        "events": events,
    }


def _select_event(
    events: list[dict[str, Any]],
    *,
    requested_year: int | None,
    current_year: int,
) -> dict[str, Any]:
    if requested_year is not None:
        return events[0]

    current = [event for event in events if event["examYear"] == current_year]
    if current:
        return current[0]

    future = sorted(
        (event for event in events if event["examYear"] > current_year),
        key=lambda event: event["examYear"],
    )
    if future:
        return future[0]

    return max(events, key=lambda event: event["examYear"])
