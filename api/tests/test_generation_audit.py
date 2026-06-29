"""WP10 generation audit service/API tests — citation MVP."""

from __future__ import annotations

from collections.abc import Generator
from urllib.parse import urlparse, urlunparse

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from api.config import settings
from api.services.generation_audit import get_generation_run_audit
from db.tests.fixtures_wp02 import seed_fixtures as seed_wp02
from db.tests.fixtures_wp03 import seed_fixtures as seed_wp03
from db.tests.fixtures_wp10 import (
    seed_generation_citation,
    seed_generation_output,
    seed_generation_run,
    seed_generation_source_asset,
)


@pytest.fixture(scope="module")
def engine() -> Generator[Engine, None, None]:
    test_db_name = "knowledge_platform_v2_test_wp10_api"
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


@pytest.fixture(scope="module")
def seeded_run(engine: Engine) -> dict:
    source = seed_generation_source_asset(
        engine,
        asset_code="WP10_API_SOURCE_ASSET",
        collection_code="coll_internal",
        confidentiality="internal",
    )
    run = seed_generation_run(
        engine,
        application_code="xiaohongshu_writer",
        user_code="operator_01",
        model_provider="deepseek",
        model_name="deepseek-chat",
        model_route="approved_external",
        prompt_version="soft_article_v1",
        confidentiality="internal",
        status="succeeded",
    )
    seed_generation_citation(engine, run_id=run["id"], fragment_id=source["fragment_ids"]["GEN_REF_01"])
    output = seed_generation_output(
        engine,
        run_id=run["id"],
        output_type="policy_article",
        content={"title": "一建报考条件怎么判断", "body": "正文"},
        confidentiality="internal",
        status="reviewed",
    )
    return {"run": run, "output": output}


def test_service_returns_run_citations_and_outputs(engine: Engine, seeded_run: dict):
    result = get_generation_run_audit(
        engine,
        run_id=seeded_run["run"]["id"],
        principal_type="org",
        principal_code="org_teaching_materials",
    )

    assert result["run"]["applicationCode"] == "xiaohongshu_writer"
    assert result["run"]["modelRoute"] == "approved_external"
    assert result["citations"][0]["fragment"]["code"] == "GEN_REF_01"
    assert result["citations"][0]["asset"]["code"] == "WP10_API_SOURCE_ASSET"
    assert result["outputs"][0]["outputType"] == "policy_article"
    assert result["outputs"][0]["content"]["title"] == "一建报考条件怎么判断"


def test_service_rejects_unreadable_citations_without_leaking_content(engine: Engine, seeded_run: dict):
    from api.auth import AuthorizationError

    with pytest.raises(AuthorizationError) as exc_info:
        get_generation_run_audit(
            engine,
            run_id=seeded_run["run"]["id"],
            principal_type="org",
            principal_code="org_operations",
        )
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Access denied"


def test_service_unknown_run_is_not_found(engine: Engine):
    with pytest.raises(ValueError):
        get_generation_run_audit(
            engine,
            run_id=999999,
            principal_type="org",
            principal_code="org_teaching_materials",
        )


def test_api_route_requires_identity_allows_denies_and_handles_unknown(
    engine: Engine,
    seeded_run: dict,
    monkeypatch: pytest.MonkeyPatch,
):
    import api.main as main

    monkeypatch.setattr(main, "sync_engine", engine)

    from fastapi.testclient import TestClient

    client = TestClient(main.app)
    run_id = seeded_run["run"]["id"]

    anonymous = client.get(f"/generation-runs/{run_id}")
    allowed = client.get(f"/generation-runs/{run_id}", headers={"X-Org-Code": "org_teaching_materials"})
    denied = client.get(f"/generation-runs/{run_id}", headers={"X-Org-Code": "org_operations"})
    unknown = client.get("/generation-runs/999999", headers={"X-Org-Code": "org_teaching_materials"})

    assert anonymous.status_code == 401
    assert allowed.status_code == 200
    assert allowed.json()["citations"][0]["fragment"]["code"] == "GEN_REF_01"
    assert denied.status_code == 403
    assert denied.json() == {"detail": "Access denied"}
    assert "WP10_API_SOURCE_ASSET" not in denied.text
    assert unknown.status_code == 404
