"""Eligibility evaluation service — WP06 policy rules MVP."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from api.auth import AuthorizationError


def _certificate_id(engine: Engine, certificate_code: str) -> int | None:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id FROM core.certificate WHERE code = :code AND status = 'active'"),
            {"code": certificate_code},
        ).fetchone()
    return None if row is None else row.id


def _base_params(
    *,
    certificate_id: int,
    as_of: date,
    region_code: str,
    qualification_level: str | None,
    degree_level_code: str | None,
    major_category_code: str | None,
    education_type_code: str | None,
    total_work_months: int | None,
    relevant_work_months: int | None,
    admission_date: date | None,
) -> dict[str, Any]:
    return {
        "certificate_id": certificate_id,
        "as_of": as_of,
        "region_code": region_code,
        "qualification_level": qualification_level,
        "degree_level_code": degree_level_code,
        "major_category_code": major_category_code,
        "education_type_code": education_type_code,
        "total_work_months": -1 if total_work_months is None else total_work_months,
        "relevant_work_months": -1 if relevant_work_months is None else relevant_work_months,
        "admission_date": admission_date,
    }


_RULE_FILTER_SQL = """
    r.certificate_id = :certificate_id
    AND r.status = 'published'
    AND r.review_status = 'approved'
    AND r.valid_during @> CAST(:as_of AS date)
    AND r.region_code IN ('CN', :region_code)
    AND (r.qualification_level IS NULL OR r.qualification_level = :qualification_level)
    AND (r.degree_level_code IS NULL OR r.degree_level_code = 'any' OR r.degree_level_code = :degree_level_code)
    AND (r.major_category_code IS NULL OR r.major_category_code = 'any' OR r.major_category_code = :major_category_code)
    AND (r.education_type_code IS NULL OR r.education_type_code = 'any' OR r.education_type_code = :education_type_code)
    AND :total_work_months >= r.min_total_work_months
    AND :relevant_work_months >= r.min_relevant_work_months
    AND (
        r.route_code <> 'grandfathered'
        OR (
            CAST(:admission_date AS date) IS NOT NULL
            AND r.admission_before IS NOT NULL
            AND CAST(:admission_date AS date) < r.admission_before
        )
    )
    AND EXISTS (
        SELECT 1
          FROM policy.eligibility_rule_evidence ev
          JOIN policy.clause pc ON pc.id = ev.clause_id
          JOIN policy.document_version pdv ON pdv.id = pc.document_version_id
         WHERE ev.eligibility_rule_id = r.id
           AND ev.evidence_role = 'primary'
           AND pdv.status = 'published'
           AND pdv.valid_during @> CAST(:as_of AS date)
    )
"""


def _hidden_candidate_count(engine: Engine, params: dict[str, Any]) -> int:
    with engine.connect() as conn:
        return int(
            conn.execute(
                text(f"""
                    SELECT count(DISTINCT r.id)
                      FROM policy.eligibility_rule r
                     WHERE {_RULE_FILTER_SQL}
                """),
                params,
            ).scalar_one()
        )


def evaluate_eligibility(
    engine: Engine,
    *,
    certificate_code: str,
    principal_type: str,
    principal_code: str,
    as_of: date,
    region_code: str = "CN",
    qualification_level: str | None = None,
    degree_level_code: str | None = None,
    major_category_code: str | None = None,
    education_type_code: str | None = None,
    total_work_months: int | None = None,
    relevant_work_months: int | None = None,
    admission_date: date | None = None,
) -> dict[str, Any]:
    """Evaluate applicant facts against approved, readable policy rules.

    This MVP intentionally returns `insufficient_data` instead of guessing when
    no approved rule can be matched.  Unauthorized callers receive a generic
    403 when matching policy facts exist but are not ACL-readable.
    """
    certificate_id = _certificate_id(engine, certificate_code)
    if certificate_id is None:
        raise ValueError("certificate not found")

    params = _base_params(
        certificate_id=certificate_id,
        as_of=as_of,
        region_code=region_code,
        qualification_level=qualification_level,
        degree_level_code=degree_level_code,
        major_category_code=major_category_code,
        education_type_code=education_type_code,
        total_work_months=total_work_months,
        relevant_work_months=relevant_work_months,
        admission_date=admission_date,
    )
    params.update({"principal_type": principal_type, "principal_code": principal_code})

    with engine.connect() as conn:
        rows = conn.execute(
            text(f"""
                SELECT
                    r.id AS rule_id,
                    r.code AS rule_code,
                    r.qualification_level,
                    r.route_code,
                    r.degree_level_code,
                    r.major_category_code,
                    r.education_type_code,
                    r.min_total_work_months,
                    r.min_relevant_work_months,
                    r.admission_before,
                    r.region_code,
                    kp.code AS knowledge_point_code,
                    kp.name AS knowledge_point_name,
                    pc.clause_code,
                    pc.summary AS clause_summary,
                    pd.document_code,
                    pdv.version_no AS document_version_no,
                    f.fragment_code
                  FROM policy.eligibility_rule r
                  JOIN knowledge.knowledge_point kp ON kp.id = r.knowledge_point_id
                  JOIN policy.eligibility_rule_evidence ev ON ev.eligibility_rule_id = r.id
                  JOIN policy.clause pc ON pc.id = ev.clause_id
                  JOIN policy.document_version pdv ON pdv.id = pc.document_version_id
                  JOIN policy.document pd ON pd.id = pdv.document_id
                  JOIN knowledge.fragment f ON f.id = pc.fragment_id
                  JOIN knowledge.asset_version av ON av.id = f.asset_version_id
                  JOIN knowledge.asset a ON a.id = av.asset_id
                  JOIN knowledge.collection c ON c.id = a.collection_id
                  JOIN knowledge.collection_acl acl ON acl.collection_id = c.id
                 WHERE {_RULE_FILTER_SQL}
                   AND ev.evidence_role = 'primary'
                   AND acl.principal_type = :principal_type
                   AND acl.principal_code = :principal_code
                   AND acl.permission = 'read'
                 ORDER BY
                   CASE WHEN r.region_code = :region_code THEN 0 ELSE 1 END,
                   CASE r.route_code
                       WHEN 'normal' THEN 0
                       WHEN 'grandfathered' THEN 1
                       WHEN 'title_substitute' THEN 2
                       ELSE 3
                   END,
                   r.min_relevant_work_months DESC,
                   r.min_total_work_months DESC,
                   r.code,
                   pc.clause_code
            """),
            params,
        ).fetchall()

    if not rows:
        hidden_count = _hidden_candidate_count(engine, params)
        if hidden_count > 0:
            raise AuthorizationError(status_code=403, detail="Access denied")
        return {
            "status": "insufficient_data",
            "certificateCode": certificate_code,
            "reason": "No approved readable rule matched the supplied facts",
            "matchedRules": [],
        }

    rules: dict[int, dict[str, Any]] = {}
    for row in rows:
        data = dict(row._mapping)
        rule = rules.setdefault(
            data["rule_id"],
            {
                "code": data["rule_code"],
                "qualificationLevel": data["qualification_level"],
                "routeCode": data["route_code"],
                "degreeLevelCode": data["degree_level_code"],
                "majorCategoryCode": data["major_category_code"],
                "educationTypeCode": data["education_type_code"],
                "minTotalWorkMonths": data["min_total_work_months"],
                "minRelevantWorkMonths": data["min_relevant_work_months"],
                "admissionBefore": data["admission_before"].isoformat() if data["admission_before"] else None,
                "regionCode": data["region_code"],
                "knowledgePoint": {
                    "code": data["knowledge_point_code"],
                    "name": data["knowledge_point_name"],
                },
                "primaryEvidence": [],
            },
        )
        rule["primaryEvidence"].append(
            {
                "documentCode": data["document_code"],
                "versionNo": data["document_version_no"],
                "clauseCode": data["clause_code"],
                "summary": data["clause_summary"],
                "fragmentCode": data["fragment_code"],
            }
        )

    return {
        "status": "eligible",
        "certificateCode": certificate_code,
        "reason": "Matched approved readable policy rule",
        "matchedRules": list(rules.values()),
    }
