"""WP04 database constraint tests — assets, versions, fragments, immutability."""

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from db.tests.fixtures_wp02 import seed_fixtures as seed_wp02


@pytest.fixture(scope="module", autouse=True)
def _migrate_module(alembic_cfg: AlembicConfig, engine: Engine):
    command.upgrade(alembic_cfg, "head")
    seed_wp02(engine)


def _seed_asset(engine: Engine, code: str = "asset_test", title: str = "Asset Test") -> int:
    with engine.begin() as conn:
        row = conn.execute(
            text("""
                INSERT INTO knowledge.asset (
                    code, asset_type, title, collection_id, owner_org_id, confidentiality
                )
                SELECT :code, 'policy', :title, c.id, o.id, 'internal'
                  FROM knowledge.collection c
                  JOIN iam.organization_unit o ON o.code = 'org_teaching_materials'
                 WHERE c.code = 'coll_internal'
                ON CONFLICT (code) DO UPDATE SET title = EXCLUDED.title
                RETURNING id
            """),
            {"code": code, "title": title},
        ).fetchone()
    assert row is not None
    return row.id


def _seed_version(
    engine: Engine,
    asset_id: int,
    *,
    version_no: int = 1,
    sha: str = "sha_test",
    review_status: str = "pending",
) -> int:
    with engine.begin() as conn:
        row = conn.execute(
            text("""
                INSERT INTO knowledge.asset_version (
                    asset_id, version_no, object_key, mime_type, extracted_text,
                    content_sha256, review_status
                )
                VALUES (:asset_id, :version_no, :object_key, 'text/plain', 'body', :sha, :review_status)
                RETURNING id
            """),
            {
                "asset_id": asset_id,
                "version_no": version_no,
                "object_key": f"assets/{sha}",
                "sha": sha,
                "review_status": review_status,
            },
        ).fetchone()
    assert row is not None
    return row.id


def test_asset_code_must_be_unique(engine: Engine):
    _seed_asset(engine, "asset_unique", "Unique A")
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            text("""
                    INSERT INTO knowledge.asset (
                        code, asset_type, title, collection_id, owner_org_id, confidentiality
                    )
                    SELECT 'asset_unique', 'policy', 'Duplicate', c.id, o.id, 'internal'
                      FROM knowledge.collection c
                      JOIN iam.organization_unit o ON o.code = 'org_teaching_materials'
                     WHERE c.code = 'coll_internal'
                """)
        )


@pytest.mark.parametrize(
    ("column", "bad_value"),
    [
        ("asset_type", "video"),
        ("confidentiality", "top_secret"),
        ("status", "deleted"),
    ],
)
def test_asset_checks_reject_invalid_values(engine: Engine, column: str, bad_value: str):
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            text(f"""
                    INSERT INTO knowledge.asset (
                        code, asset_type, title, collection_id, owner_org_id, confidentiality, status
                    )
                    SELECT 'asset_bad_{column}', 'policy', 'Bad', c.id, o.id, 'internal', 'draft'
                      FROM knowledge.collection c
                      JOIN iam.organization_unit o ON o.code = 'org_teaching_materials'
                     WHERE c.code = 'coll_internal'
                """.replace(f"{column},", f"{column},")),
        )
        conn.execute(
            text(f"UPDATE knowledge.asset SET {column} = :bad WHERE code = :code"),
            {"bad": bad_value, "code": f"asset_bad_{column}"},
        )


def test_asset_fk_must_exist(engine: Engine):
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            text("""
                    INSERT INTO knowledge.asset (
                        code, asset_type, title, collection_id, owner_org_id, confidentiality
                    )
                    VALUES ('asset_orphan', 'policy', 'Orphan', 999999, 999999, 'internal')
                """)
        )


def test_asset_version_fk_and_version_check(engine: Engine):
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            text("""
                    INSERT INTO knowledge.asset_version (asset_id, version_no, content_sha256)
                    VALUES (999999, 1, 'sha_orphan')
                """)
        )

    asset_id = _seed_asset(engine, "asset_bad_version", "Bad Version")
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            text("""
                    INSERT INTO knowledge.asset_version (asset_id, version_no, content_sha256)
                    VALUES (:asset_id, 0, 'sha_bad_version')
                """),
            {"asset_id": asset_id},
        )


def test_asset_version_unique_version_and_sha(engine: Engine):
    asset_id = _seed_asset(engine, "asset_versions", "Versions")
    _seed_version(engine, asset_id, version_no=1, sha="sha_unique_a")

    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            text("""
                    INSERT INTO knowledge.asset_version (asset_id, version_no, content_sha256)
                    VALUES (:asset_id, 1, 'sha_unique_b')
                """),
            {"asset_id": asset_id},
        )

    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            text("""
                    INSERT INTO knowledge.asset_version (asset_id, version_no, content_sha256)
                    VALUES (:asset_id, 2, 'sha_unique_a')
                """),
            {"asset_id": asset_id},
        )


def test_approved_asset_version_immutable_fields_cannot_change(engine: Engine):
    asset_id = _seed_asset(engine, "asset_immutable", "Immutable")
    version_id = _seed_version(engine, asset_id, version_no=1, sha="sha_immutable", review_status="approved")

    with pytest.raises(SQLAlchemyError), engine.begin() as conn:
        conn.execute(
            text("""
                    UPDATE knowledge.asset_version
                       SET object_key = 'assets/changed'
                     WHERE id = :version_id
                """),
            {"version_id": version_id},
        )


def test_fragment_constraints_and_cascade(engine: Engine):
    asset_id = _seed_asset(engine, "asset_fragment", "Fragment")
    version_id = _seed_version(engine, asset_id, version_no=1, sha="sha_fragment")

    with engine.begin() as conn:
        parent_id = conn.execute(
            text("""
                INSERT INTO knowledge.fragment (
                    asset_version_id, fragment_code, fragment_type, sequence_no,
                    heading, content, page_from, page_to
                )
                VALUES (:version_id, 'CH01', 'chapter', 1, 'Chapter', 'Body', 1, 3)
                RETURNING id
            """),
            {"version_id": version_id},
        ).scalar_one()

    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            text("""
                    INSERT INTO knowledge.fragment (asset_version_id, fragment_code, fragment_type, content)
                    VALUES (:version_id, 'CH01', 'section', 'Duplicate')
                """),
            {"version_id": version_id},
        )

    bad_fragment_sql = [
        """
        INSERT INTO knowledge.fragment (asset_version_id, fragment_code, fragment_type, content)
        VALUES (999999, 'ORPHAN', 'section', 'x')
        """,
        """
        INSERT INTO knowledge.fragment (asset_version_id, fragment_code, fragment_type, content)
        VALUES (:version_id, 'BAD_TYPE', 'video', 'x')
        """,
        """
        INSERT INTO knowledge.fragment (
            asset_version_id, fragment_code, fragment_type, content, page_from
        )
        VALUES (:version_id, 'BAD_PAGE', 'page', 'x', 0)
        """,
        """
        INSERT INTO knowledge.fragment (
            asset_version_id, fragment_code, fragment_type, content, page_from, page_to
        )
        VALUES (:version_id, 'BAD_RANGE', 'page', 'x', 5, 4)
        """,
    ]
    for sql in bad_fragment_sql:
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(text(sql), {"version_id": version_id})

    with engine.begin() as conn:
        child_id = conn.execute(
            text("""
                INSERT INTO knowledge.fragment (
                    asset_version_id, fragment_code, fragment_type, parent_id,
                    sequence_no, heading, content, page_from, page_to
                )
                VALUES (:version_id, 'CH01_SEC01', 'section', :parent_id, 1, 'Section', 'Child', 2, 2)
                RETURNING id
            """),
            {"version_id": version_id, "parent_id": parent_id},
        ).scalar_one()
        assert child_id is not None
        conn.execute(text("DELETE FROM knowledge.asset_version WHERE id = :version_id"), {"version_id": version_id})
        remaining = conn.execute(
            text("SELECT count(*) FROM knowledge.fragment WHERE asset_version_id = :version_id"),
            {"version_id": version_id},
        ).scalar_one()
    assert remaining == 0
