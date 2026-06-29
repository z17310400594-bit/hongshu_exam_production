"""WP07 database constraint tests — exam events, phases, and score rules."""

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from db.tests.fixtures_wp02 import seed_fixtures as seed_wp02
from db.tests.fixtures_wp03 import seed_fixtures as seed_wp03
from db.tests.fixtures_wp07 import seed_exam_event, seed_exam_phase, seed_subject_score_rule


@pytest.fixture(scope="module", autouse=True)
def _migrate_module(alembic_cfg: AlembicConfig, engine: Engine):
    command.upgrade(alembic_cfg, "head")
    seed_wp02(engine)
    seed_wp03(engine)


def test_exam_event_unique_year_region_and_status_constraints(engine: Engine):
    event = seed_exam_event(engine, code="WP07_CONSTRUCTOR_2026", exam_year=2026)
    assert event["status"] == "scheduled"

    seed_exam_event(
        engine,
        code="WP07_PHARMACIST_DUP_NEEDS_REVIEW",
        certificate_code="c_pharmacist_licensed",
        exam_year=2026,
        status="needs_review",
    )

    bad_select_rows = [
        {"code": "WP07_DUP_YEAR_REGION", "cert": "c_constructor_1", "year": 2026, "region": "CN", "status": "scheduled"},
        {"code": "WP07_BAD_YEAR_LOW", "cert": "c_constructor_1", "year": 1999, "region": "CN", "status": "scheduled"},
        {"code": "WP07_BAD_YEAR_HIGH", "cert": "c_constructor_1", "year": 2101, "region": "CN", "status": "scheduled"},
        {"code": "WP07_BAD_STATUS", "cert": "c_constructor_1", "year": 2027, "region": "CN", "status": "draft"},
    ]
    for row in bad_select_rows:
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO assessment.exam_event (
                        code, certificate_id, exam_year, region_code, status
                    )
                    SELECT :code, id, :year, :region, :status
                      FROM core.certificate
                     WHERE code = :cert
                """),
                row,
            )

    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO assessment.exam_event (
                    code, certificate_id, exam_year, region_code, status
                )
                VALUES ('WP07_BAD_CERT', 999999, 2028, 'CN', 'scheduled')
            """)
        )


def test_exam_phase_type_date_order_duplicate_and_fk_constraints(engine: Engine):
    event = seed_exam_event(engine, code="WP07_PHASE_EVENT", exam_year=2027)
    seed_exam_phase(
        engine,
        event_id=event["id"],
        phase_type="registration",
        starts_on="2027-06-01",
        ends_on="2027-06-15",
    )

    bad_rows = [
        {"event_id": event["id"], "phase": "registration", "start": "2027-06-01", "end": "2027-06-15"},
        {"event_id": event["id"], "phase": "oral", "start": "2027-06-16", "end": "2027-06-16"},
        {"event_id": event["id"], "phase": "written", "start": "2027-09-20", "end": "2027-09-19"},
        {"event_id": 999999, "phase": "written", "start": "2027-09-20", "end": "2027-09-21"},
    ]
    for row in bad_rows:
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO assessment.exam_phase (
                        exam_event_id, phase_type, starts_on, ends_on
                    )
                    VALUES (:event_id, :phase, :start, :end)
                """),
                row,
            )


def test_score_rule_constraints_and_unique_subject_per_event(engine: Engine):
    event = seed_exam_event(engine, code="WP07_SCORE_EVENT", exam_year=2028)
    seed_subject_score_rule(engine, event_id=event["id"], subject_code="subj_constructor_mgmt", full_mark=130, pass_mark=78)

    bad_select_rows = [
        {"event_id": event["id"], "subject": "subj_constructor_mgmt", "full": 130, "pass": 78},
        {"event_id": event["id"], "subject": "subj_constructor_econ", "full": 0, "pass": 0},
        {"event_id": event["id"], "subject": "subj_constructor_econ", "full": 100, "pass": 101},
        {"event_id": event["id"], "subject": "subj_constructor_econ", "full": 100, "pass": -1},
        {"event_id": 999999, "subject": "subj_constructor_econ", "full": 100, "pass": 60},
    ]
    for row in bad_select_rows:
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO assessment.subject_score_rule (
                        exam_event_id, subject_id, full_mark, pass_mark
                    )
                    SELECT :event_id, id, :full, :pass
                      FROM core.exam_subject
                     WHERE code = :subject
                """),
                row,
            )

    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO assessment.subject_score_rule (
                    exam_event_id, subject_id, full_mark, pass_mark
                )
                VALUES (:event_id, 999999, 100, 60)
            """),
            {"event_id": event["id"]},
        )
