"""WP08 fixtures — content products, versions, chapters, and KP mappings."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine


def seed_source_asset(
    engine: Engine,
    *,
    asset_code: str,
    title: str = "WP08 Textbook Source",
    collection_code: str = "coll_internal",
    owner_org_code: str = "org_teaching_materials",
    asset_type: str = "textbook",
    confidentiality: str = "internal",
    version_no: int = 1,
    fragments: list[tuple[str, str, str, int]] | None = None,
) -> dict[str, Any]:
    fragments = fragments or [
        ("CH01", "chapter", "第一章 基础", 1),
        ("CH01_SEC01", "section", "第一节 报考条件", 2),
    ]
    with engine.begin() as conn:
        asset = conn.execute(
            text("""
                INSERT INTO knowledge.asset (
                    code, asset_type, title, collection_id, owner_org_id,
                    confidentiality, copyright_owner, allowed_use, status
                )
                SELECT :asset_code, :asset_type, :title, c.id, ou.id,
                       :confidentiality, '本公司', ARRAY['retrieval','generation']::text[], 'published'
                  FROM knowledge.collection c
                  JOIN iam.organization_unit ou ON ou.code = :owner_org_code
                 WHERE c.code = :collection_code
                RETURNING id, code, confidentiality
            """),
            {
                "asset_code": asset_code,
                "asset_type": asset_type,
                "title": title,
                "collection_code": collection_code,
                "owner_org_code": owner_org_code,
                "confidentiality": confidentiality,
            },
        ).fetchone()
        if asset is None:
            raise ValueError("asset dependencies not found")

        version = conn.execute(
            text("""
                INSERT INTO knowledge.asset_version (
                    asset_id, version_no, object_key, mime_type,
                    content_sha256, review_status, reviewed_by
                )
                VALUES (
                    :asset_id, :version_no, :object_key,
                    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    :sha, 'approved', 'wp08_reviewer'
                )
                RETURNING id, version_no
            """),
            {
                "asset_id": asset.id,
                "version_no": version_no,
                "object_key": f"wp08/{asset_code}/v{version_no}.docx",
                "sha": f"sha_wp08_{asset_code}_{version_no}",
            },
        ).fetchone()
        if version is None:
            raise RuntimeError("asset version insert failed")

        fragment_ids: dict[str, int] = {}
        for fragment_code, fragment_type, heading, sequence_no in fragments:
            fragment = conn.execute(
                text("""
                    INSERT INTO knowledge.fragment (
                        asset_version_id, fragment_code, fragment_type,
                        sequence_no, heading, content, page_from, page_to
                    )
                    VALUES (
                        :asset_version_id, :fragment_code, :fragment_type,
                        :sequence_no, :heading, :content, :page_from, :page_to
                    )
                    RETURNING id, fragment_code
                """),
                {
                    "asset_version_id": version.id,
                    "fragment_code": fragment_code,
                    "fragment_type": fragment_type,
                    "sequence_no": sequence_no,
                    "heading": heading,
                    "content": f"{heading} 的正文内容。",
                    "page_from": sequence_no,
                    "page_to": sequence_no,
                },
            ).fetchone()
            if fragment is None:
                raise RuntimeError("fragment insert failed")
            fragment_ids[fragment.fragment_code] = fragment.id

    return {
        "asset_id": asset.id,
        "asset_code": asset.code,
        "asset_version_id": version.id,
        "version_no": version.version_no,
        "fragment_ids": fragment_ids,
    }


def seed_content_product(
    engine: Engine,
    *,
    code: str,
    title: str = "WP08 一建教材",
    certificate_code: str = "c_constructor_1",
    product_type: str = "textbook",
    owner_org_code: str = "org_teaching_materials",
    status: str = "active",
) -> dict[str, Any]:
    with engine.begin() as conn:
        row = conn.execute(
            text("""
                INSERT INTO content.product (
                    code, certificate_id, product_type, title, owner_org_id, status
                )
                SELECT :code, cert.id, :product_type, :title, org.id, :status
                  FROM core.certificate cert
                  JOIN iam.organization_unit org ON org.code = :owner_org_code
                 WHERE cert.code = :certificate_code
                RETURNING id, code, certificate_id, product_type, title, owner_org_id, status
            """),
            {
                "code": code,
                "title": title,
                "certificate_code": certificate_code,
                "product_type": product_type,
                "owner_org_code": owner_org_code,
                "status": status,
            },
        ).fetchone()
    if row is None:
        raise ValueError("product dependencies not found")
    return dict(row._mapping)


def seed_product_version(
    engine: Engine,
    *,
    product_code: str,
    asset_code: str,
    version_no: int = 1,
    asset_version_no: int = 1,
    title: str = "WP08 一建教材 v1",
    summary: str | None = "MVP 教材版本",
    confidentiality: str = "internal",
    status: str = "approved",
    review_status: str = "approved",
    reviewed_by: str | None = "wp08_reviewer",
) -> dict[str, Any]:
    with engine.begin() as conn:
        row = conn.execute(
            text("""
                INSERT INTO content.product_version (
                    product_id, version_no, source_asset_version_id, title,
                    summary, confidentiality, status, review_status, reviewed_by
                )
                SELECT p.id, :version_no, av.id, :title,
                       :summary, :confidentiality, :status, :review_status, :reviewed_by
                  FROM content.product p
                  JOIN knowledge.asset a ON a.code = :asset_code
                  JOIN knowledge.asset_version av ON av.asset_id = a.id
                 WHERE p.code = :product_code
                   AND av.version_no = :asset_version_no
                RETURNING id, product_id, version_no, source_asset_version_id,
                          title, summary, confidentiality, status, review_status, reviewed_by
            """),
            {
                "product_code": product_code,
                "asset_code": asset_code,
                "version_no": version_no,
                "asset_version_no": asset_version_no,
                "title": title,
                "summary": summary,
                "confidentiality": confidentiality,
                "status": status,
                "review_status": review_status,
                "reviewed_by": reviewed_by,
            },
        ).fetchone()
    if row is None:
        raise ValueError("product version dependencies not found")
    return dict(row._mapping)


def seed_chapter(
    engine: Engine,
    *,
    product_version_id: int,
    source_fragment_id: int,
    chapter_code: str,
    title: str,
    parent_id: int | None = None,
    body: str | None = None,
    sequence_no: int = 1,
    confidentiality: str = "internal",
    review_status: str = "approved",
    status: str = "published",
) -> dict[str, Any]:
    with engine.begin() as conn:
        row = conn.execute(
            text("""
                INSERT INTO content.chapter (
                    product_version_id, parent_id, source_fragment_id,
                    chapter_code, title, body, sequence_no,
                    confidentiality, review_status, status
                )
                VALUES (
                    :product_version_id, :parent_id, :source_fragment_id,
                    :chapter_code, :title, :body, :sequence_no,
                    :confidentiality, :review_status, :status
                )
                RETURNING id, product_version_id, parent_id, source_fragment_id,
                          chapter_code, title, body, sequence_no,
                          confidentiality, review_status, status
            """),
            {
                "product_version_id": product_version_id,
                "parent_id": parent_id,
                "source_fragment_id": source_fragment_id,
                "chapter_code": chapter_code,
                "title": title,
                "body": body,
                "sequence_no": sequence_no,
                "confidentiality": confidentiality,
                "review_status": review_status,
                "status": status,
            },
        ).fetchone()
    if row is None:
        raise RuntimeError("chapter insert failed")
    return dict(row._mapping)


def seed_knowledge_point(engine: Engine, *, code: str = "WP08_KP", name: str = "WP08 知识点") -> dict[str, Any]:
    with engine.begin() as conn:
        row = conn.execute(
            text("""
                INSERT INTO knowledge.knowledge_point (
                    code, name, domain_code, cognitive_level, description, status
                )
                VALUES (:code, :name, 'construction', 'understand', :description, 'active')
                RETURNING id, code, name
            """),
            {"code": code, "name": name, "description": f"{name} 描述"},
        ).fetchone()
    if row is None:
        raise RuntimeError("knowledge point insert failed")
    return dict(row._mapping)


def seed_chapter_knowledge_point(
    engine: Engine,
    *,
    chapter_id: int,
    kp_code: str,
    teaching_role: str = "core",
    review_status: str = "approved",
    reviewed_by: str | None = "wp08_reviewer",
) -> dict[str, Any]:
    with engine.begin() as conn:
        row = conn.execute(
            text("""
                INSERT INTO content.chapter_knowledge_point (
                    chapter_id, kp_id, teaching_role, review_status, reviewed_by
                )
                SELECT :chapter_id, kp.id, :teaching_role, :review_status, :reviewed_by
                  FROM knowledge.knowledge_point kp
                 WHERE kp.code = :kp_code
                RETURNING chapter_id, kp_id, teaching_role, review_status, reviewed_by
            """),
            {
                "chapter_id": chapter_id,
                "kp_code": kp_code,
                "teaching_role": teaching_role,
                "review_status": review_status,
                "reviewed_by": reviewed_by,
            },
        ).fetchone()
    if row is None:
        raise ValueError("knowledge point not found")
    return dict(row._mapping)
