"""WP05 knowledge point service/API tests — MVP approved fragment lookup."""

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
from api.services.knowledge_points import (
    add_knowledge_point_scope,
    create_knowledge_point,
    create_knowledge_point_relation,
    list_approved_fragments_for_knowledge_point,
    map_fragment_to_knowledge_point,
)
from db.tests.fixtures_wp02 import seed_fixtures as seed_wp02
from db.tests.fixtures_wp03 import seed_fixtures as seed_wp03


@pytest.fixture(scope="module")
def engine() -> Generator[Engine, None, None]:
    parsed = urlparse(settings.database_url)
    parsed = parsed._replace(path="knowledge_platform_v2_test")
    test_url = urlunparse(parsed)

    admin_url = settings.database_url.replace(f"/{settings.db_name}", "/postgres")
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS knowledge_platform_v2_test"))
        conn.execute(text(f"CREATE DATABASE knowledge_platform_v2_test OWNER {settings.db_user}"))
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
        conn.execute(text("DROP DATABASE IF EXISTS knowledge_platform_v2_test"))
    admin_engine.dispose()


def _seed_asset_fragment(
    engine: Engine,
    *,
    asset_code: str,
    asset_type: str = "textbook",
    collection_code: str,
    confidentiality: str = "internal",
    fragment_code: str,
    content: str,
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
                        code, asset_type, title, collection_id, owner_org_id, confidentiality
                    )
                    SELECT :asset_code, :asset_type, :asset_code, collection_id, owner_org_id, :confidentiality
                      FROM refs
                    ON CONFLICT (code) DO UPDATE SET title = EXCLUDED.title
                    RETURNING id
                ),
                version_row AS (
                    INSERT INTO knowledge.asset_version (
                        asset_id, version_no, object_key, mime_type, extracted_text, content_sha256
                    )
                    SELECT id, 1, :asset_code || '/v1', 'text/plain', :content, :asset_code || '_sha'
                      FROM asset_row
                    ON CONFLICT (content_sha256) DO UPDATE SET extracted_text = EXCLUDED.extracted_text
                    RETURNING id
                )
                INSERT INTO knowledge.fragment (
                    asset_version_id, fragment_code, fragment_type, heading, content, page_from, page_to
                )
                SELECT id, :fragment_code, 'section', :fragment_code, :content, 3, 4
                  FROM version_row
                ON CONFLICT (asset_version_id, fragment_code) DO UPDATE SET content = EXCLUDED.content
            """),
            {
                "asset_code": asset_code,
                "asset_type": asset_type,
                "collection_code": collection_code,
                "confidentiality": confidentiality,
                "fragment_code": fragment_code,
                "content": content,
            },
        )


def test_service_creates_reusable_tree_relation_scope_and_mapping(engine: Engine):
    parent = create_knowledge_point(
        engine,
        code="WP05_LAW",
        name="Law Qualification",
        domain_code="law",
        cognitive_level="understand",
    )
    child = create_knowledge_point(
        engine,
        code="WP05_LAW_ELIGIBILITY",
        name="Law Eligibility",
        parent_code="WP05_LAW",
        domain_code="law",
        cognitive_level="apply",
    )
    relation = create_knowledge_point_relation(
        engine,
        from_code="WP05_LAW",
        to_code="WP05_LAW_ELIGIBILITY",
        relation_type="contains",
    )
    certificate_scope = add_knowledge_point_scope(
        engine,
        kp_code="WP05_LAW_ELIGIBILITY",
        scope_type="certificate",
        scope_code="c_constructor_1",
    )
    subject_scope = add_knowledge_point_scope(
        engine,
        kp_code="WP05_LAW_ELIGIBILITY",
        scope_type="exam_subject",
        scope_code="subj_constructor_mgmt",
    )
    asset_type_scope = add_knowledge_point_scope(
        engine,
        kp_code="WP05_LAW_ELIGIBILITY",
        scope_type="asset_type",
        scope_code="textbook",
    )

    _seed_asset_fragment(
        engine,
        asset_code="WP05_APPROVED_ASSET",
        asset_type="policy",
        collection_code="coll_internal",
        fragment_code="ARTICLE_09",
        content="approved law eligibility evidence",
    )
    _seed_asset_fragment(
        engine,
        asset_code="WP05_TEXTBOOK_ASSET",
        asset_type="textbook",
        collection_code="coll_internal",
        fragment_code="CH03_SEC02",
        content="approved textbook explanation",
    )
    _seed_asset_fragment(
        engine,
        asset_code="WP05_PRIVATE_ASSET",
        asset_type="private",
        collection_code="coll_restricted",
        confidentiality="restricted",
        fragment_code="PRIVATE_NOTE",
        content="approved private note",
    )
    pending = map_fragment_to_knowledge_point(
        engine,
        asset_code="WP05_APPROVED_ASSET",
        version_no=1,
        fragment_code="ARTICLE_09",
        kp_code="WP05_LAW_ELIGIBILITY",
        relation_role="evidence",
        confidence=Decimal("0.950"),
    )

    assert parent["code"] == "WP05_LAW"
    assert child["parent_id"] == parent["id"]
    assert relation["relation_type"] == "contains"
    assert certificate_scope["scope_code"] == "c_constructor_1"
    assert subject_scope["scope_code"] == "subj_constructor_mgmt"
    assert asset_type_scope["scope_code"] == "textbook"
    assert pending["review_status"] == "pending"

    result = list_approved_fragments_for_knowledge_point(
        engine,
        kp_code="WP05_LAW_ELIGIBILITY",
        principal_type="org",
        principal_code="org_teaching_materials",
    )
    assert result["fragments"] == []

    with engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE knowledge.fragment_knowledge_point
                   SET review_status = 'approved', reviewed_by = 'reviewer_01'
                 WHERE kp_id = :kp_id
            """),
            {"kp_id": child["id"]},
        )
    map_fragment_to_knowledge_point(
        engine,
        asset_code="WP05_TEXTBOOK_ASSET",
        version_no=1,
        fragment_code="CH03_SEC02",
        kp_code="WP05_LAW_ELIGIBILITY",
        relation_role="explanation",
        review_status="approved",
        reviewed_by="editor_01",
    )
    map_fragment_to_knowledge_point(
        engine,
        asset_code="WP05_PRIVATE_ASSET",
        version_no=1,
        fragment_code="PRIVATE_NOTE",
        kp_code="WP05_LAW_ELIGIBILITY",
        relation_role="example",
        review_status="approved",
        reviewed_by="reviewer_02",
    )

    approved = list_approved_fragments_for_knowledge_point(
        engine,
        kp_code="WP05_LAW_ELIGIBILITY",
        principal_type="org",
        principal_code="org_teaching_materials",
    )
    assert approved["knowledgePoint"]["code"] == "WP05_LAW_ELIGIBILITY"
    visible_codes = {item["fragment_code"] for item in approved["fragments"]}
    assert {"ARTICLE_09", "CH03_SEC02"}.issubset(visible_codes)
    assert "PRIVATE_NOTE" not in visible_codes

    with engine.connect() as conn:
        mapped_asset_types = set(
            conn.execute(
                text("""
                    SELECT a.asset_type
                      FROM knowledge.fragment_knowledge_point fkp
                      JOIN knowledge.fragment f ON f.id = fkp.fragment_id
                      JOIN knowledge.asset_version av ON av.id = f.asset_version_id
                      JOIN knowledge.asset a ON a.id = av.asset_id
                     WHERE fkp.kp_id = :kp_id
                """),
                {"kp_id": child["id"]},
            ).scalars()
        )
    assert {"policy", "textbook", "private"}.issubset(mapped_asset_types)


def test_service_filters_by_acl_without_leaking_private_fragment(engine: Engine):
    create_knowledge_point(
        engine,
        code="WP05_ACL_KP",
        name="ACL KP",
        domain_code="law",
    )
    _seed_asset_fragment(
        engine,
        asset_code="WP05_INTERNAL_ONLY",
        collection_code="coll_internal",
        fragment_code="PRIVATE_SEC",
        content="internal-only fragment body",
    )
    map_fragment_to_knowledge_point(
        engine,
        asset_code="WP05_INTERNAL_ONLY",
        version_no=1,
        fragment_code="PRIVATE_SEC",
        kp_code="WP05_ACL_KP",
        relation_role="explanation",
        confidence=Decimal("1.000"),
        review_status="approved",
        reviewed_by="reviewer_01",
    )

    denied = list_approved_fragments_for_knowledge_point(
        engine,
        kp_code="WP05_ACL_KP",
        principal_type="org",
        principal_code="org_operations",
    )
    allowed = list_approved_fragments_for_knowledge_point(
        engine,
        kp_code="WP05_ACL_KP",
        principal_type="org",
        principal_code="org_teaching_materials",
    )

    assert denied["fragments"] == []
    assert allowed["fragments"][0]["content"] == "internal-only fragment body"


def test_route_requires_identity_and_returns_only_acl_readable_approved_fragments(engine: Engine, monkeypatch: pytest.MonkeyPatch):
    import api.main as main

    create_knowledge_point(
        engine,
        code="WP05_ROUTE_KP",
        name="Route KP",
        domain_code="law",
    )
    _seed_asset_fragment(
        engine,
        asset_code="WP05_ROUTE_ASSET",
        collection_code="coll_internal",
        fragment_code="ROUTE_SEC",
        content="route approved content",
    )
    map_fragment_to_knowledge_point(
        engine,
        asset_code="WP05_ROUTE_ASSET",
        version_no=1,
        fragment_code="ROUTE_SEC",
        kp_code="WP05_ROUTE_KP",
        relation_role="definition",
        review_status="approved",
        reviewed_by="reviewer_01",
    )

    monkeypatch.setattr(main, "sync_engine", engine)

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Using `httpx` with `starlette.testclient` is deprecated")
        from fastapi.testclient import TestClient

        client = TestClient(main.app)

    anonymous = client.get("/knowledge-points/WP05_ROUTE_KP/fragments")
    denied = client.get(
        "/knowledge-points/WP05_ROUTE_KP/fragments",
        headers={"X-Org-Code": "org_operations"},
    )
    allowed = client.get(
        "/knowledge-points/WP05_ROUTE_KP/fragments",
        headers={"X-Org-Code": "org_teaching_materials"},
    )
    missing = client.get(
        "/knowledge-points/NO_SUCH_KP/fragments",
        headers={"X-Org-Code": "org_teaching_materials"},
    )

    assert anonymous.status_code == 401
    assert denied.status_code == 200
    assert "route approved content" not in denied.text
    assert denied.json()["fragments"] == []
    assert allowed.status_code == 200
    assert allowed.json()["fragments"][0]["content"] == "route approved content"
    assert missing.status_code == 404
