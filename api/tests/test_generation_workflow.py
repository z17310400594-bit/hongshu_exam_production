"""WP14 generation workflow tests — backendized MVP generation."""

from __future__ import annotations

import warnings
from collections.abc import Generator
from decimal import Decimal
from urllib.parse import urlparse, urlunparse

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from api.config import settings
from api.services import model_gateway
from api.services.generation_workflow import create_generation, get_generation_v2
from api.services.knowledge_points import create_knowledge_point, map_fragment_to_knowledge_point
from db.tests.fixtures_wp02 import seed_fixtures as seed_wp02
from db.tests.fixtures_wp03 import seed_fixtures as seed_wp03
from db.tests.fixtures_wp10 import seed_generation_source_asset


@pytest.fixture(scope="module")
def engine() -> Generator[Engine, None, None]:
    parsed = urlparse(settings.database_url)
    test_db_name = "knowledge_platform_v2_test_wp14_api"
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
def _seed_generation_sources(engine: Engine):
    create_knowledge_point(engine, code="WP14_GEN_KP", name="WP14 Generation KP", domain_code="generation")
    internal = seed_generation_source_asset(
        engine,
        asset_code="WP14_INTERNAL_SOURCE",
        collection_code="coll_internal",
        confidentiality="internal",
    )
    map_fragment_to_knowledge_point(
        engine,
        asset_code="WP14_INTERNAL_SOURCE",
        version_no=1,
        fragment_code="GEN_REF_01",
        kp_code="WP14_GEN_KP",
        relation_role="explanation",
        confidence=Decimal("0.900"),
        review_status="approved",
        reviewed_by="reviewer_01",
    )

    restricted = seed_generation_source_asset(
        engine,
        asset_code="WP14_RESTRICTED_SOURCE",
        collection_code="coll_restricted",
        confidentiality="restricted",
    )
    map_fragment_to_knowledge_point(
        engine,
        asset_code="WP14_RESTRICTED_SOURCE",
        version_no=1,
        fragment_code="GEN_REF_01",
        kp_code="WP14_GEN_KP",
        relation_role="explanation",
        confidence=Decimal("0.800"),
        review_status="approved",
        reviewed_by="reviewer_01",
    )
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO knowledge.collection_acl (
                    collection_id, principal_type, principal_code, permission
                )
                SELECT id, 'org', 'org_teaching_materials', 'read'
                  FROM knowledge.collection
                 WHERE code = 'coll_restricted'
                ON CONFLICT DO NOTHING
            """)
        )
    return {"internal": internal, "restricted": restricted}


@pytest.fixture(autouse=True)
def _default_generation_provider(monkeypatch: pytest.MonkeyPatch):
    """Keep workflow tests deterministic even when local .env enables Dify."""
    monkeypatch.setattr(settings, "generation_provider", "local")


def test_service_creates_generation_run_citations_and_output(engine: Engine):
    result = create_generation(
        engine,
        principal_type="org",
        principal_code="org_teaching_materials",
        application_code="exam_article",
        output_type="card_set",
        certificate_code="c_constructor_1",
        collection_codes=["coll_internal"],
        knowledge_point_codes=["WP14_GEN_KP"],
        inputs={
            "examName": "一建",
            "examDate": "2026-09-19",
            "targetAudience": "零基础考生",
            "theme": "生成引用",
        },
        idempotency_key="wp14-test-key",
        card_sequence=["cover", "plan"],
    )

    assert result["status"] == "succeeded"
    assert result["outputType"] == "card_set"
    assert result["confidentiality"] == "internal"
    assert result["cards"][0]["type"] == "cover"
    assert result["citations"][0]["assetCode"] == "WP14_INTERNAL_SOURCE"

    fetched = get_generation_v2(
        engine,
        run_id=result["runId"],
        principal_type="org",
        principal_code="org_teaching_materials",
    )
    assert fetched["runId"] == result["runId"]
    assert fetched["citations"][0]["fragmentCode"] == "GEN_REF_01"
    assert fetched["cards"][0]["citations"][0]["assetCode"] == "WP14_INTERNAL_SOURCE"


def test_restricted_generation_routes_internal_and_preserves_confidentiality(engine: Engine):
    result = create_generation(
        engine,
        principal_type="org",
        principal_code="org_teaching_materials",
        application_code="exam_article",
        output_type="card_set",
        certificate_code="c_constructor_1",
        collection_codes=["coll_restricted"],
        knowledge_point_codes=["WP14_GEN_KP"],
        inputs={"examName": "一建", "theme": "生成引用"},
        card_sequence=["cover"],
    )

    assert result["confidentiality"] == "restricted"
    assert result["modelRoute"] == "internal"
    assert result["citations"][0]["confidentiality"] == "restricted"


def test_configured_model_gateway_success_persists_provider_and_citations(
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "generation_provider", "dify")
    monkeypatch.setattr(settings, "dify_api_url", "https://dify.example.test")
    monkeypatch.setattr(settings, "dify_api_key", "test-placeholder-key")

    def fake_gateway(**kwargs):
        assert kwargs["model_route"] == "approved_external"
        return model_gateway.ModelGatewayResult(
            provider="dify",
            model_name="dify-workflow",
            cards=[
                {
                    "type": "cover",
                    "title": "Dify generated card",
                    "subtitle": "",
                    "days": [],
                    "items": [{"label": "模型输出", "content": "已结合引用生成"}],
                    "qrcode_url": "",
                }
            ],
            raw_metadata={"workflowRunId": "wf-test"},
        )

    monkeypatch.setattr(model_gateway, "generate_cards", fake_gateway)

    result = create_generation(
        engine,
        principal_type="org",
        principal_code="org_teaching_materials",
        application_code="exam_article",
        output_type="card_set",
        certificate_code="c_constructor_1",
        collection_codes=["coll_internal"],
        knowledge_point_codes=["WP14_GEN_KP"],
        inputs={"examName": "一建", "theme": "模型网关"},
        card_sequence=["cover"],
    )

    assert result["status"] == "succeeded"
    assert result["modelRoute"] == "approved_external"
    assert result["cards"][0]["title"] == "Dify generated card"
    assert result["cards"][0]["citations"][0]["assetCode"] == "WP14_INTERNAL_SOURCE"

    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT r.model_provider, r.model_name, o.content
                  FROM generation.run r
                  JOIN generation.output o ON o.generation_run_id = r.id
                 WHERE r.id = :run_id
            """),
            {"run_id": result["runId"]},
        ).fetchone()

    assert row is not None
    assert row.model_provider == "dify"
    assert row.model_name == "dify-workflow"
    assert row.content["gateway"]["provider"] == "dify"
    assert row.content["gateway"]["metadata"]["workflowRunId"] == "wf-test"


def test_model_gateway_failure_is_persisted_without_output(
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "generation_provider", "dify")
    monkeypatch.setattr(settings, "dify_api_url", "https://dify.example.test")
    monkeypatch.setattr(settings, "dify_api_key", "test-placeholder-key")

    def failing_gateway(**kwargs):
        assert kwargs["model_route"] == "approved_external"
        raise model_gateway.ModelGatewayError(
            code="MODEL_GATEWAY_TIMEOUT",
            message="Model gateway request timed out",
            provider="dify",
        )

    monkeypatch.setattr(model_gateway, "generate_cards", failing_gateway)

    result = create_generation(
        engine,
        principal_type="org",
        principal_code="org_teaching_materials",
        application_code="exam_article",
        output_type="card_set",
        certificate_code="c_constructor_1",
        collection_codes=["coll_internal"],
        knowledge_point_codes=["WP14_GEN_KP"],
        inputs={"examName": "一建", "theme": "失败落库"},
        card_sequence=["cover"],
    )

    assert result["status"] == "failed"
    assert result["error"] == {
        "code": "MODEL_GATEWAY_TIMEOUT",
        "message": "Model gateway request timed out",
        "provider": "dify",
    }
    assert result["citations"][0]["assetCode"] == "WP14_INTERNAL_SOURCE"

    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT
                    r.status,
                    count(DISTINCT c.fragment_id) AS citation_count,
                    count(DISTINCT o.id) AS output_count
                  FROM generation.run r
                  LEFT JOIN generation.citation c ON c.generation_run_id = r.id
                  LEFT JOIN generation.output o ON o.generation_run_id = r.id
                 WHERE r.id = :run_id
                 GROUP BY r.id, r.status
            """),
            {"run_id": result["runId"]},
        ).fetchone()

    assert row is not None
    assert row.status == "failed"
    assert row.citation_count >= 1
    assert row.output_count == 0


def test_generation_without_readable_citations_fails_without_output(engine: Engine):
    result = create_generation(
        engine,
        principal_type="org",
        principal_code="org_teaching_materials",
        application_code="exam_article",
        output_type="card_set",
        certificate_code="c_constructor_1",
        collection_codes=["coll_internal"],
        knowledge_point_codes=["WP14_UNKNOWN_KP"],
        inputs={"examName": "一建", "theme": "无引用"},
        card_sequence=["cover"],
    )

    assert result["status"] == "failed"
    assert result["cards"] == []
    assert result["citations"] == []
    assert result["error"]["code"] == "GENERATION_REQUIRES_CITATION"

    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT r.status, count(o.id) AS output_count
                  FROM generation.run r
                  LEFT JOIN generation.output o ON o.generation_run_id = r.id
                 WHERE r.id = :run_id
                 GROUP BY r.id, r.status
            """),
            {"run_id": result["runId"]},
        ).fetchone()

    assert row is not None
    assert row.status == "failed"
    assert row.output_count == 0


def test_route_requires_identity_allows_denies_and_handles_unknown(
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
):
    import api.main as main

    monkeypatch.setattr(main, "sync_engine", engine)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Using `httpx` with `starlette.testclient` is deprecated")
        from fastapi.testclient import TestClient

        client = TestClient(main.app)

    payload = {
        "applicationCode": "exam_article",
        "outputType": "card_set",
        "certificateCode": "c_constructor_1",
        "collectionCodes": ["coll_internal"],
        "knowledgePointCodes": ["WP14_GEN_KP"],
        "cardSequence": ["cover", "plan"],
        "inputs": {
            "examName": "一建",
            "examDate": "2026-09-19",
            "targetAudience": "零基础考生",
            "theme": "生成引用",
        },
    }

    anonymous = client.post("/api/v2/generations", json=payload)
    denied = client.post("/api/v2/generations", json=payload, headers={"X-Org-Code": "org_operations"})
    allowed = client.post("/api/v2/generations", json=payload, headers={"X-Org-Code": "org_teaching_materials"})

    assert anonymous.status_code == 401
    assert denied.status_code == 403
    assert "WP14_INTERNAL_SOURCE" not in denied.text
    assert "生成引用 1 的正文内容" not in denied.text
    assert allowed.status_code == 200
    body = allowed.json()
    assert body["cards"][0]["citations"][0]["assetCode"] == "WP14_INTERNAL_SOURCE"

    fetched = client.get(f"/api/v2/generations/{body['runId']}", headers={"X-Org-Code": "org_teaching_materials"})
    unknown = client.get("/api/v2/generations/999999", headers={"X-Org-Code": "org_teaching_materials"})

    assert fetched.status_code == 200
    assert fetched.json()["runId"] == body["runId"]
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "NOT_FOUND"
