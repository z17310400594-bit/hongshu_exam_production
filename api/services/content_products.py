"""Content product service — WP08 MVP chapter lookup with ACL."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from api.auth import check_collection_access


def get_content_product_chapters(
    engine: Engine,
    *,
    product_code: str,
    principal_type: str,
    principal_code: str,
    version_no: int | None = None,
) -> dict[str, Any]:
    """Return one approved/published content product version with approved chapters and KPs."""
    version_filter = ""
    params: dict[str, Any] = {"product_code": product_code}
    if version_no is not None:
        version_filter = "AND pv.version_no = :version_no"
        params["version_no"] = version_no

    with engine.connect() as conn:
        version = conn.execute(
            text(f"""
                SELECT
                    p.id AS product_id,
                    p.code AS product_code,
                    p.title AS product_title,
                    p.product_type,
                    c.code AS certificate_code,
                    c.name AS certificate_name,
                    ou.code AS owner_org_code,
                    pv.id AS version_id,
                    pv.version_no,
                    pv.title AS version_title,
                    pv.summary,
                    pv.confidentiality,
                    pv.status AS version_status,
                    a.code AS source_asset_code,
                    a.title AS source_asset_title,
                    av.version_no AS source_asset_version_no,
                    kc.code AS collection_code
                  FROM content.product p
                  JOIN core.certificate c ON c.id = p.certificate_id
                  JOIN iam.organization_unit ou ON ou.id = p.owner_org_id
                  JOIN content.product_version pv ON pv.product_id = p.id
                  JOIN knowledge.asset_version av ON av.id = pv.source_asset_version_id
                  JOIN knowledge.asset a ON a.id = av.asset_id
                  JOIN knowledge.collection kc ON kc.id = a.collection_id
                 WHERE p.code = :product_code
                   AND p.status = 'active'
                   AND pv.status IN ('approved','published')
                   AND pv.review_status = 'approved'
                   {version_filter}
                 ORDER BY (pv.status = 'published') DESC, pv.version_no DESC
                 LIMIT 1
            """),
            params,
        ).fetchone()
        if version is None:
            raise ValueError("content product version not found")

    check_collection_access(
        engine,
        principal_type=principal_type,
        principal_code=principal_code,
        collection_code=version.collection_code,
        required_permission="read",
    )

    with engine.connect() as conn:
        chapter_rows = conn.execute(
            text("""
                SELECT
                    ch.id,
                    ch.chapter_code,
                    parent.chapter_code AS parent_chapter_code,
                    ch.title,
                    ch.body,
                    ch.sequence_no,
                    ch.confidentiality,
                    f.fragment_code AS source_fragment_code,
                    f.heading AS source_heading,
                    f.page_from,
                    f.page_to
                  FROM content.chapter ch
                  LEFT JOIN content.chapter parent ON parent.id = ch.parent_id
                  JOIN knowledge.fragment f ON f.id = ch.source_fragment_id
                 WHERE ch.product_version_id = :version_id
                   AND ch.status = 'published'
                   AND ch.review_status = 'approved'
                 ORDER BY ch.sequence_no, ch.chapter_code
            """),
            {"version_id": version.version_id},
        ).fetchall()
        kp_rows = conn.execute(
            text("""
                SELECT
                    ch.chapter_code,
                    kp.code AS kp_code,
                    kp.name AS kp_name,
                    ckp.teaching_role
                  FROM content.chapter_knowledge_point ckp
                  JOIN content.chapter ch ON ch.id = ckp.chapter_id
                  JOIN knowledge.knowledge_point kp ON kp.id = ckp.kp_id
                 WHERE ch.product_version_id = :version_id
                   AND ch.status = 'published'
                   AND ch.review_status = 'approved'
                   AND ckp.review_status = 'approved'
                 ORDER BY ch.sequence_no, ch.chapter_code, ckp.teaching_role, kp.code
            """),
            {"version_id": version.version_id},
        ).fetchall()

    kps_by_chapter: dict[str, list[dict[str, str]]] = {}
    for row in kp_rows:
        kps_by_chapter.setdefault(row.chapter_code, []).append(
            {
                "code": row.kp_code,
                "name": row.kp_name,
                "teachingRole": row.teaching_role,
            }
        )

    flat_chapters = [
        {
            "code": row.chapter_code,
            "parentCode": row.parent_chapter_code,
            "title": row.title,
            "body": row.body,
            "sequenceNo": row.sequence_no,
            "confidentiality": row.confidentiality,
            "sourceFragment": {
                "code": row.source_fragment_code,
                "heading": row.source_heading,
                "pageFrom": row.page_from,
                "pageTo": row.page_to,
            },
            "knowledgePoints": kps_by_chapter.get(row.chapter_code, []),
        }
        for row in chapter_rows
    ]

    return {
        "product": {
            "code": version.product_code,
            "title": version.product_title,
            "productType": version.product_type,
            "certificate": {
                "code": version.certificate_code,
                "name": version.certificate_name,
            },
            "ownerOrgCode": version.owner_org_code,
        },
        "selectedVersion": {
            "versionNo": version.version_no,
            "title": version.version_title,
            "summary": version.summary,
            "status": version.version_status,
            "confidentiality": version.confidentiality,
            "sourceAsset": {
                "code": version.source_asset_code,
                "title": version.source_asset_title,
                "versionNo": version.source_asset_version_no,
            },
        },
        "chapters": flat_chapters,
        "chapterTree": _build_chapter_tree(flat_chapters),
    }


def _build_chapter_tree(chapters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    nodes = [{**chapter, "children": []} for chapter in chapters]
    by_code = {node["code"]: node for node in nodes}
    roots: list[dict[str, Any]] = []
    for node in nodes:
        parent_code = node["parentCode"]
        if parent_code is None or parent_code not in by_code:
            roots.append(node)
        else:
            by_code[parent_code]["children"].append(node)
    return roots
