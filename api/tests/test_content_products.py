"""WP08 content product service/API tests — chapter MVP."""

from __future__ import annotations

from collections.abc import Generator
from urllib.parse import urlparse, urlunparse

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from api.config import settings
from api.services.content_products import get_content_product_chapters
from db.tests.fixtures_wp02 import seed_fixtures as seed_wp02
from db.tests.fixtures_wp03 import seed_fixtures as seed_wp03
from db.tests.fixtures_wp08 import (
    seed_chapter,
    seed_chapter_knowledge_point,
    seed_content_product,
    seed_knowledge_point,
    seed_product_version,
    seed_source_asset,
)


@pytest.fixture(scope="module")
def engine() -> Generator[Engine, None, None]:
    test_db_name = "knowledge_platform_v2_test_wp08_api"
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
def _seed_content_data(engine: Engine):
    source = seed_source_asset(
        engine,
        asset_code="WP08_API_TEXTBOOK_ASSET",
        title="WP08 API 一建教材源文件",
        collection_code="coll_internal",
        confidentiality="internal",
        fragments=[
            ("CH01", "chapter", "第一章 工程基础", 1),
            ("CH01_SEC01", "section", "第一节 报考条件", 2),
        ],
    )
    product = seed_content_product(engine, code="WP08_API_TEXTBOOK", title="WP08 API 一建教材")
    version = seed_product_version(
        engine,
        product_code=product["code"],
        asset_code=source["asset_code"],
        title="WP08 API 一建教材 2026 版",
        summary="用于 API smoke 的教材版本",
    )
    root = seed_chapter(
        engine,
        product_version_id=version["id"],
        source_fragment_id=source["fragment_ids"]["CH01"],
        chapter_code="CH01",
        title="第一章 工程基础",
        body="工程基础正文",
        sequence_no=1,
    )
    child = seed_chapter(
        engine,
        product_version_id=version["id"],
        parent_id=root["id"],
        source_fragment_id=source["fragment_ids"]["CH01_SEC01"],
        chapter_code="CH01_SEC01",
        title="第一节 报考条件",
        body="报考条件正文",
        sequence_no=2,
    )
    kp = seed_knowledge_point(engine, code="WP08_API_KP_ELIGIBILITY", name="一建报考条件")
    seed_chapter_knowledge_point(engine, chapter_id=root["id"], kp_code=kp["code"], teaching_role="core")
    seed_chapter_knowledge_point(engine, chapter_id=child["id"], kp_code=kp["code"], teaching_role="example")

    with engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE content.product_version
                   SET status = 'published', review_status = 'approved', reviewed_by = 'wp08_reviewer'
                 WHERE id = :version_id
            """),
            {"version_id": version["id"]},
        )


def test_service_returns_chapter_tree_source_asset_and_kps(engine: Engine):
    result = get_content_product_chapters(
        engine,
        product_code="WP08_API_TEXTBOOK",
        principal_type="org",
        principal_code="org_teaching_materials",
    )

    assert result["product"]["code"] == "WP08_API_TEXTBOOK"
    assert result["selectedVersion"]["status"] == "published"
    assert result["selectedVersion"]["sourceAsset"]["code"] == "WP08_API_TEXTBOOK_ASSET"
    assert [chapter["code"] for chapter in result["chapters"]] == ["CH01", "CH01_SEC01"]
    assert result["chapterTree"][0]["code"] == "CH01"
    assert result["chapterTree"][0]["children"][0]["code"] == "CH01_SEC01"
    assert result["chapters"][0]["knowledgePoints"][0]["code"] == "WP08_API_KP_ELIGIBILITY"
    assert result["chapters"][1]["knowledgePoints"][0]["teachingRole"] == "example"


def test_service_rejects_unreadable_collection_without_leaking_content(engine: Engine):
    from api.auth import AuthorizationError

    with pytest.raises(AuthorizationError) as exc_info:
        get_content_product_chapters(
            engine,
            product_code="WP08_API_TEXTBOOK",
            principal_type="org",
            principal_code="org_operations",
        )
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Access denied"


def test_service_unknown_product_is_not_found(engine: Engine):
    with pytest.raises(ValueError):
        get_content_product_chapters(
            engine,
            product_code="NO_SUCH_PRODUCT",
            principal_type="org",
            principal_code="org_teaching_materials",
        )


def test_api_route_requires_identity_allows_denies_and_handles_unknown(engine: Engine, monkeypatch: pytest.MonkeyPatch):
    import api.main as main

    monkeypatch.setattr(main, "sync_engine", engine)

    from fastapi.testclient import TestClient

    client = TestClient(main.app)

    anonymous = client.get("/content-products/WP08_API_TEXTBOOK/chapters")
    allowed = client.get("/content-products/WP08_API_TEXTBOOK/chapters", headers={"X-Org-Code": "org_teaching_materials"})
    denied = client.get("/content-products/WP08_API_TEXTBOOK/chapters", headers={"X-Org-Code": "org_operations"})
    unknown = client.get("/content-products/NO_SUCH_PRODUCT/chapters", headers={"X-Org-Code": "org_teaching_materials"})

    assert anonymous.status_code == 401
    assert allowed.status_code == 200
    assert allowed.json()["chapterTree"][0]["code"] == "CH01"
    assert denied.status_code == 403
    assert denied.json() == {"detail": "Access denied"}
    assert "WP08_API_TEXTBOOK" not in denied.text
    assert unknown.status_code == 404
