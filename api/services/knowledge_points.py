"""Knowledge point service — minimal MVP graph and approved fragment lookup."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.engine import Engine

ASSET_TYPE_SCOPES = {"policy", "textbook", "handout", "private", "paper", "manual"}


def _lookup_id(engine: Engine, sql: str, params: dict) -> int | None:
    with engine.connect() as conn:
        row = conn.execute(text(sql), params).fetchone()
    return None if row is None else row.id


def _knowledge_point_id(engine: Engine, code: str) -> int | None:
    return _lookup_id(
        engine,
        "SELECT id FROM knowledge.knowledge_point WHERE code = :code",
        {"code": code},
    )


def create_knowledge_point(
    engine: Engine,
    *,
    code: str,
    name: str,
    domain_code: str,
    parent_code: str | None = None,
    cognitive_level: str | None = None,
    description: str | None = None,
    status: str = "active",
    merged_into_code: str | None = None,
) -> dict:
    """Create a canonical knowledge point, preserving code history for merges."""
    parent_id = _knowledge_point_id(engine, parent_code) if parent_code is not None else None
    if parent_code is not None and parent_id is None:
        raise ValueError("parent knowledge point not found")

    merged_into_kp_id = _knowledge_point_id(engine, merged_into_code) if merged_into_code is not None else None
    if merged_into_code is not None and merged_into_kp_id is None:
        raise ValueError("merged target knowledge point not found")

    with engine.begin() as conn:
        row = conn.execute(
            text("""
                INSERT INTO knowledge.knowledge_point (
                    code, name, parent_id, domain_code, cognitive_level,
                    description, status, merged_into_kp_id
                )
                VALUES (
                    :code, :name, :parent_id, :domain_code, :cognitive_level,
                    :description, :status, :merged_into_kp_id
                )
                RETURNING id, code, name, parent_id, domain_code, cognitive_level,
                          description, status, merged_into_kp_id
            """),
            {
                "code": code,
                "name": name,
                "parent_id": parent_id,
                "domain_code": domain_code,
                "cognitive_level": cognitive_level,
                "description": description,
                "status": status,
                "merged_into_kp_id": merged_into_kp_id,
            },
        ).fetchone()
    if row is None:
        raise RuntimeError("knowledge point insert failed")
    return dict(row._mapping)


def create_knowledge_point_relation(
    engine: Engine,
    *,
    from_code: str,
    to_code: str,
    relation_type: str,
) -> dict:
    """Create a lightweight relation between two knowledge points."""
    from_kp_id = _knowledge_point_id(engine, from_code)
    to_kp_id = _knowledge_point_id(engine, to_code)
    if from_kp_id is None or to_kp_id is None:
        raise ValueError("knowledge point relation endpoints must exist")

    with engine.begin() as conn:
        row = conn.execute(
            text("""
                INSERT INTO knowledge.knowledge_point_relation (
                    from_kp_id, to_kp_id, relation_type
                )
                VALUES (:from_kp_id, :to_kp_id, :relation_type)
                RETURNING from_kp_id, to_kp_id, relation_type
            """),
            {
                "from_kp_id": from_kp_id,
                "to_kp_id": to_kp_id,
                "relation_type": relation_type,
            },
        ).fetchone()
    if row is None:
        raise RuntimeError("knowledge point relation insert failed")
    return dict(row._mapping)


def add_knowledge_point_scope(
    engine: Engine,
    *,
    kp_code: str,
    scope_type: str,
    scope_code: str,
) -> dict:
    """Attach a reusable knowledge point to a certificate, subject, curriculum, or asset type."""
    kp_id = _knowledge_point_id(engine, kp_code)
    if kp_id is None:
        raise ValueError("knowledge point not found")

    if scope_type == "certificate":
        exists = _lookup_id(engine, "SELECT id FROM core.certificate WHERE code = :code", {"code": scope_code})
        if exists is None:
            raise ValueError("certificate scope not found")
    elif scope_type == "exam_subject":
        exists = _lookup_id(engine, "SELECT id FROM core.exam_subject WHERE code = :code", {"code": scope_code})
        if exists is None:
            raise ValueError("exam subject scope not found")
    elif scope_type == "asset_type" and scope_code not in ASSET_TYPE_SCOPES:
        raise ValueError("asset type scope not supported")

    with engine.begin() as conn:
        row = conn.execute(
            text("""
                INSERT INTO knowledge.knowledge_point_scope (kp_id, scope_type, scope_code)
                VALUES (:kp_id, :scope_type, :scope_code)
                RETURNING id, kp_id, scope_type, scope_code
            """),
            {"kp_id": kp_id, "scope_type": scope_type, "scope_code": scope_code},
        ).fetchone()
    if row is None:
        raise RuntimeError("knowledge point scope insert failed")
    return dict(row._mapping)


def map_fragment_to_knowledge_point(
    engine: Engine,
    *,
    asset_code: str,
    version_no: int,
    fragment_code: str,
    kp_code: str,
    relation_role: str,
    confidence: Decimal | float | str = Decimal("1"),
    review_status: str = "pending",
    reviewed_by: str | None = None,
) -> dict:
    """Map an asset fragment to a knowledge point.

    Machine-generated mappings should use the default `pending` status.  The
    database enforces that approved mappings always record a reviewer.
    """
    kp_id = _knowledge_point_id(engine, kp_code)
    if kp_id is None:
        raise ValueError("knowledge point not found")

    with engine.begin() as conn:
        row = conn.execute(
            text("""
                WITH fragment_ref AS (
                    SELECT f.id
                      FROM knowledge.fragment f
                      JOIN knowledge.asset_version av ON av.id = f.asset_version_id
                      JOIN knowledge.asset a ON a.id = av.asset_id
                     WHERE a.code = :asset_code
                       AND av.version_no = :version_no
                       AND f.fragment_code = :fragment_code
                )
                INSERT INTO knowledge.fragment_knowledge_point (
                    fragment_id, kp_id, relation_role, confidence,
                    review_status, reviewed_by
                )
                SELECT id, :kp_id, :relation_role, :confidence,
                       :review_status, :reviewed_by
                  FROM fragment_ref
                RETURNING fragment_id, kp_id, relation_role, confidence,
                          review_status, reviewed_by
            """),
            {
                "asset_code": asset_code,
                "version_no": version_no,
                "fragment_code": fragment_code,
                "kp_id": kp_id,
                "relation_role": relation_role,
                "confidence": Decimal(str(confidence)),
                "review_status": review_status,
                "reviewed_by": reviewed_by,
            },
        ).fetchone()
    if row is None:
        raise ValueError("fragment not found")
    return dict(row._mapping)


def list_approved_fragments_for_knowledge_point(
    engine: Engine,
    *,
    kp_code: str,
    principal_type: str,
    principal_code: str,
    limit: int = 20,
) -> dict:
    """Return only approved, ACL-readable fragments for one knowledge point."""
    with engine.connect() as conn:
        kp = conn.execute(
            text("""
                SELECT id, code, name, domain_code, status
                  FROM knowledge.knowledge_point
                 WHERE code = :kp_code
            """),
            {"kp_code": kp_code},
        ).fetchone()
        if kp is None:
            raise ValueError("knowledge point not found")

        rows = conn.execute(
            text("""
                SELECT
                    f.fragment_code,
                    f.heading,
                    f.content,
                    f.page_from,
                    f.page_to,
                    fkp.relation_role,
                    fkp.confidence,
                    a.code AS asset_code,
                    a.title AS asset_title,
                    av.version_no
                  FROM knowledge.fragment_knowledge_point fkp
                  JOIN knowledge.fragment f ON f.id = fkp.fragment_id
                  JOIN knowledge.asset_version av ON av.id = f.asset_version_id
                  JOIN knowledge.asset a ON a.id = av.asset_id
                  JOIN knowledge.collection c ON c.id = a.collection_id
                  JOIN knowledge.collection_acl acl ON acl.collection_id = c.id
                 WHERE fkp.kp_id = :kp_id
                   AND fkp.review_status = 'approved'
                   AND acl.principal_type = :principal_type
                   AND acl.principal_code = :principal_code
                   AND acl.permission = 'read'
                 ORDER BY fkp.confidence DESC, a.code, av.version_no, f.sequence_no, f.fragment_code
                 LIMIT :limit
            """),
            {
                "kp_id": kp.id,
                "principal_type": principal_type,
                "principal_code": principal_code,
                "limit": limit,
            },
        ).fetchall()

    return {
        "knowledgePoint": dict(kp._mapping),
        "fragments": [dict(row._mapping) for row in rows],
    }
