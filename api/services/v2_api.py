"""V2 MVP query API service layer.

WP12 intentionally keeps this as a thin aggregation layer over existing V2
knowledge-platform tables and WP06/WP07 services.  It exposes stable API shapes
without expanding into generation orchestration or production search ranking.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Engine

from api.auth import check_collection_access
from api.services.eligibility import evaluate_eligibility
from api.services.exam_events import get_exam_events


def list_certificates(
    engine: Engine,
    *,
    query: str | None = None,
    cursor: str | None = None,
    limit: int = 20,
    as_of: date | None = None,
) -> dict[str, Any]:
    """Return active certificates with aliases and the next exam summary."""
    offset = _decode_offset_cursor(cursor)
    params: dict[str, Any] = {"limit": limit + 1, "offset": offset}
    filter_sql = "c.status = 'active'"
    if query:
        params["query_like"] = f"%{query.lower()}%"
        filter_sql += """
            AND (
                lower(c.code) LIKE :query_like
                OR lower(c.name) LIKE :query_like
                OR EXISTS (
                    SELECT 1
                      FROM core.certificate_alias ca
                     WHERE ca.certificate_id = c.id
                       AND lower(ca.alias) LIKE :query_like
                )
            )
        """

    with engine.connect() as conn:
        rows = conn.execute(
            text(f"""
                SELECT c.id, c.code, c.name, c.category_code, c.issuing_authority, c.nationwide
                  FROM core.certificate c
                 WHERE {filter_sql}
                 ORDER BY
                    CASE WHEN left(c.code, 2) = 'c_' THEN 1 ELSE 0 END,
                    c.code
                  LIMIT :limit OFFSET :offset
            """),
            params,
        ).fetchall()

        visible_rows = rows[:limit]
        cert_ids = [row.id for row in visible_rows]
        aliases_by_cert: dict[int, list[str]] = {cert_id: [] for cert_id in cert_ids}
        if cert_ids:
            alias_rows = conn.execute(
                text("""
                    SELECT certificate_id, alias
                      FROM core.certificate_alias
                     WHERE certificate_id IN :cert_ids
                     ORDER BY alias_type, alias
                """).bindparams(bindparam("cert_ids", expanding=True)),
                {"cert_ids": tuple(cert_ids)},
            ).fetchall()
            for row in alias_rows:
                aliases = aliases_by_cert[row.certificate_id]
                if row.alias not in aliases:
                    aliases.append(row.alias)

    items = []
    for row in visible_rows:
        event_summary = _next_exam_summary(engine, certificate_code=row.code, as_of=as_of)
        items.append(
            {
                "code": row.code,
                "name": row.name,
                "categoryCode": row.category_code,
                "issuingAuthority": row.issuing_authority,
                "nationwide": row.nationwide,
                "aliases": aliases_by_cert[row.id],
                "nextExam": event_summary,
            }
        )

    next_cursor = str(offset + limit) if len(rows) > limit else None
    return {"items": items, "nextCursor": next_cursor}


def get_certificate_detail(
    engine: Engine,
    *,
    certificate_code: str,
    as_of: date | None = None,
) -> dict[str, Any]:
    """Return one active certificate with aliases and next exam summary."""
    with engine.connect() as conn:
        cert = conn.execute(
            text("""
                SELECT id, code, name, category_code, issuing_authority, exam_authority, nationwide, status
                  FROM core.certificate
                 WHERE code = :code
                   AND status = 'active'
            """),
            {"code": certificate_code},
        ).fetchone()
        if cert is None:
            raise ValueError("certificate not found")
        alias_rows = conn.execute(
            text("""
                SELECT alias
                  FROM core.certificate_alias
                 WHERE certificate_id = :certificate_id
                 ORDER BY alias_type, alias
            """),
            {"certificate_id": cert.id},
        ).scalars().all()
        aliases: list[str] = []
        for alias in alias_rows:
            if alias not in aliases:
                aliases.append(alias)

    return {
        "code": cert.code,
        "name": cert.name,
        "categoryCode": cert.category_code,
        "issuingAuthority": cert.issuing_authority,
        "examAuthority": cert.exam_authority,
        "nationwide": cert.nationwide,
        "status": cert.status,
        "aliases": aliases,
        "nextExam": _next_exam_summary(engine, certificate_code=certificate_code, as_of=as_of),
    }


def get_certificate_exam_events_v2(
    engine: Engine,
    *,
    certificate_code: str,
    region_code: str = "CN",
    exam_year: int | None = None,
    as_of: date | None = None,
) -> dict[str, Any]:
    """Return exam events using the WP07 schedule service with V2 field names."""
    result = get_exam_events(
        engine,
        certificate_code=certificate_code,
        region_code=region_code,
        exam_year=exam_year,
        as_of=as_of,
    )
    certificate = result["certificate"]
    return {
        "certificate": {
            "code": certificate["code"],
            "name": certificate["name"],
            "categoryCode": certificate.get("category_code"),
        },
        "selectedEvent": result["selectedEvent"],
        "events": result["events"],
    }


def evaluate_eligibility_v2(
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
    """Evaluate eligibility and shape it as the public V2 contract."""
    result = evaluate_eligibility(
        engine,
        certificate_code=certificate_code,
        principal_type=principal_type,
        principal_code=principal_code,
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
    if result["status"] == "insufficient_data":
        return {
            "decision": "insufficient_data",
            "certificateCode": certificate_code,
            "reason": result["reason"],
            "matchedRuleCode": None,
            "requirements": [],
            "citations": [],
            "reviewedAt": None,
        }

    matched_rule = result["matchedRules"][0]
    return {
        "decision": "eligible",
        "certificateCode": certificate_code,
        "reason": result["reason"],
        "matchedRuleCode": matched_rule["code"],
        "requirements": _requirements_for_rule(
            matched_rule,
            total_work_months=total_work_months,
            relevant_work_months=relevant_work_months,
            admission_date=admission_date,
        ),
        "citations": [_citation_for_evidence(item) for item in matched_rule["primaryEvidence"]],
        "reviewedAt": None,
    }


def search_knowledge(
    engine: Engine,
    *,
    principal_type: str,
    principal_code: str,
    query: str,
    collection_codes: list[str] | None = None,
    knowledge_point_codes: list[str] | None = None,
    asset_types: list[str] | None = None,
    top_k: int = 8,
    as_of: date | None = None,
) -> dict[str, Any]:
    """Search approved, ACL-readable fragments with MVP text matching."""
    requested_collections = [code for code in (collection_codes or []) if code]
    for code in requested_collections:
        check_collection_access(
            engine,
            principal_type=principal_type,
            principal_code=principal_code,
            collection_code=code,
            required_permission="read",
        )

    params: dict[str, Any] = {
        "principal_type": principal_type,
        "principal_code": principal_code,
        "query": query,
        "query_like": f"%{query.lower()}%",
        "top_k": top_k,
        "as_of": as_of or date.today(),
    }
    filters = [
        "c.status = 'active'",
        "a.status = 'published'",
        "av.review_status = 'approved'",
        "fkp.review_status = 'approved'",
        "(av.valid_during IS NULL OR av.valid_during @> CAST(:as_of AS date))",
        """
        (
            :query = ''
            OR lower(f.content) LIKE :query_like
            OR lower(coalesce(f.heading, '')) LIKE :query_like
            OR f.search_tsv @@ plainto_tsquery('simple', :query)
        )
        """,
    ]
    bindparams = []
    if requested_collections:
        params["collection_codes"] = tuple(requested_collections)
        filters.append("c.code IN :collection_codes")
        bindparams.append(bindparam("collection_codes", expanding=True))
    if knowledge_point_codes:
        params["knowledge_point_codes"] = tuple(knowledge_point_codes)
        filters.append("kp.code IN :knowledge_point_codes")
        bindparams.append(bindparam("knowledge_point_codes", expanding=True))
    if asset_types:
        params["asset_types"] = tuple(asset_types)
        filters.append("a.asset_type IN :asset_types")
        bindparams.append(bindparam("asset_types", expanding=True))

    statement = text(f"""
        SELECT
            f.fragment_code,
            f.heading,
            f.content,
            f.page_from,
            f.page_to,
            max(fkp.confidence) AS confidence,
            a.code AS asset_code,
            a.title AS asset_title,
            a.asset_type,
            av.version_no,
            c.code AS collection_code,
            array_agg(DISTINCT kp.code ORDER BY kp.code) AS knowledge_point_codes
          FROM knowledge.fragment f
          JOIN knowledge.asset_version av ON av.id = f.asset_version_id
          JOIN knowledge.asset a ON a.id = av.asset_id
          JOIN knowledge.collection c ON c.id = a.collection_id
          JOIN knowledge.collection_acl acl ON acl.collection_id = c.id
          JOIN knowledge.fragment_knowledge_point fkp ON fkp.fragment_id = f.id
          JOIN knowledge.knowledge_point kp ON kp.id = fkp.kp_id
         WHERE acl.principal_type = :principal_type
           AND acl.principal_code = :principal_code
           AND acl.permission = 'read'
           AND {" AND ".join(filters)}
         GROUP BY
            f.id, f.fragment_code, f.heading, f.content, f.page_from, f.page_to,
            a.code, a.title, a.asset_type, av.version_no, c.code
         ORDER BY
            CASE
                WHEN lower(f.content) LIKE :query_like THEN 0
                WHEN lower(coalesce(f.heading, '')) LIKE :query_like THEN 1
                ELSE 2
            END,
            max(fkp.confidence) DESC,
            a.code,
            f.fragment_code
         LIMIT :top_k
    """)
    if bindparams:
        statement = statement.bindparams(*bindparams)

    with engine.connect() as conn:
        rows = conn.execute(statement, params).fetchall()

    return {
        "query": query,
        "items": [
            {
                "assetCode": row.asset_code,
                "assetTitle": row.asset_title,
                "assetType": row.asset_type,
                "versionNo": row.version_no,
                "fragmentCode": row.fragment_code,
                "heading": row.heading,
                "content": row.content,
                "pageFrom": row.page_from,
                "pageTo": row.page_to,
                "collectionCode": row.collection_code,
                "knowledgePointCodes": list(row.knowledge_point_codes),
                "score": float(row.confidence),
            }
            for row in rows
        ],
        "nextCursor": None,
    }


def _decode_offset_cursor(cursor: str | None) -> int:
    if cursor is None or cursor == "":
        return 0
    try:
        offset = int(cursor)
    except ValueError as exc:
        raise ValueError("invalid cursor") from exc
    if offset < 0:
        raise ValueError("invalid cursor")
    return offset


def _next_exam_summary(engine: Engine, *, certificate_code: str, as_of: date | None) -> dict[str, Any] | None:
    try:
        result = get_exam_events(engine, certificate_code=certificate_code, as_of=as_of)
    except ValueError:
        return None
    selected = result["selectedEvent"]
    if selected is None:
        return None
    return {
        "eventCode": selected["code"],
        "examYear": selected["examYear"],
        "regionCode": selected["regionCode"],
        "phases": [
            {
                "type": phase["phaseType"],
                "startsOn": phase["startsOn"],
                "endsOn": phase["endsOn"],
            }
            for phase in selected["phases"]
        ],
    }


def _requirements_for_rule(
    rule: dict[str, Any],
    *,
    total_work_months: int | None,
    relevant_work_months: int | None,
    admission_date: date | None,
) -> list[dict[str, Any]]:
    requirements = [
        {
            "field": "totalWorkMonths",
            "required": rule["minTotalWorkMonths"],
            "actual": total_work_months,
            "passed": total_work_months is not None and total_work_months >= rule["minTotalWorkMonths"],
        },
        {
            "field": "relevantWorkMonths",
            "required": rule["minRelevantWorkMonths"],
            "actual": relevant_work_months,
            "passed": relevant_work_months is not None and relevant_work_months >= rule["minRelevantWorkMonths"],
        },
    ]
    if rule["routeCode"] == "grandfathered":
        requirements.append(
            {
                "field": "admissionDate",
                "required": f"before {rule['admissionBefore']}",
                "actual": admission_date.isoformat() if admission_date else None,
                "passed": admission_date is not None and admission_date.isoformat() < rule["admissionBefore"],
            }
        )
    return requirements


def _citation_for_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "assetCode": evidence["documentCode"],
        "versionNo": evidence["versionNo"],
        "fragmentCode": evidence["fragmentCode"],
        "title": evidence["documentCode"],
        "section": evidence["clauseCode"],
        "quote": evidence["summary"],
    }
