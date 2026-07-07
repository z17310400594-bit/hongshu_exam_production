"""WP07 exam event service/API tests — schedule and score MVP."""

from __future__ import annotations

from collections.abc import Generator
from datetime import date
from urllib.parse import urlparse, urlunparse

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from api.config import settings
from api.services.exam_events import get_exam_events
from db.tests.fixtures_wp02 import seed_fixtures as seed_wp02
from db.tests.fixtures_wp03 import seed_fixtures as seed_wp03
from db.tests.fixtures_wp07 import seed_exam_event, seed_exam_phase, seed_subject_score_rule


@pytest.fixture(scope="module")
def engine() -> Generator[Engine, None, None]:
    test_db_name = "knowledge_platform_v2_test_wp07_api"
    parsed = urlparse(settings.database_url)
    parsed = parsed._replace(path=test_db_name)
    test_url = urlunparse(parsed)

    admin_url = settings.database_url.replace(f"/{settings.db_name}", "/postgres")
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {test_db_name}"))
        conn.execute(text(f"CREATE DATABASE {test_db_name} OWNER {settings.db_user}"))
    admin_engine.dispose()

    eng = create_engine(test_url, pool_size=1)
    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", test_url)
    command.upgrade(cfg, "head")
    seed_wp02(eng)
    seed_wp03(eng)

    yield eng
    eng.dispose()

    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {test_db_name}"))
    admin_engine.dispose()


@pytest.fixture(scope="module", autouse=True)
def _seed_exam_data(engine: Engine):
    event_2025 = seed_exam_event(engine, code="WP07_CONSTRUCTOR_2025_CN", exam_year=2025, status="completed")
    event_2026 = seed_exam_event(engine, code="WP07_CONSTRUCTOR_2026_CN", exam_year=2026, status="published")
    event_2027 = seed_exam_event(engine, code="WP07_CONSTRUCTOR_2027_CN", exam_year=2027, status="scheduled")

    seed_exam_phase(
        engine,
        event_id=event_2026["id"],
        phase_type="registration",
        starts_on="2026-06-16",
        ends_on="2026-06-30",
        note="网上报名",
    )
    seed_exam_phase(
        engine,
        event_id=event_2026["id"],
        phase_type="practical",
        starts_on="2026-08-20",
        ends_on="2026-08-20",
        note="实务考核",
    )
    seed_exam_phase(engine, event_id=event_2026["id"], phase_type="written", starts_on="2026-09-19", ends_on="2026-09-20", note="笔试")
    seed_exam_phase(engine, event_id=event_2026["id"], phase_type="result", starts_on="2026-11-20", ends_on="2026-11-20", note="查分")

    seed_subject_score_rule(engine, event_id=event_2026["id"], subject_code="subj_constructor_econ", full_mark=100, pass_mark=60)
    seed_subject_score_rule(engine, event_id=event_2026["id"], subject_code="subj_constructor_mgmt", full_mark=130, pass_mark=78)
    seed_subject_score_rule(engine, event_id=event_2026["id"], subject_code="subj_constructor_practice", full_mark=160, pass_mark=96)

    seed_exam_phase(engine, event_id=event_2025["id"], phase_type="written", starts_on="2025-09-20", ends_on="2025-09-21")
    seed_exam_phase(engine, event_id=event_2027["id"], phase_type="written", starts_on="2027-09-18", ends_on="2027-09-19")


def test_service_returns_multi_phase_event_and_score_rules(engine: Engine):
    result = get_exam_events(
        engine,
        certificate_code="c_constructor_1",
        region_code="CN",
        exam_year=2026,
        as_of=date(2026, 6, 29),
    )

    selected = result["selectedEvent"]
    assert selected["code"] == "WP07_CONSTRUCTOR_2026_CN"
    assert [phase["phaseType"] for phase in selected["phases"]] == ["registration", "practical", "written", "result"]
    assert {score["subjectCode"] for score in selected["scoreRules"]} == {
        "subj_constructor_econ",
        "subj_constructor_mgmt",
        "subj_constructor_practice",
    }
    assert next(score for score in selected["scoreRules"] if score["subjectCode"] == "subj_constructor_mgmt")["passMark"] == 78.0


def test_service_keeps_history_and_selects_current_year_deterministically(engine: Engine):
    result = get_exam_events(
        engine,
        certificate_code="c_constructor_1",
        region_code="CN",
        as_of=date(2026, 1, 1),
    )

    years = [event["examYear"] for event in result["events"]]
    assert years == [2027, 2026, 2025]
    assert result["selectedEvent"]["examYear"] == 2026


def test_service_selects_nearest_future_then_latest_history(engine: Engine):
    future = get_exam_events(
        engine,
        certificate_code="c_constructor_1",
        region_code="CN",
        as_of=date(2024, 1, 1),
    )
    history = get_exam_events(
        engine,
        certificate_code="c_constructor_1",
        region_code="CN",
        as_of=date(2028, 1, 1),
    )

    assert future["selectedEvent"]["examYear"] == 2025
    assert history["selectedEvent"]["examYear"] == 2027


def test_service_returns_empty_events_for_known_certificate_without_schedule(engine: Engine):
    result = get_exam_events(
        engine,
        certificate_code="c_pharmacist_licensed",
        region_code="CN",
        as_of=date(2026, 1, 1),
    )

    assert result["certificate"]["code"] == "c_pharmacist_licensed"
    assert result["selectedEvent"] is None
    assert result["events"] == []


def test_api_route_requires_identity_allows_and_handles_unknown(engine: Engine, monkeypatch: pytest.MonkeyPatch):
    import api.main as main

    monkeypatch.setattr(main, "sync_engine", engine)

    from fastapi.testclient import TestClient

    client = TestClient(main.app)

    anonymous = client.get("/exam-events/c_constructor_1?exam_year=2026")
    allowed = client.get("/exam-events/c_constructor_1?exam_year=2026", headers={"X-Org-Code": "org_teaching_materials"})
    unknown = client.get("/exam-events/no_such_cert", headers={"X-Org-Code": "org_teaching_materials"})

    assert anonymous.status_code == 401
    assert allowed.status_code == 200
    assert allowed.json()["selectedEvent"]["examYear"] == 2026
    assert allowed.json()["selectedEvent"]["phases"][0]["phaseType"] == "registration"
    assert unknown.status_code == 404
