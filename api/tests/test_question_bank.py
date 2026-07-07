"""WP09 question bank service/API tests — paper question MVP."""

from __future__ import annotations

from collections.abc import Generator
from urllib.parse import urlparse, urlunparse

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from api.config import settings
from api.services.question_bank import get_paper_questions
from db.tests.fixtures_wp02 import seed_fixtures as seed_wp02
from db.tests.fixtures_wp03 import seed_fixtures as seed_wp03
from db.tests.fixtures_wp09 import (
    seed_knowledge_point,
    seed_paper,
    seed_paper_source_asset,
    seed_question,
    seed_question_knowledge_point,
)


@pytest.fixture(scope="module")
def engine() -> Generator[Engine, None, None]:
    test_db_name = "knowledge_platform_v2_test_wp09_api"
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
def _seed_question_bank_data(engine: Engine):
    source = seed_paper_source_asset(engine, asset_code="WP09_API_PAPER_ASSET")
    paper = seed_paper(
        engine,
        code="WP09_API_MOCK_2026",
        source_asset_code=source["asset_code"],
        title="WP09 API 一建模拟卷",
        paper_type="mock",
    )
    kp_eligibility = seed_knowledge_point(engine, code="WP09_API_KP_ELIGIBILITY", name="一建报考条件")
    kp_case = seed_knowledge_point(engine, code="WP09_API_KP_CASE", name="案例分析")

    q1 = seed_question(
        engine,
        paper_id=paper["id"],
        source_fragment_id=source["fragment_ids"]["Q001"],
        question_no="1",
        question_type="single",
        content="下列人员符合报考条件的是？",
        options={"A": "满足工作年限", "B": "不满足学历"},
        answer="A",
        analysis="依据报考规则选择 A。",
        difficulty=2,
    )
    q2 = seed_question(
        engine,
        paper_id=paper["id"],
        source_fragment_id=source["fragment_ids"]["Q002"],
        question_no="2",
        question_type="multiple",
        content="以下属于审核材料的是？",
        options={"A": "学历证明", "B": "工作证明", "C": "无关材料"},
        answer=["A", "B"],
        difficulty=3,
    )
    q3 = seed_question(
        engine,
        paper_id=paper["id"],
        question_no="3",
        question_type="true_false",
        content="报考条件无需审核工作年限。",
        answer=False,
        difficulty=1,
    )
    q4 = seed_question(
        engine,
        paper_id=paper["id"],
        source_fragment_id=source["fragment_ids"]["CASE01"],
        question_no="4",
        question_type="case",
        content="根据案例判断是否满足报考要求。",
        answer={"points": ["学历", "工作年限"]},
        difficulty=5,
    )
    seed_question_knowledge_point(engine, question_id=q1["id"], kp_code=kp_eligibility["code"], role="primary", score_weight=1)
    seed_question_knowledge_point(engine, question_id=q2["id"], kp_code=kp_eligibility["code"], role="secondary", score_weight="0.5")
    seed_question_knowledge_point(engine, question_id=q3["id"], kp_code=kp_eligibility["code"], role="primary", score_weight=1)
    seed_question_knowledge_point(engine, question_id=q4["id"], kp_code=kp_case["code"], role="primary", score_weight=1)

    with engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE assessment.paper
                   SET status = 'published', review_status = 'approved', reviewed_by = 'wp09_reviewer'
                 WHERE id = :paper_id
            """),
            {"paper_id": paper["id"]},
        )

    draft_source = seed_paper_source_asset(engine, asset_code="WP09_API_DRAFT_ASSET")
    seed_paper(
        engine,
        code="WP09_API_DRAFT",
        source_asset_code=draft_source["asset_code"],
        title="WP09 API 草稿卷",
        status="draft",
        review_status="pending",
        reviewed_by=None,
    )


def test_service_returns_questions_coverage_and_difficulty_distribution(engine: Engine):
    result = get_paper_questions(
        engine,
        paper_code="WP09_API_MOCK_2026",
        principal_type="org",
        principal_code="org_teaching_materials",
    )

    assert result["paper"]["code"] == "WP09_API_MOCK_2026"
    assert result["paper"]["sourceAsset"]["code"] == "WP09_API_PAPER_ASSET"
    assert [question["questionType"] for question in result["questions"]] == ["single", "multiple", "true_false", "case"]
    assert result["questions"][0]["answer"] == "A"
    assert result["questions"][1]["answer"] == ["A", "B"]
    assert result["questions"][2]["answer"] is False
    assert result["stats"]["questionCount"] == 4
    assert result["stats"]["knowledgePointCount"] == 2
    assert result["stats"]["difficultyDistribution"] == {"1": 1, "2": 1, "3": 1, "4": 0, "5": 1}
    coverage = {item["code"]: item for item in result["stats"]["knowledgePointCoverage"]}
    assert coverage["WP09_API_KP_ELIGIBILITY"]["questionCount"] == 3
    assert coverage["WP09_API_KP_ELIGIBILITY"]["primaryCount"] == 2


def test_service_rejects_unreadable_paper_without_leaking_content(engine: Engine):
    from api.auth import AuthorizationError

    with pytest.raises(AuthorizationError) as exc_info:
        get_paper_questions(
            engine,
            paper_code="WP09_API_MOCK_2026",
            principal_type="org",
            principal_code="org_operations",
        )
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Access denied"


def test_service_hides_draft_or_unknown_paper(engine: Engine):
    for code in ["WP09_API_DRAFT", "NO_SUCH_PAPER"]:
        with pytest.raises(ValueError):
            get_paper_questions(
                engine,
                paper_code=code,
                principal_type="org",
                principal_code="org_teaching_materials",
            )


def test_api_route_requires_identity_allows_denies_and_handles_unknown(engine: Engine, monkeypatch: pytest.MonkeyPatch):
    import api.main as main

    monkeypatch.setattr(main, "sync_engine", engine)

    from fastapi.testclient import TestClient

    client = TestClient(main.app)

    anonymous = client.get("/papers/WP09_API_MOCK_2026/questions")
    allowed = client.get("/papers/WP09_API_MOCK_2026/questions", headers={"X-Org-Code": "org_teaching_materials"})
    denied = client.get("/papers/WP09_API_MOCK_2026/questions", headers={"X-Org-Code": "org_operations"})
    unknown = client.get("/papers/NO_SUCH_PAPER/questions", headers={"X-Org-Code": "org_teaching_materials"})

    assert anonymous.status_code == 401
    assert allowed.status_code == 200
    assert allowed.json()["stats"]["questionCount"] == 4
    assert denied.status_code == 403
    assert denied.json() == {"detail": "Access denied"}
    assert "WP09_API_MOCK_2026" not in denied.text
    assert unknown.status_code == 404
