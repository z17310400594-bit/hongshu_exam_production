"""WP06 eligibility service/API tests — policy rules MVP."""

from __future__ import annotations

import warnings
from collections.abc import Generator
from datetime import date
from urllib.parse import urlparse, urlunparse

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from api.auth import AuthorizationError
from api.config import settings
from api.services.eligibility import evaluate_eligibility
from db.tests.fixtures_wp02 import seed_fixtures as seed_wp02
from db.tests.fixtures_wp03 import seed_fixtures as seed_wp03
from db.tests.fixtures_wp06 import seed_eligibility_rule, seed_policy_document


@pytest.fixture(scope="module")
def engine() -> Generator[Engine, None, None]:
    parsed = urlparse(settings.database_url)
    test_db_name = "knowledge_platform_v2_test_wp06_api"
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
def _seed_policy_rules(engine: Engine):
    normal = seed_policy_document(engine, prefix="WP06_API_NORMAL", clause_codes=("ARTICLE_09", "ARTICLE_10"))
    seed_eligibility_rule(
        engine,
        code="WP06_NORMAL_BACHELOR_LAW",
        certificate_id=normal["certificate_id"],
        knowledge_point_id=normal["knowledge_point_id"],
        clause_id=normal["clauses"]["ARTICLE_09"],
        degree_level_code="bachelor",
        major_category_code="law",
        education_type_code="full_time",
        min_relevant_work_months=36,
    )
    seed_eligibility_rule(
        engine,
        code="WP06_GRANDFATHERED",
        certificate_id=normal["certificate_id"],
        knowledge_point_id=normal["knowledge_point_id"],
        clause_id=normal["clauses"]["ARTICLE_10"],
        route_code="grandfathered",
        degree_level_code="any",
        major_category_code="any",
        education_type_code="any",
        admission_before="2018-04-28",
        evidence_role="primary",
    )

    regional = seed_policy_document(engine, prefix="WP06_API_REGION", clause_codes=("ARTICLE_BJ",))
    seed_eligibility_rule(
        engine,
        code="WP06_BJ_EXCEPTION",
        certificate_id=regional["certificate_id"],
        knowledge_point_id=regional["knowledge_point_id"],
        clause_id=regional["clauses"]["ARTICLE_BJ"],
        degree_level_code="bachelor",
        major_category_code="non_law",
        education_type_code="full_time",
        min_relevant_work_months=12,
        region_code="BJ",
    )

    superseded = seed_policy_document(
        engine,
        prefix="WP06_API_SUPERSEDED",
        certificate_code="c_fire_engineer_1",
        document_status="superseded",
        clause_codes=("ARTICLE_OLD",),
    )
    seed_eligibility_rule(
        engine,
        code="WP06_SUPERSEDED_DOC_RULE",
        certificate_id=superseded["certificate_id"],
        knowledge_point_id=superseded["knowledge_point_id"],
        clause_id=superseded["clauses"]["ARTICLE_OLD"],
        degree_level_code="bachelor",
        major_category_code="law",
        education_type_code="full_time",
        min_relevant_work_months=0,
    )

    expired = seed_policy_document(
        engine,
        prefix="WP06_API_EXPIRED",
        certificate_code="c_cost_engineer_1",
        valid_from="2020-01-01",
        valid_to="2021-01-01",
        clause_codes=("ARTICLE_EXPIRED",),
    )
    seed_eligibility_rule(
        engine,
        code="WP06_EXPIRED_RULE",
        certificate_id=expired["certificate_id"],
        knowledge_point_id=expired["knowledge_point_id"],
        clause_id=expired["clauses"]["ARTICLE_EXPIRED"],
        degree_level_code="bachelor",
        major_category_code="law",
        education_type_code="full_time",
        min_relevant_work_months=0,
        valid_from="2020-01-01",
        valid_to="2021-01-01",
    )


def test_normal_rule_matches_approved_readable_policy(engine: Engine):
    result = evaluate_eligibility(
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

    assert result["status"] == "eligible"
    assert result["matchedRules"][0]["code"] == "WP06_NORMAL_BACHELOR_LAW"
    assert result["matchedRules"][0]["minRelevantWorkMonths"] == 36
    assert result["matchedRules"][0]["primaryEvidence"][0]["clauseCode"] == "ARTICLE_09"


def test_grandfathered_rule_uses_admission_cutoff(engine: Engine):
    result = evaluate_eligibility(
        engine,
        certificate_code="c_constructor_1",
        principal_type="org",
        principal_code="org_teaching_materials",
        as_of=date(2026, 6, 29),
        qualification_level="first_exam",
        degree_level_code="associate",
        major_category_code="history",
        education_type_code="part_time",
        total_work_months=0,
        relevant_work_months=0,
        admission_date=date(2017, 9, 1),
    )

    assert result["status"] == "eligible"
    assert result["matchedRules"][0]["routeCode"] == "grandfathered"
    assert result["matchedRules"][0]["admissionBefore"] == "2018-04-28"


def test_region_exception_prefers_matching_region(engine: Engine):
    result = evaluate_eligibility(
        engine,
        certificate_code="c_constructor_1",
        principal_type="org",
        principal_code="org_teaching_materials",
        as_of=date(2026, 6, 29),
        region_code="BJ",
        qualification_level="first_exam",
        degree_level_code="bachelor",
        major_category_code="non_law",
        education_type_code="full_time",
        total_work_months=12,
        relevant_work_months=12,
    )

    assert result["status"] == "eligible"
    assert result["matchedRules"][0]["code"] == "WP06_BJ_EXCEPTION"
    assert result["matchedRules"][0]["regionCode"] == "BJ"


def test_superseded_repealed_or_expired_policy_rules_are_not_returned(engine: Engine):
    superseded = evaluate_eligibility(
        engine,
        certificate_code="c_fire_engineer_1",
        principal_type="org",
        principal_code="org_teaching_materials",
        as_of=date(2026, 6, 29),
        qualification_level="first_exam",
        degree_level_code="bachelor",
        major_category_code="law",
        education_type_code="full_time",
        total_work_months=0,
        relevant_work_months=0,
    )
    expired = evaluate_eligibility(
        engine,
        certificate_code="c_cost_engineer_1",
        principal_type="org",
        principal_code="org_teaching_materials",
        as_of=date(2026, 6, 29),
        qualification_level="first_exam",
        degree_level_code="bachelor",
        major_category_code="law",
        education_type_code="full_time",
        total_work_months=0,
        relevant_work_months=0,
    )

    assert superseded["status"] == "insufficient_data"
    assert expired["status"] == "insufficient_data"
    assert superseded["matchedRules"] == []
    assert expired["matchedRules"] == []


def test_insufficient_data_does_not_guess_when_no_rule_matches(engine: Engine):
    result = evaluate_eligibility(
        engine,
        certificate_code="c_constructor_1",
        principal_type="org",
        principal_code="org_teaching_materials",
        as_of=date(2026, 6, 29),
        qualification_level="first_exam",
        degree_level_code="high_school",
        major_category_code="unknown",
        education_type_code="full_time",
        total_work_months=0,
        relevant_work_months=0,
    )

    assert result["status"] == "insufficient_data"
    assert result["matchedRules"] == []


def test_acl_denies_hidden_policy_without_leaking_evidence(engine: Engine):
    with pytest.raises(AuthorizationError) as exc:
        evaluate_eligibility(
            engine,
            certificate_code="c_constructor_1",
            principal_type="org",
            principal_code="org_operations",
            as_of=date(2026, 6, 29),
            qualification_level="first_exam",
            degree_level_code="bachelor",
            major_category_code="law",
            education_type_code="full_time",
            total_work_months=36,
            relevant_work_months=36,
        )

    assert exc.value.status_code == 403
    assert "ARTICLE_09" not in exc.value.detail
    assert "WP06_NORMAL" not in exc.value.detail


def test_api_route_requires_identity_allows_and_denies(engine: Engine, monkeypatch: pytest.MonkeyPatch):
    import api.main as main

    monkeypatch.setattr(main, "sync_engine", engine)

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Using `httpx` with `starlette.testclient` is deprecated")
        from fastapi.testclient import TestClient

        client = TestClient(main.app)

    payload = {
        "certificate_code": "c_constructor_1",
        "as_of": "2026-06-29",
        "qualification_level": "first_exam",
        "degree_level_code": "bachelor",
        "major_category_code": "law",
        "education_type_code": "full_time",
        "total_work_months": 36,
        "relevant_work_months": 36,
    }
    anonymous = client.post("/eligibility/evaluate", json=payload)
    denied = client.post("/eligibility/evaluate", json=payload, headers={"X-Org-Code": "org_operations"})
    allowed = client.post("/eligibility/evaluate", json=payload, headers={"X-Org-Code": "org_teaching_materials"})
    unknown = client.post(
        "/eligibility/evaluate",
        json={**payload, "certificate_code": "no_such_cert"},
        headers={"X-Org-Code": "org_teaching_materials"},
    )

    assert anonymous.status_code == 401
    assert denied.status_code == 403
    assert "ARTICLE_09" not in denied.text
    assert "WP06_NORMAL" not in denied.text
    assert allowed.status_code == 200
    assert allowed.json()["status"] == "eligible"
    assert allowed.json()["matchedRules"][0]["code"] == "WP06_NORMAL_BACHELOR_LAW"
    assert unknown.status_code == 404
