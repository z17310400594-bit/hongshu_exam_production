"""Generation audit service — WP10 MVP run/citation/output lookup."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from api.auth import check_collection_access


def get_generation_run_audit(
    engine: Engine,
    *,
    run_id: int,
    principal_type: str,
    principal_code: str,
) -> dict[str, Any]:
    """Return one generation run with citations and outputs after citation ACL checks."""
    with engine.connect() as conn:
        run = conn.execute(
            text("""
                SELECT
                    id,
                    application_code,
                    user_code,
                    model_provider,
                    model_name,
                    model_route,
                    prompt_version,
                    confidentiality,
                    status,
                    created_at
                  FROM generation.run
                 WHERE id = :run_id
            """),
            {"run_id": run_id},
        ).fetchone()
        if run is None:
            raise ValueError("generation run not found")

        citation_rows = conn.execute(
            text("""
                SELECT
                    c.citation_order,
                    c.usage_type,
                    f.fragment_code,
                    f.heading,
                    f.page_from,
                    f.page_to,
                    a.code AS asset_code,
                    a.title AS asset_title,
                    a.confidentiality AS asset_confidentiality,
                    av.version_no AS asset_version_no,
                    kc.code AS collection_code
                  FROM generation.citation c
                  JOIN knowledge.fragment f ON f.id = c.fragment_id
                  JOIN knowledge.asset_version av ON av.id = f.asset_version_id
                  JOIN knowledge.asset a ON a.id = av.asset_id
                  JOIN knowledge.collection kc ON kc.id = a.collection_id
                 WHERE c.generation_run_id = :run_id
                 ORDER BY c.citation_order
            """),
            {"run_id": run_id},
        ).fetchall()

        output_rows = conn.execute(
            text("""
                SELECT
                    id,
                    output_type,
                    content,
                    confidentiality,
                    status,
                    approved_by,
                    approved_at,
                    created_at
                  FROM generation.output
                 WHERE generation_run_id = :run_id
                 ORDER BY id
            """),
            {"run_id": run_id},
        ).fetchall()

    for row in citation_rows:
        check_collection_access(
            engine,
            principal_type=principal_type,
            principal_code=principal_code,
            collection_code=row.collection_code,
            required_permission="read",
        )

    return {
        "run": {
            "id": run.id,
            "applicationCode": run.application_code,
            "userCode": run.user_code,
            "modelProvider": run.model_provider,
            "modelName": run.model_name,
            "modelRoute": run.model_route,
            "promptVersion": run.prompt_version,
            "confidentiality": run.confidentiality,
            "status": run.status,
            "createdAt": run.created_at.isoformat(),
        },
        "citations": [
            {
                "order": row.citation_order,
                "usageType": row.usage_type,
                "fragment": {
                    "code": row.fragment_code,
                    "heading": row.heading,
                    "pageFrom": row.page_from,
                    "pageTo": row.page_to,
                },
                "asset": {
                    "code": row.asset_code,
                    "title": row.asset_title,
                    "versionNo": row.asset_version_no,
                    "confidentiality": row.asset_confidentiality,
                },
            }
            for row in citation_rows
        ],
        "outputs": [
            {
                "id": row.id,
                "outputType": row.output_type,
                "content": row.content,
                "confidentiality": row.confidentiality,
                "status": row.status,
                "approvedBy": row.approved_by,
                "approvedAt": row.approved_at.isoformat() if row.approved_at else None,
                "createdAt": row.created_at.isoformat(),
            }
            for row in output_rows
        ],
    }
