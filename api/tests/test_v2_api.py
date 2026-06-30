"""WP12 API V2 MVP contract tests."""

from __future__ import annotations

import warnings
from collections.abc import Generator
from datetime import date
from decimal import Decimal
from urllib.parse import urlparse, urlunparse

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

from api.config import settings
from api.services.knowledge_points import create_knowledge_point, map_fragment_to_knowledge_point
from api.services.v2_api import evaluate_eligibility_v2, list_certificates, search_knowledge
from db.tests.fixtures_wp02 import seed_fixtures as seed_wp02
from db.tests.fixtures_wp03 import seed_fixtures as seed_wp03
from db.tests.fixtures_wp06 import seed_eligibility_rule, seed_policy_document
from db.tests.fixtures_wp07 import seed_exam_event, seed_exam_phase, seed_subject_score_rule


@pytest.fixture(scope="module")
def engine() -> Generator[Engine, None, None]:
    parsed = urlparse(settings.database_url)
    test_db_name = "knowledge_platform_v2_test_wp12_api"
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
def _seed_v2_data(engine: Engine):
    event = seed_exam_event(engine, code="WP12_CONSTRUCTOR_2026", exam_year=2026)
    seed_exam_phase(engine, event_id=event["id"], phase_type="registration", starts_on="2026-06-01")
    seed_exam_phase(engine, event_id=event["id"], phase_type="written", starts_on="2026-09-19")
    seed_subject_score_rule(engine, event_id=event["id"], subject_code="subj_constructor_mgmt", full_mark=100, pass_mark=60)

    policy = seed_policy_document(engine, prefix="WP12_POLICY", clause_codes=("ARTICLE_09",))
    seed_eligibility_rule(
        engine,
        code="WP12_BACHELOR_LAW",
        certificate_id=policy["certificate_id"],
        knowledge_point_id=policy["knowledge_point_id"],
        clause_id=policy["clauses"]["ARTICLE_09"],
        degree_level_code="bachelor",
        major_category_code="law",
        education_type_code="full_time",
        min_total_work_months=36,
        min_relevant_work_months=36,
    )

    create_knowledge_point(engine, code="WP12_SEARCH_KP", name="WP12 Search KP", domain_code="policy")
    _seed_asset_fragment(
        engine,
        asset_code="WP12_SEARCH_INTERNAL",
        collection_code="coll_internal",
        asset_type="textbook",
        fragment_code="SEARCH_INTERNAL",
        content="work months requirement explanation for constructor eligibility",
    )
    _seed_asset_fragment(
        engine,
        asset_code="WP12_SEARCH_PUBLIC",
        collection_code="coll_public",
        asset_type="policy",
        fragment_code="SEARCH_PUBLIC",
        content="public work months policy summary",
    )
    _seed_asset_fragment(
        engine,
        asset_code="WP12_SEARCH_RESTRICTED",
        collection_code="coll_restricted",
        asset_type="private",
        confidentiality="restricted",
        fragment_code="SEARCH_RESTRICTED",
        content="restricted answer key must not leak",
    )
    for asset_code, fragment_code in (
        ("WP12_SEARCH_INTERNAL", "SEARCH_INTERNAL"),
        ("WP12_SEARCH_PUBLIC", "SEARCH_PUBLIC"),
        ("WP12_SEARCH_RESTRICTED", "SEARCH_RESTRICTED"),
    ):
        map_fragment_to_knowledge_point(
            engine,
            asset_code=asset_code,
            version_no=1,
            fragment_code=fragment_code,
            kp_code="WP12_SEARCH_KP",
            relation_role="explanation",
            confidence=Decimal("0.900"),
            review_status="approved",
            reviewed_by="reviewer_01",
        )


def _seed_asset_fragment(
    engine: Engine,
    *,
    asset_code: str,
    collection_code: str,
    asset_type: str,
    fragment_code: str,
    content: str,
    confidentiality: str = "internal",
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("""
                WITH refs AS (
                    SELECT c.id AS collection_id, o.id AS owner_org_id
                      FROM knowledge.collection c
                      JOIN iam.organization_unit o ON o.code = 'org_teaching_materials'
                     WHERE c.code = :collection_code
                ),
                asset_row AS (
                    INSERT INTO knowledge.asset (
                        code, asset_type, title, collection_id, owner_org_id,
                        confidentiality, status
                    )
                    SELECT :asset_code, :asset_type, :asset_code, collection_id, owner_org_id,
                           :confidentiality, 'published'
                      FROM refs
                    RETURNING id
                ),
                version_row AS (
                    INSERT INTO knowledge.asset_version (
                        asset_id, version_no, object_key, mime_type, extracted_text,
                        content_sha256, valid_during, review_status, reviewed_by, reviewed_at
                    )
                    SELECT id, 1, :asset_code || '/v1', 'text/plain', :content,
                           :asset_code || '_sha', daterange('2020-01-01', NULL, '[)'),
                           'approved', 'reviewer_01', now()
                      FROM asset_row
                    RETURNING id
                )
                INSERT INTO knowledge.fragment (
                    asset_version_id, fragment_code, fragment_type, heading, content, page_from, page_to
                )
                SELECT id, :fragment_code, 'section', :fragment_code, :content, 1, 1
                  FROM version_row
            """),
            {
                "asset_code": asset_code,
                "collection_code": collection_code,
                "asset_type": asset_type,
                "fragment_code": fragment_code,
                "content": content,
                "confidentiality": confidentiality,
            },
        )


def test_v2_certificate_query_returns_aliases_and_next_exam(engine: Engine):
    result = list_certificates(engine, query="一建", limit=10, as_of=date(2026, 6, 29))

    item = next(item for item in result["items"] if item["code"] == "c_constructor_1")
    assert "一建" in item["aliases"]
    assert item["nextExam"]["eventCode"] == "WP12_CONSTRUCTOR_2026"
    assert item["nextExam"]["phases"][0]["type"] == "registration"
    assert result["nextCursor"] is None


def test_v2_certificate_query_deduplicates_display_aliases(engine: Engine):
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO core.certificate_alias (certificate_id, alias, normalized_alias, alias_type)
                SELECT id, '一建', 'wp12_duplicate_display_alias', 'legacy'
                  FROM core.certificate
                 WHERE code = 'c_constructor_1'
                ON CONFLICT DO NOTHING
            """),
        )

    result = list_certificates(engine, query="一建", limit=10, as_of=date(2026, 6, 29))

    item = next(item for item in result["items"] if item["code"] == "c_constructor_1")
    assert item["aliases"].count("一建") == 1


def test_v2_eligibility_response_contains_requirements_and_citations(engine: Engine):
    result = evaluate_eligibility_v2(
        engine,
        certificate_code="c_constructor_1",
        principal_type="org",
        principal_code="org_teaching_materials",
        as_of=date(2026, 6, 29),
        qualification_level="first_exam",
        degree_level_code="bachelor",
        major_category_code="law",
        education_type_code="full_time",
        total_work_months=36,
        relevant_work_months=36,
    )

    assert result["decision"] == "eligible"
    assert result["matchedRuleCode"] == "WP12_BACHELOR_LAW"
    assert {"field": "relevantWorkMonths", "required": 36, "actual": 36, "passed": True} in result["requirements"]
    assert result["citations"][0]["section"] == "ARTICLE_09"


def test_v2_knowledge_search_filters_acl_status_and_structured_inputs(engine: Engine):
    allowed = search_knowledge(
        engine,
        principal_type="org",
        principal_code="org_teaching_materials",
        query="work months",
        collection_codes=["coll_internal"],
        knowledge_point_codes=["WP12_SEARCH_KP"],
        asset_types=["textbook"],
        top_k=5,
        as_of=date(2026, 6, 29),
    )
    public_only = search_knowledge(
        engine,
        principal_type="org",
        principal_code="org_operations",
        query="work months",
        knowledge_point_codes=["WP12_SEARCH_KP"],
        top_k=5,
        as_of=date(2026, 6, 29),
    )

    assert [item["fragmentCode"] for item in allowed["items"]] == ["SEARCH_INTERNAL"]
    assert {item["fragmentCode"] for item in public_only["items"]} == {"SEARCH_PUBLIC"}
    assert "restricted answer key" not in str(public_only)


def test_v2_routes_require_identity_return_error_model_and_prevent_leaks(
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
):
    import api.main as main

    monkeypatch.setattr(main, "sync_engine", engine)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Using `httpx` with `starlette.testclient` is deprecated")
        from fastapi.testclient import TestClient

        client = TestClient(main.app)

    anonymous = client.get("/api/v2/certificates")
    unknown = client.get(
        "/api/v2/certificates/no_such_cert",
        headers={"X-Org-Code": "org_teaching_materials", "X-Request-ID": "req_wp12_fixed"},
    )
    denied = client.post(
        "/api/v2/knowledge/search",
        json={"query": "restricted", "collectionCodes": ["coll_restricted"], "topK": 5},
        headers={"X-Org-Code": "org_operations"},
    )
    allowed = client.post(
        "/api/v2/knowledge/search",
        json={"query": "work months", "collectionCodes": ["coll_internal"], "knowledgePointCodes": ["WP12_SEARCH_KP"]},
        headers={"X-Org-Code": "org_teaching_materials"},
    )

    assert anonymous.status_code == 401
    assert anonymous.json()["error"]["code"] == "UNAUTHENTICATED"
    assert unknown.status_code == 404
    assert unknown.headers["X-Request-ID"] == "req_wp12_fixed"
    assert unknown.json()["error"]["requestId"] == "req_wp12_fixed"
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "ACCESS_DENIED"
    assert "restricted answer key" not in denied.text
    assert "coll_restricted" not in denied.text
    assert allowed.status_code == 200
    assert allowed.json()["items"][0]["fragmentCode"] == "SEARCH_INTERNAL"


def test_v2_database_failure_returns_503_error_model(engine: Engine, monkeypatch: pytest.MonkeyPatch):
    import api.main as main

    monkeypatch.setattr(main, "sync_engine", engine)

    def _raise_db_error(*args, **kwargs):
        raise OperationalError("SELECT 1", {}, Exception("db down"))

    monkeypatch.setattr(main, "list_certificates", _raise_db_error)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Using `httpx` with `starlette.testclient` is deprecated")
        from fastapi.testclient import TestClient

        client = TestClient(main.app)

    response = client.get("/api/v2/certificates", headers={"X-Org-Code": "org_teaching_materials"})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert response.json()["error"]["requestId"].startswith("req_")
