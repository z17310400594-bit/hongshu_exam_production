"""WP06 fixtures — policy documents, clauses, and eligibility rules."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine


def seed_policy_document(
    engine: Engine,
    *,
    prefix: str,
    certificate_code: str = "c_constructor_1",
    collection_code: str = "coll_internal",
    document_status: str = "published",
    valid_from: str = "2020-01-01",
    valid_to: str | None = None,
    clause_codes: tuple[str, ...] = ("ARTICLE_09",),
) -> dict[str, Any]:
    """Create one policy asset/document/version with clause fragments."""
    with engine.begin() as conn:
        kp_id = conn.execute(
            text("""
                INSERT INTO knowledge.knowledge_point (
                    code, name, domain_code, cognitive_level, description
                )
                VALUES (:kp_code, :kp_name, 'policy', 'apply', 'eligibility policy')
                RETURNING id
            """),
            {"kp_code": f"{prefix}_KP", "kp_name": f"{prefix} eligibility"},
        ).scalar_one()

        cert_id = conn.execute(
            text("SELECT id FROM core.certificate WHERE code = :code"),
            {"code": certificate_code},
        ).scalar_one()

        asset_version_id = conn.execute(
            text("""
                WITH refs AS (
                    SELECT c.id AS collection_id, o.id AS owner_org_id
                      FROM knowledge.collection c
                      JOIN iam.organization_unit o ON o.id = c.owner_org_id
                     WHERE c.code = :collection_code
                ),
                asset_row AS (
                    INSERT INTO knowledge.asset (
                        code, asset_type, title, collection_id, owner_org_id,
                        confidentiality, status
                    )
                    SELECT :asset_code, 'policy', :asset_code, collection_id, owner_org_id,
                           'internal', 'published'
                      FROM refs
                    RETURNING id
                )
                INSERT INTO knowledge.asset_version (
                    asset_id, version_no, object_key, mime_type, extracted_text,
                    content_sha256, valid_during, review_status, reviewed_by, reviewed_at
                )
                SELECT id, 1, :asset_code || '/v1', 'text/plain', :asset_code || ' extracted',
                       :asset_code || '_sha', daterange(:valid_from, :valid_to, '[)'),
                       'approved', 'reviewer_01', now()
                  FROM asset_row
                RETURNING id
            """),
            {
                "collection_code": collection_code,
                "asset_code": f"{prefix}_ASSET",
                "valid_from": valid_from,
                "valid_to": valid_to,
            },
        ).scalar_one()

        document_id = conn.execute(
            text("""
                INSERT INTO policy.document (
                    asset_id, document_code, doc_number, issuing_authority, official_url
                )
                SELECT asset_id, :document_code, :doc_number, 'Test Authority', 'https://example.test/policy'
                  FROM knowledge.asset_version
                 WHERE id = :asset_version_id
                RETURNING id
            """),
            {
                "asset_version_id": asset_version_id,
                "document_code": f"{prefix}_DOC",
                "doc_number": f"{prefix}-2026",
            },
        ).scalar_one()

        document_version_id = conn.execute(
            text("""
                INSERT INTO policy.document_version (
                    document_id, asset_version_id, version_no, published_on,
                    valid_during, status
                )
                VALUES (
                    :document_id, :asset_version_id, 1, :published_on,
                    daterange(:valid_from, :valid_to, '[)'), :document_status
                )
                RETURNING id
            """),
            {
                "document_id": document_id,
                "asset_version_id": asset_version_id,
                "published_on": date.fromisoformat(valid_from),
                "valid_from": valid_from,
                "valid_to": valid_to,
                "document_status": document_status,
            },
        ).scalar_one()

        clauses: dict[str, int] = {}
        for index, clause_code in enumerate(clause_codes, start=1):
            fragment_id = conn.execute(
                text("""
                    INSERT INTO knowledge.fragment (
                        asset_version_id, fragment_code, fragment_type, sequence_no,
                        heading, content, page_from, page_to
                    )
                    VALUES (
                        :asset_version_id, :fragment_code, 'clause', :sequence_no,
                        :fragment_code, :content, :sequence_no, :sequence_no
                    )
                    RETURNING id
                """),
                {
                    "asset_version_id": asset_version_id,
                    "fragment_code": clause_code,
                    "sequence_no": index,
                    "content": f"{prefix} {clause_code} policy content",
                },
            ).scalar_one()
            clause_id = conn.execute(
                text("""
                    INSERT INTO policy.clause (
                        document_version_id, fragment_id, clause_code, section_path, summary
                    )
                    VALUES (
                        :document_version_id, :fragment_id, :clause_code,
                        :section_path, :summary
                    )
                    RETURNING id
                """),
                {
                    "document_version_id": document_version_id,
                    "fragment_id": fragment_id,
                    "clause_code": clause_code,
                    "section_path": f"Chapter {index}",
                    "summary": f"{clause_code} summary",
                },
            ).scalar_one()
            clauses[clause_code] = clause_id

    return {
        "certificate_id": cert_id,
        "knowledge_point_id": kp_id,
        "document_id": document_id,
        "document_version_id": document_version_id,
        "asset_version_id": asset_version_id,
        "clauses": clauses,
    }


def seed_eligibility_rule(
    engine: Engine,
    *,
    code: str,
    certificate_id: int,
    knowledge_point_id: int,
    clause_id: int,
    qualification_level: str | None = "first_exam",
    route_code: str = "normal",
    degree_level_code: str | None = "bachelor",
    major_category_code: str | None = "law",
    education_type_code: str | None = "full_time",
    min_total_work_months: int = 0,
    min_relevant_work_months: int = 0,
    admission_before: str | None = None,
    region_code: str = "CN",
    valid_from: str = "2020-01-01",
    valid_to: str | None = None,
    status: str = "published",
    review_status: str = "approved",
    reviewed_by: str | None = "reviewer_01",
    evidence_role: str = "primary",
) -> int:
    """Create one rule and its evidence in one transaction for deferred triggers."""
    with engine.begin() as conn:
        rule_id = conn.execute(
            text("""
                INSERT INTO policy.eligibility_rule (
                    code, certificate_id, knowledge_point_id, qualification_level,
                    route_code, degree_level_code, major_category_code,
                    education_type_code, min_total_work_months,
                    min_relevant_work_months, admission_before, region_code,
                    valid_during, status, review_status, reviewed_by, reviewed_at
                )
                VALUES (
                    :code, :certificate_id, :knowledge_point_id, :qualification_level,
                    :route_code, :degree_level_code, :major_category_code,
                    :education_type_code, :min_total_work_months,
                    :min_relevant_work_months, :admission_before, :region_code,
                    daterange(:valid_from, :valid_to, '[)'), :status,
                    :review_status, :reviewed_by, now()
                )
                RETURNING id
            """),
            {
                "code": code,
                "certificate_id": certificate_id,
                "knowledge_point_id": knowledge_point_id,
                "qualification_level": qualification_level,
                "route_code": route_code,
                "degree_level_code": degree_level_code,
                "major_category_code": major_category_code,
                "education_type_code": education_type_code,
                "min_total_work_months": min_total_work_months,
                "min_relevant_work_months": min_relevant_work_months,
                "admission_before": admission_before,
                "region_code": region_code,
                "valid_from": valid_from,
                "valid_to": valid_to,
                "status": status,
                "review_status": review_status,
                "reviewed_by": reviewed_by,
            },
        ).scalar_one()
        conn.execute(
            text("""
                INSERT INTO policy.eligibility_rule_evidence (
                    eligibility_rule_id, clause_id, evidence_role
                )
                VALUES (:rule_id, :clause_id, :evidence_role)
            """),
            {"rule_id": rule_id, "clause_id": clause_id, "evidence_role": evidence_role},
        )
    return rule_id
