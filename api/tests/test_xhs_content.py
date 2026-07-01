"""Xiaohongshu content generator MVP tests."""

from __future__ import annotations

import json
import warnings
from collections.abc import Generator
from urllib.parse import urlparse, urlunparse

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from api.config import settings
from api.services.xhs_content import (
    MAX_SOURCE_TEXT_CHARS,
    generate_xhs_content,
    get_xhs_chapter,
    list_xhs_chapters,
)
from db.tests.fixtures_wp02 import seed_fixtures as seed_wp02
from db.tests.fixtures_wp03 import seed_fixtures as seed_wp03


@pytest.fixture(scope="module")
def engine() -> Generator[Engine, None, None]:
    parsed = urlparse(settings.database_url)
    test_db_name = "knowledge_platform_v2_test_xhs_content"
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
def _seed_xhs_fragments(engine: Engine):
    _seed_asset_fragment(
        engine,
        asset_code="pharm_xhs_textbook_demo",
        asset_type="textbook",
        fragment_code="XHS_MAHUANG",
        heading="中药二 / 解表药 / 麻黄",
        content="麻黄：发汗散寒，宣肺平喘，利水消肿。主治风寒表实无汗证，肺气不宣之胸闷喘咳。",
    )
    _seed_asset_fragment(
        engine,
        asset_code="pharm_xhs_handout_long",
        asset_type="handout",
        fragment_code="XHS_LONG",
        heading="执业药师长片段",
        content="A" * (MAX_SOURCE_TEXT_CHARS + 20),
    )


def _seed_asset_fragment(
    engine: Engine,
    *,
    asset_code: str,
    asset_type: str,
    fragment_code: str,
    heading: str,
    content: str,
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("""
                WITH refs AS (
                    SELECT c.id AS collection_id, o.id AS owner_org_id
                      FROM knowledge.collection c
                      JOIN iam.organization_unit o ON o.code = 'org_teaching_materials'
                     WHERE c.code = 'coll_internal'
                ),
                asset_row AS (
                    INSERT INTO knowledge.asset (
                        code, asset_type, title, collection_id, owner_org_id,
                        confidentiality, status
                    )
                    SELECT :asset_code, :asset_type, :asset_code, collection_id, owner_org_id,
                           'internal', 'published'
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
                SELECT id, :fragment_code, 'section', :heading, :content, 1, 1
                  FROM version_row
            """),
            {"asset_code": asset_code, "asset_type": asset_type, "fragment_code": fragment_code, "heading": heading, "content": content},
        )


def test_lists_pharmacist_fragments_as_chapter_options(engine: Engine):
    result = list_xhs_chapters(
        engine,
        principal_type="org",
        principal_code="org_teaching_materials",
        certificate_code="pharmacist_licensed",
        query="麻黄",
    )

    assert result["items"]
    assert result["items"][0]["chapterCode"] == "XHS_MAHUANG"
    assert result["items"][0]["title"] == "中药二 / 解表药 / 麻黄"
    assert "麻黄" in result["items"][0]["textPreview"]


def test_chapter_detail_truncates_database_source(engine: Engine):
    result = get_xhs_chapter(
        engine,
        principal_type="org",
        principal_code="org_teaching_materials",
        chapter_id="XHS_LONG",
    )

    assert result["sourceTruncated"] is True
    assert len(result["sourceText"]) == MAX_SOURCE_TEXT_CHARS
    assert result["textLength"] == MAX_SOURCE_TEXT_CHARS + 20


def test_generate_parses_dify_json(monkeypatch: pytest.MonkeyPatch, engine: Engine):
    import api.services.xhs_content as service

    def fake_dify(inputs: dict):
        assert inputs["source_text"].startswith("麻黄")
        return json.dumps(
            {
                "meta": {
                    "angle_type": "错因诊断",
                    "target_user": "学了一段但做题总错",
                    "tone": "备考陪跑",
                    "length_style": "短平快",
                    "cta_type": "收藏+评论卡点",
                },
                "internal": {"source_basis": [], "core_point": "判断抓手", "risk_notes": [], "self_check": []},
                "external": {
                    "title_candidates": [],
                    "selected_title_index": 0,
                    "cover_copy": "",
                    "cards": [],
                    "caption": "",
                    "hashtags": [],
                    "cta": "",
                    "today_action": "",
                },
                "next_topics": [],
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(service, "_call_xhs_dify", fake_dify)
    result = generate_xhs_content(
        engine,
        principal_type="org",
        principal_code="org_teaching_materials",
        payload={"source_mode": "database", "chapter_id": "XHS_MAHUANG", "knowledge_keyword": "麻黄"},
    )

    assert result["ok"] is True
    assert result["data"]["internal"]["core_point"] == "判断抓手"


def test_generate_keeps_raw_output_when_json_parse_fails(monkeypatch: pytest.MonkeyPatch, engine: Engine):
    import api.services.xhs_content as service

    monkeypatch.setattr(service, "_call_xhs_dify", lambda inputs: "not json")
    result = generate_xhs_content(
        engine,
        principal_type="org",
        principal_code="org_teaching_materials",
        payload={"source_mode": "database", "chapter_id": "XHS_MAHUANG"},
    )

    assert result["ok"] is False
    assert result["raw_output"] == "not json"
    assert result["error"]["code"] == "LLM_JSON_PARSE_ERROR"


def test_custom_text_over_limit_is_rejected(engine: Engine):
    result = generate_xhs_content(
        engine,
        principal_type="org",
        principal_code="org_teaching_materials",
        payload={"source_mode": "custom_text", "custom_text": "A" * (MAX_SOURCE_TEXT_CHARS + 1)},
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "CUSTOM_TEXT_TOO_LONG"


def test_routes_require_identity_and_return_chapters(engine: Engine, monkeypatch: pytest.MonkeyPatch):
    import api.main as main

    monkeypatch.setattr(main, "sync_engine", engine)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Using `httpx` with `starlette.testclient` is deprecated")
        from fastapi.testclient import TestClient

        client = TestClient(main.app)

    anonymous = client.get("/api/xhs-content/chapters")
    allowed = client.get("/api/xhs-content/chapters?query=麻黄", headers={"X-Org-Code": "org_teaching_materials"})

    assert anonymous.status_code == 401
    assert allowed.status_code == 200
    assert allowed.json()["items"][0]["chapterCode"] == "XHS_MAHUANG"
