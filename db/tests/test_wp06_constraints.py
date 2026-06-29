"""WP06 database constraint tests — policy facts and eligibility evidence."""

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, ProgrammingError

from db.tests.fixtures_wp02 import seed_fixtures as seed_wp02
from db.tests.fixtures_wp03 import seed_fixtures as seed_wp03
from db.tests.fixtures_wp06 import seed_eligibility_rule, seed_policy_document

CONSTRAINT_ERROR = (IntegrityError, ProgrammingError)


@pytest.fixture(scope="module", autouse=True)
def _migrate_module(alembic_cfg: AlembicConfig, engine: Engine):
    command.upgrade(alembic_cfg, "head")
    seed_wp02(engine)
    seed_wp03(engine)


def test_policy_document_version_and_clause_constraints(engine: Engine):
    refs = seed_policy_document(engine, prefix="WP06_DOC_CONSTRAINT", clause_codes=("ARTICLE_09",))

    with pytest.raises(CONSTRAINT_ERROR), engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO policy.document (
                    asset_id, document_code, issuing_authority
                )
                VALUES (999999, 'WP06_BAD_ASSET_DOC', 'Authority')
            """)
        )

    with pytest.raises(CONSTRAINT_ERROR), engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO policy.document (
                    asset_id, document_code, issuing_authority
                )
                SELECT asset_id, 'WP06_DUP_ASSET_DOC', 'Authority'
                  FROM knowledge.asset_version
                 WHERE id = :asset_version_id
            """),
            {"asset_version_id": refs["asset_version_id"]},
        )

    with pytest.raises(CONSTRAINT_ERROR), engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO policy.document_version (
                    document_id, asset_version_id, version_no, valid_during, status
                )
                VALUES (:document_id, 999999, 2, daterange('2020-01-01', NULL, '[)'), 'published')
            """),
            {"document_id": refs["document_id"]},
        )

    with pytest.raises(CONSTRAINT_ERROR), engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO policy.document_version (
                    document_id, asset_version_id, version_no, valid_during, status
                )
                VALUES (:document_id, :asset_version_id, 2, daterange('2020-01-01', NULL, '[)'), 'deleted')
            """),
            {"document_id": refs["document_id"], "asset_version_id": refs["asset_version_id"]},
        )

    with pytest.raises(CONSTRAINT_ERROR), engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO policy.document_version (
                    document_id, asset_version_id, version_no, valid_during, status
                )
                VALUES (:document_id, :asset_version_id, 2, daterange('2024-01-01', '2024-01-01', '[)'), 'published')
            """),
            {"document_id": refs["document_id"], "asset_version_id": refs["asset_version_id"]},
        )

    with pytest.raises(CONSTRAINT_ERROR), engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO policy.clause (
                    document_version_id, fragment_id, clause_code
                )
                VALUES (:document_version_id, 999999, 'BAD_FRAGMENT')
            """),
            {"document_version_id": refs["document_version_id"]},
        )

    with pytest.raises(CONSTRAINT_ERROR), engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO policy.clause (
                    document_version_id, fragment_id, clause_code
                )
                SELECT :document_version_id, fragment_id, 'DUP_FRAGMENT'
                  FROM policy.clause
                 WHERE id = :clause_id
            """),
            {
                "document_version_id": refs["document_version_id"],
                "clause_id": refs["clauses"]["ARTICLE_09"],
            },
        )


def test_eligibility_rule_constraints_and_publish_trigger(engine: Engine):
    refs = seed_policy_document(engine, prefix="WP06_RULE_CONSTRAINT", clause_codes=("ARTICLE_09", "ARTICLE_22"))
    clause_id = refs["clauses"]["ARTICLE_09"]

    seed_eligibility_rule(
        engine,
        code="WP06_RULE_OK",
        certificate_id=refs["certificate_id"],
        knowledge_point_id=refs["knowledge_point_id"],
        clause_id=clause_id,
        min_relevant_work_months=36,
    )

    base_row = {
        "certificate_id": refs["certificate_id"],
        "kp_id": refs["knowledge_point_id"],
        "route": "normal",
        "months": 0,
        "extra": "{}",
        "status": "draft",
        "review": "pending",
        "reviewed_by": None,
    }
    bad_rows = [
        {**base_row, "code": "WP06_RULE_DUP"},
        {**base_row, "code": "WP06_BAD_CERT", "certificate_id": 999999},
        {**base_row, "code": "WP06_BAD_KP", "kp_id": 999999},
        {**base_row, "code": "WP06_BAD_ROUTE", "route": "legacy"},
        {**base_row, "code": "WP06_BAD_MONTHS", "months": -1},
        {**base_row, "code": "WP06_BAD_JSON", "extra": "[]"},
        {**base_row, "code": "WP06_BAD_STATUS", "status": "deleted"},
        {**base_row, "code": "WP06_BAD_REVIEW", "review": "approved"},
    ]

    # First insert a duplicate target so the duplicate-code case is explicit.
    seed_eligibility_rule(
        engine,
        code="WP06_RULE_DUP",
        certificate_id=refs["certificate_id"],
        knowledge_point_id=refs["knowledge_point_id"],
        clause_id=refs["clauses"]["ARTICLE_22"],
    )

    for row in bad_rows:
        with pytest.raises(CONSTRAINT_ERROR), engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO policy.eligibility_rule (
                        code, certificate_id, knowledge_point_id, route_code,
                        min_relevant_work_months, extra_conditions, valid_during,
                        status, review_status, reviewed_by
                    )
                    VALUES (
                        :code, :certificate_id, :kp_id, :route, :months,
                        CAST(:extra AS jsonb), daterange('2020-01-01', NULL, '[)'),
                        :status, :review, :reviewed_by
                    )
                """),
                row,
            )

    with pytest.raises(CONSTRAINT_ERROR), engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO policy.eligibility_rule (
                    code, certificate_id, knowledge_point_id, valid_during,
                    status, review_status, reviewed_by
                )
                VALUES (
                    'WP06_PUBLISHED_PENDING', :certificate_id, :kp_id,
                    daterange('2020-01-01', NULL, '[)'),
                    'published', 'pending', NULL
                )
            """),
            {"certificate_id": refs["certificate_id"], "kp_id": refs["knowledge_point_id"]},
        )

    with pytest.raises(CONSTRAINT_ERROR), engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO policy.eligibility_rule (
                    code, certificate_id, knowledge_point_id, valid_during,
                    status, review_status, reviewed_by
                )
                VALUES (
                    'WP06_PUBLISHED_NO_PRIMARY', :certificate_id, :kp_id,
                    daterange('2020-01-01', NULL, '[)'),
                    'published', 'approved', 'reviewer_01'
                )
            """),
            {"certificate_id": refs["certificate_id"], "kp_id": refs["knowledge_point_id"]},
        )


def test_evidence_constraints_and_delete_primary_from_published_rule(engine: Engine):
    refs = seed_policy_document(engine, prefix="WP06_EVIDENCE", clause_codes=("ARTICLE_09", "ARTICLE_22"))
    rule_id = seed_eligibility_rule(
        engine,
        code="WP06_EVIDENCE_RULE",
        certificate_id=refs["certificate_id"],
        knowledge_point_id=refs["knowledge_point_id"],
        clause_id=refs["clauses"]["ARTICLE_09"],
    )

    bad_rows = [
        {"rule_id": rule_id, "clause_id": refs["clauses"]["ARTICLE_22"], "role": "quote"},
        {"rule_id": 999999, "clause_id": refs["clauses"]["ARTICLE_22"], "role": "supporting"},
        {"rule_id": rule_id, "clause_id": 999999, "role": "supporting"},
        {"rule_id": rule_id, "clause_id": refs["clauses"]["ARTICLE_09"], "role": "primary"},
    ]
    for row in bad_rows:
        with pytest.raises(CONSTRAINT_ERROR), engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO policy.eligibility_rule_evidence (
                        eligibility_rule_id, clause_id, evidence_role
                    )
                    VALUES (:rule_id, :clause_id, :role)
                """),
                row,
            )

    with pytest.raises(CONSTRAINT_ERROR), engine.begin() as conn:
        conn.execute(
            text("""
                DELETE FROM policy.eligibility_rule_evidence
                 WHERE eligibility_rule_id = :rule_id
                   AND evidence_role = 'primary'
            """),
            {"rule_id": rule_id},
        )
