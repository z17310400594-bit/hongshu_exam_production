"""WP08 database constraint tests — content products, versions, chapters, and KPs."""

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

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


@pytest.fixture(scope="module", autouse=True)
def _migrate_module(alembic_cfg: AlembicConfig, engine: Engine):
    command.upgrade(alembic_cfg, "head")
    seed_wp02(engine)
    seed_wp03(engine)


def _seed_product_version_graph(engine: Engine, *, prefix: str, confidentiality: str = "internal"):
    source = seed_source_asset(
        engine,
        asset_code=f"{prefix}_ASSET",
        confidentiality=confidentiality,
        fragments=[
            ("CH01", "chapter", "第一章 基础", 1),
            ("CH01_SEC01", "section", "第一节 报考条件", 2),
        ],
    )
    product = seed_content_product(engine, code=f"{prefix}_PRODUCT")
    version = seed_product_version(
        engine,
        product_code=product["code"],
        asset_code=source["asset_code"],
        confidentiality=confidentiality,
    )
    return source, product, version


def test_product_and_version_constraints(engine: Engine):
    source, product, version = _seed_product_version_graph(engine, prefix="WP08_CONSTRAINT")
    assert product["product_type"] == "textbook"
    assert version["status"] == "approved"

    bad_product_rows = [
        {"code": "WP08_BAD_PRODUCT_TYPE", "ptype": "video", "status": "active"},
        {"code": "WP08_BAD_PRODUCT_STATUS", "ptype": "textbook", "status": "draft"},
    ]
    for row in bad_product_rows:
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO content.product (
                        code, certificate_id, product_type, title, owner_org_id, status
                    )
                    SELECT :code, cert.id, :ptype, 'Bad Product', org.id, :status
                      FROM core.certificate cert
                      JOIN iam.organization_unit org ON org.code = 'org_teaching_materials'
                     WHERE cert.code = 'c_constructor_1'
                """),
                row,
            )

    bad_version_rows = [
        {"version_no": 1, "conf": "internal", "status": "approved", "review": "approved", "reviewer": "r"},
        {"version_no": 0, "conf": "internal", "status": "approved", "review": "approved", "reviewer": "r"},
        {"version_no": 2, "conf": "secret", "status": "approved", "review": "approved", "reviewer": "r"},
        {"version_no": 3, "conf": "internal", "status": "editing", "review": "approved", "reviewer": "r"},
        {"version_no": 4, "conf": "internal", "status": "published", "review": "pending", "reviewer": None},
    ]
    for row in bad_version_rows:
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO content.product_version (
                        product_id, version_no, source_asset_version_id,
                        title, confidentiality, status, review_status, reviewed_by
                    )
                    VALUES (
                        :product_id, :version_no, :source_asset_version_id,
                        'Bad Version', :conf, :status, :review, :reviewer
                    )
                """),
                {
                    **row,
                    "product_id": product["id"],
                    "source_asset_version_id": source["asset_version_id"],
                },
            )

    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO content.product_version (
                    product_id, version_no, source_asset_version_id,
                    title, confidentiality, status, review_status, reviewed_by
                )
                VALUES (:product_id, 5, 999999, 'Bad FK', 'internal', 'approved', 'approved', 'r')
            """),
            {"product_id": product["id"]},
        )


def test_chapter_traceability_confidentiality_tree_and_publish_constraints(engine: Engine):
    source, _, version = _seed_product_version_graph(engine, prefix="WP08_CHAPTER")
    root = seed_chapter(
        engine,
        product_version_id=version["id"],
        source_fragment_id=source["fragment_ids"]["CH01"],
        chapter_code="CH01",
        title="第一章 基础",
    )
    child = seed_chapter(
        engine,
        product_version_id=version["id"],
        parent_id=root["id"],
        source_fragment_id=source["fragment_ids"]["CH01_SEC01"],
        chapter_code="CH01_SEC01",
        title="第一节 报考条件",
        sequence_no=2,
    )

    other_source, other_product, other_version = _seed_product_version_graph(engine, prefix="WP08_OTHER")
    other_root = seed_chapter(
        engine,
        product_version_id=other_version["id"],
        source_fragment_id=other_source["fragment_ids"]["CH01"],
        chapter_code="OTHER_CH01",
        title="其他第一章",
    )

    trigger_or_integrity_rows = [
        {
            "product_version_id": version["id"],
            "parent_id": None,
            "source_fragment_id": source["fragment_ids"]["CH01"],
            "chapter_code": "CH01",
            "title": "重复章节编码",
            "sequence_no": 3,
            "confidentiality": "internal",
            "review_status": "approved",
            "status": "published",
        },
        {
            "product_version_id": version["id"],
            "parent_id": None,
            "source_fragment_id": other_source["fragment_ids"]["CH01"],
            "chapter_code": "BAD_SOURCE",
            "title": "错误来源片段",
            "sequence_no": 3,
            "confidentiality": "internal",
            "review_status": "approved",
            "status": "published",
        },
        {
            "product_version_id": version["id"],
            "parent_id": None,
            "source_fragment_id": source["fragment_ids"]["CH01"],
            "chapter_code": "BAD_CONF",
            "title": "保密降级",
            "sequence_no": 3,
            "confidentiality": "public",
            "review_status": "approved",
            "status": "published",
        },
        {
            "product_version_id": version["id"],
            "parent_id": other_root["id"],
            "source_fragment_id": source["fragment_ids"]["CH01"],
            "chapter_code": "BAD_PARENT",
            "title": "跨版本父章节",
            "sequence_no": 3,
            "confidentiality": "internal",
            "review_status": "approved",
            "status": "published",
        },
        {
            "product_version_id": version["id"],
            "parent_id": None,
            "source_fragment_id": source["fragment_ids"]["CH01"],
            "chapter_code": "BAD_SEQUENCE",
            "title": "负序号",
            "sequence_no": -1,
            "confidentiality": "internal",
            "review_status": "approved",
            "status": "published",
        },
        {
            "product_version_id": version["id"],
            "parent_id": None,
            "source_fragment_id": source["fragment_ids"]["CH01"],
            "chapter_code": "BAD_REVIEW",
            "title": "未审核发布",
            "sequence_no": 3,
            "confidentiality": "internal",
            "review_status": "pending",
            "status": "published",
        },
    ]
    for row in trigger_or_integrity_rows:
        with pytest.raises(SQLAlchemyError), engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO content.chapter (
                        product_version_id, parent_id, source_fragment_id,
                        chapter_code, title, sequence_no,
                        confidentiality, review_status, status
                    )
                    VALUES (
                        :product_version_id, :parent_id, :source_fragment_id,
                        :chapter_code, :title, :sequence_no,
                        :confidentiality, :review_status, :status
                    )
                """),
                row,
            )

    with pytest.raises(SQLAlchemyError), engine.begin() as conn:
        conn.execute(
            text("UPDATE content.chapter SET parent_id = :child_id WHERE id = :root_id"),
            {"child_id": child["id"], "root_id": root["id"]},
        )

    with engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE content.product_version
                   SET status = 'published', review_status = 'approved', reviewed_by = 'wp08_reviewer'
                 WHERE id = :version_id
            """),
            {"version_id": version["id"]},
        )

    with pytest.raises(SQLAlchemyError), engine.begin() as conn:
        conn.execute(text("UPDATE content.chapter SET body = 'should fail' WHERE id = :chapter_id"), {"chapter_id": root["id"]})

    seed_product_version(
        engine,
        product_code=other_product["code"],
        asset_code=other_source["asset_code"],
        version_no=2,
        title="其他教材修订版",
    )


def test_product_version_cannot_publish_with_unapproved_chapters(engine: Engine):
    source, _, version = _seed_product_version_graph(engine, prefix="WP08_PUBLISH")
    seed_chapter(
        engine,
        product_version_id=version["id"],
        source_fragment_id=source["fragment_ids"]["CH01"],
        chapter_code="CH01_DRAFT",
        title="未审核章节",
        review_status="pending",
        status="draft",
    )

    with pytest.raises(SQLAlchemyError), engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE content.product_version
                   SET status = 'published', review_status = 'approved', reviewed_by = 'wp08_reviewer'
                 WHERE id = :version_id
            """),
            {"version_id": version["id"]},
        )


def test_chapter_knowledge_point_constraints(engine: Engine):
    source, _, version = _seed_product_version_graph(engine, prefix="WP08_KP_GRAPH")
    chapter = seed_chapter(
        engine,
        product_version_id=version["id"],
        source_fragment_id=source["fragment_ids"]["CH01"],
        chapter_code="CH01",
        title="第一章 基础",
    )
    kp = seed_knowledge_point(engine, code="WP08_KP_CONSTRAINT", name="WP08 约束知识点")
    seed_chapter_knowledge_point(engine, chapter_id=chapter["id"], kp_code=kp["code"])

    bad_rows = [
        {"chapter_id": chapter["id"], "kp_id": kp["id"], "role": "core", "review": "approved", "reviewer": "r"},
        {"chapter_id": chapter["id"], "kp_id": kp["id"], "role": "summary", "review": "approved", "reviewer": "r"},
        {"chapter_id": chapter["id"], "kp_id": kp["id"], "role": "example", "review": "approved", "reviewer": None},
        {"chapter_id": 999999, "kp_id": kp["id"], "role": "example", "review": "approved", "reviewer": "r"},
        {"chapter_id": chapter["id"], "kp_id": 999999, "role": "example", "review": "approved", "reviewer": "r"},
    ]
    for row in bad_rows:
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO content.chapter_knowledge_point (
                        chapter_id, kp_id, teaching_role, review_status, reviewed_by
                    )
                    VALUES (:chapter_id, :kp_id, :role, :review, :reviewer)
                """),
                row,
            )
