"""WP05 database constraint tests — reusable knowledge points and fragment mappings."""

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from db.tests.fixtures_wp02 import seed_fixtures as seed_wp02
from db.tests.fixtures_wp03 import seed_fixtures as seed_wp03


@pytest.fixture(scope="module", autouse=True)
def _migrate_module(alembic_cfg: AlembicConfig, engine: Engine):
    command.upgrade(alembic_cfg, "head")
    seed_wp02(engine)
    seed_wp03(engine)


def _seed_kp(engine: Engine, code: str = "KP_TEST", *, status: str = "active", merged_into: int | None = None) -> int:
    with engine.begin() as conn:
        row = conn.execute(
            text("""
                INSERT INTO knowledge.knowledge_point (
                    code, name, domain_code, cognitive_level, description,
                    status, merged_into_kp_id
                )
                VALUES (:code, :name, 'law', 'understand', 'desc', :status, :merged_into)
                RETURNING id
            """),
            {
                "code": code,
                "name": code.replace("_", " ").title(),
                "status": status,
                "merged_into": merged_into,
            },
        ).fetchone()
    assert row is not None
    return row.id


def _seed_fragment(engine: Engine, *, asset_code: str = "WP05_ASSET", fragment_code: str = "ARTICLE_09") -> int:
    with engine.begin() as conn:
        row = conn.execute(
            text("""
                WITH refs AS (
                    SELECT c.id AS collection_id, o.id AS owner_org_id
                      FROM knowledge.collection c
                      JOIN iam.organization_unit o ON o.code = 'org_teaching_materials'
                     WHERE c.code = 'coll_internal'
                ),
                asset_row AS (
                    INSERT INTO knowledge.asset (
                        code, asset_type, title, collection_id, owner_org_id, confidentiality
                    )
                    SELECT :asset_code, 'policy', :asset_code, collection_id, owner_org_id, 'internal'
                      FROM refs
                    ON CONFLICT (code) DO UPDATE SET title = EXCLUDED.title
                    RETURNING id
                ),
                version_row AS (
                    INSERT INTO knowledge.asset_version (
                        asset_id, version_no, object_key, mime_type, extracted_text, content_sha256
                    )
                    SELECT id, 1, :asset_code || '/v1', 'text/plain', 'extracted', :asset_code || '_sha'
                      FROM asset_row
                    ON CONFLICT (content_sha256) DO UPDATE SET extracted_text = EXCLUDED.extracted_text
                    RETURNING id
                )
                INSERT INTO knowledge.fragment (
                    asset_version_id, fragment_code, fragment_type, heading, content, page_from, page_to
                )
                SELECT id, :fragment_code, 'clause', 'Article 9', 'eligible content', 1, 1
                  FROM version_row
                ON CONFLICT (asset_version_id, fragment_code) DO UPDATE SET content = EXCLUDED.content
                RETURNING id
            """),
            {"asset_code": asset_code, "fragment_code": fragment_code},
        ).fetchone()
    assert row is not None
    return row.id


def test_knowledge_point_unique_checks_parent_and_status(engine: Engine):
    parent_id = _seed_kp(engine, "KP_PARENT")

    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO knowledge.knowledge_point (code, name, parent_id, domain_code)
                VALUES ('KP_CHILD_BAD_PARENT', 'bad', 999999, 'law')
            """)
        )

    with engine.begin() as conn:
        child_id = conn.execute(
            text("""
                INSERT INTO knowledge.knowledge_point (code, name, parent_id, domain_code, cognitive_level)
                VALUES ('KP_CHILD', 'child', :parent_id, 'law', 'apply')
                RETURNING id
            """),
            {"parent_id": parent_id},
        ).scalar_one()

    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text("UPDATE knowledge.knowledge_point SET parent_id = id WHERE id = :id"), {"id": child_id})

    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO knowledge.knowledge_point (code, name, domain_code, cognitive_level)
                VALUES ('KP_BAD_LEVEL', 'bad', 'law', 'memorize')
            """)
        )

    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO knowledge.knowledge_point (code, name, domain_code, status)
                VALUES ('KP_BAD_STATUS', 'bad', 'law', 'deleted')
            """)
        )


def test_relation_rejects_self_invalid_type_and_duplicates(engine: Engine):
    from_id = _seed_kp(engine, "KP_REL_FROM")
    to_id = _seed_kp(engine, "KP_REL_TO")

    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO knowledge.knowledge_point_relation (from_kp_id, to_kp_id, relation_type)
                VALUES (:from_id, :to_id, 'prerequisite')
            """),
            {"from_id": from_id, "to_id": to_id},
        )

    bad_rows = [
        {"from_id": from_id, "to_id": from_id, "relation_type": "related"},
        {"from_id": from_id, "to_id": to_id, "relation_type": "blocks"},
        {"from_id": from_id, "to_id": to_id, "relation_type": "prerequisite"},
    ]
    for row in bad_rows:
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO knowledge.knowledge_point_relation (from_kp_id, to_kp_id, relation_type)
                    VALUES (:from_id, :to_id, :relation_type)
                """),
                row,
            )


def test_scope_allows_cross_certificate_subject_and_rejects_duplicates(engine: Engine):
    kp_id = _seed_kp(engine, "KP_SCOPE")

    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO knowledge.knowledge_point_scope (kp_id, scope_type, scope_code)
                VALUES (:kp_id, 'certificate', 'c_constructor_1'),
                       (:kp_id, 'certificate', 'c_pharmacist_licensed'),
                       (:kp_id, 'exam_subject', 'subj_constructor_mgmt')
            """),
            {"kp_id": kp_id},
        )

    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO knowledge.knowledge_point_scope (kp_id, scope_type, scope_code)
                VALUES (:kp_id, 'certificate', 'c_constructor_1')
            """),
            {"kp_id": kp_id},
        )

    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO knowledge.knowledge_point_scope (kp_id, scope_type, scope_code)
                VALUES (:kp_id, 'city', 'beijing')
            """),
            {"kp_id": kp_id},
        )


def test_fragment_mapping_requires_valid_refs_review_rules_and_confidence(engine: Engine):
    kp_id = _seed_kp(engine, "KP_FRAGMENT")
    fragment_id = _seed_fragment(engine, asset_code="WP05_FRAGMENT_ASSET")

    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO knowledge.fragment_knowledge_point (
                    fragment_id, kp_id, relation_role, confidence, review_status
                )
                VALUES (:fragment_id, :kp_id, 'evidence', 0.8, 'pending')
            """),
            {"fragment_id": fragment_id, "kp_id": kp_id},
        )

    bad_rows = [
        {"fragment_id": fragment_id, "kp_id": kp_id, "role": "video", "confidence": 0.5, "status": "pending", "reviewed_by": None},
        {"fragment_id": fragment_id, "kp_id": kp_id, "role": "example", "confidence": 1.5, "status": "pending", "reviewed_by": None},
        {"fragment_id": fragment_id, "kp_id": kp_id, "role": "example", "confidence": 0.5, "status": "approved", "reviewed_by": None},
        {"fragment_id": 999999, "kp_id": kp_id, "role": "example", "confidence": 0.5, "status": "pending", "reviewed_by": None},
        {"fragment_id": fragment_id, "kp_id": 999999, "role": "example", "confidence": 0.5, "status": "pending", "reviewed_by": None},
    ]
    for row in bad_rows:
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO knowledge.fragment_knowledge_point (
                        fragment_id, kp_id, relation_role, confidence, review_status, reviewed_by
                    )
                    VALUES (:fragment_id, :kp_id, :role, :confidence, :status, :reviewed_by)
                """),
                row,
            )


def test_merge_and_deprecate_preserve_history_code(engine: Engine):
    target_id = _seed_kp(engine, "KP_MERGE_TARGET")
    old_id = _seed_kp(engine, "KP_TO_DEPRECATE")

    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO knowledge.knowledge_point (code, name, domain_code, status)
                VALUES ('KP_BAD_MERGE', 'bad merge', 'law', 'merged')
            """)
        )

    with engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE knowledge.knowledge_point
                   SET status = 'deprecated'
                 WHERE id = :old_id
            """),
            {"old_id": old_id},
        )
        merged_code = conn.execute(
            text("""
                INSERT INTO knowledge.knowledge_point (
                    code, name, domain_code, status, merged_into_kp_id
                )
                VALUES ('KP_OLD_CODE', 'old code', 'law', 'merged', :target_id)
                RETURNING code
            """),
            {"target_id": target_id},
        ).scalar_one()
        codes = conn.execute(
            text("""
                SELECT code
                  FROM knowledge.knowledge_point
                 WHERE code IN ('KP_TO_DEPRECATE', 'KP_OLD_CODE', 'KP_MERGE_TARGET')
                 ORDER BY code
            """)
        ).scalars().all()

    assert merged_code == "KP_OLD_CODE"
    assert codes == ["KP_MERGE_TARGET", "KP_OLD_CODE", "KP_TO_DEPRECATE"]
