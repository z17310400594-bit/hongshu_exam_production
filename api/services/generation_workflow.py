"""Generation workflow service — WP14 MVP backendized generation.

This is deliberately small: it creates an auditable generation run, gathers
approved ACL-readable citations, stores a draft output, and returns a card set.
The actual long-running Dify/SSE orchestration remains deferred; the browser no
longer talks to Dify or holds a model key.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Engine

from api.auth import check_collection_access
from api.config import settings

CONFIDENTIALITY_RANK = {
    "public": 0,
    "internal": 1,
    "confidential": 2,
    "restricted": 3,
}


def create_generation(
    engine: Engine,
    *,
    principal_type: str,
    principal_code: str,
    application_code: str,
    output_type: str,
    certificate_code: str | None,
    collection_codes: list[str],
    knowledge_point_codes: list[str],
    inputs: dict[str, Any],
    idempotency_key: str | None = None,
    card_sequence: list[str] | None = None,
) -> dict[str, Any]:
    """Create one synchronous MVP generation run with citations and output."""
    _ = certificate_code
    requested_collections = [code for code in collection_codes if code]
    for code in requested_collections:
        check_collection_access(
            engine,
            principal_type=principal_type,
            principal_code=principal_code,
            collection_code=code,
            required_permission="read",
        )

    citations = _select_generation_citations(
        engine,
        principal_type=principal_type,
        principal_code=principal_code,
        collection_codes=requested_collections,
        knowledge_point_codes=[code for code in knowledge_point_codes if code],
        query=_build_generation_query(inputs),
        limit=5,
    )
    confidentiality = _max_confidentiality([item["assetConfidentiality"] for item in citations])
    model_route = _model_route_for_confidentiality(confidentiality)
    model_provider = "local" if not settings.dify_api_key else "dify"
    model_name = "local-draft-generator" if not settings.dify_api_key else "dify-workflow"

    cards = _build_local_cards(
        inputs=inputs,
        card_sequence=card_sequence or [],
        citations=citations,
    )
    output_content = {
        "cards": cards,
        "citations": [_public_citation(item) for item in citations],
        "idempotencyKey": idempotency_key,
    }

    with engine.begin() as conn:
        run = conn.execute(
            text("""
                INSERT INTO generation.run (
                    application_code, user_code, model_provider, model_name,
                    model_route, prompt_version, confidentiality, status
                )
                VALUES (
                    :application_code, :user_code, :model_provider, :model_name,
                    :model_route, :prompt_version, :confidentiality, 'succeeded'
                )
                RETURNING id, application_code, user_code, model_provider, model_name,
                          model_route, prompt_version, confidentiality, status, created_at
            """),
            {
                "application_code": application_code,
                "user_code": principal_code,
                "model_provider": model_provider,
                "model_name": model_name,
                "model_route": model_route,
                "prompt_version": "wp14_mvp_backend_v1",
                "confidentiality": confidentiality,
            },
        ).fetchone()
        if run is None:
            raise RuntimeError("generation run insert failed")

        for index, item in enumerate(citations, start=1):
            conn.execute(
                text("""
                    INSERT INTO generation.citation (
                        generation_run_id, fragment_id, citation_order, usage_type
                    )
                    VALUES (:run_id, :fragment_id, :citation_order, 'prompt_context')
                """),
                {
                    "run_id": run.id,
                    "fragment_id": item["fragmentId"],
                    "citation_order": index,
                },
            )

        output = conn.execute(
            text("""
                INSERT INTO generation.output (
                    generation_run_id, output_type, content, confidentiality, status
                )
                VALUES (
                    :run_id, :output_type, CAST(:content_json AS jsonb),
                    :confidentiality, 'draft'
                )
                RETURNING id, output_type, content, confidentiality, status, created_at
            """),
            {
                "run_id": run.id,
                "output_type": output_type,
                "content_json": json.dumps(output_content, ensure_ascii=False),
                "confidentiality": confidentiality,
            },
        ).fetchone()
        if output is None:
            raise RuntimeError("generation output insert failed")

    return _generation_response(run=dict(run._mapping), output=dict(output._mapping), citations=citations)


def get_generation_v2(
    engine: Engine,
    *,
    run_id: int,
    principal_type: str,
    principal_code: str,
) -> dict[str, Any]:
    """Return one V2 generation run after citation ACL checks."""
    with engine.connect() as conn:
        run = conn.execute(
            text("""
                SELECT id, application_code, user_code, model_provider, model_name,
                       model_route, prompt_version, confidentiality, status, created_at
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
                    gc.citation_order,
                    gc.usage_type,
                    f.id AS fragment_id,
                    f.fragment_code,
                    f.heading,
                    f.content,
                    f.page_from,
                    f.page_to,
                    a.code AS asset_code,
                    a.title AS asset_title,
                    a.asset_type,
                    a.confidentiality AS asset_confidentiality,
                    av.version_no,
                    c.code AS collection_code
                  FROM generation.citation gc
                  JOIN knowledge.fragment f ON f.id = gc.fragment_id
                  JOIN knowledge.asset_version av ON av.id = f.asset_version_id
                  JOIN knowledge.asset a ON a.id = av.asset_id
                  JOIN knowledge.collection c ON c.id = a.collection_id
                 WHERE gc.generation_run_id = :run_id
                 ORDER BY gc.citation_order
            """),
            {"run_id": run_id},
        ).fetchall()

        output = conn.execute(
            text("""
                SELECT id, output_type, content, confidentiality, status, created_at
                  FROM generation.output
                 WHERE generation_run_id = :run_id
                 ORDER BY id DESC
                 LIMIT 1
            """),
            {"run_id": run_id},
        ).fetchone()

    for row in citation_rows:
        check_collection_access(
            engine,
            principal_type=principal_type,
            principal_code=principal_code,
            collection_code=row.collection_code,
            required_permission="read",
        )

    citations = [
        {
            "fragmentId": row.fragment_id,
            "fragmentCode": row.fragment_code,
            "heading": row.heading,
            "content": row.content,
            "pageFrom": row.page_from,
            "pageTo": row.page_to,
            "assetCode": row.asset_code,
            "assetTitle": row.asset_title,
            "assetType": row.asset_type,
            "assetConfidentiality": row.asset_confidentiality,
            "versionNo": row.version_no,
            "collectionCode": row.collection_code,
        }
        for row in citation_rows
    ]
    return _generation_response(
        run=dict(run._mapping),
        output=dict(output._mapping) if output is not None else None,
        citations=citations,
    )


def _select_generation_citations(
    engine: Engine,
    *,
    principal_type: str,
    principal_code: str,
    collection_codes: list[str],
    knowledge_point_codes: list[str],
    query: str,
    limit: int,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {
        "principal_type": principal_type,
        "principal_code": principal_code,
        "query": query,
        "query_like": f"%{query.lower()}%",
        "limit": limit,
    }
    filters = [
        "c.status = 'active'",
        "a.status = 'published'",
        "av.review_status = 'approved'",
        "fkp.review_status = 'approved'",
        "(av.valid_during IS NULL OR av.valid_during @> CURRENT_DATE)",
    ]
    bindparams = []
    if collection_codes:
        params["collection_codes"] = tuple(collection_codes)
        filters.append("c.code IN :collection_codes")
        bindparams.append(bindparam("collection_codes", expanding=True))
    if knowledge_point_codes:
        params["knowledge_point_codes"] = tuple(knowledge_point_codes)
        filters.append("kp.code IN :knowledge_point_codes")
        bindparams.append(bindparam("knowledge_point_codes", expanding=True))
    statement = text(f"""
        SELECT DISTINCT ON (f.id)
            f.id AS fragment_id,
            f.fragment_code,
            f.heading,
            f.content,
            f.page_from,
            f.page_to,
            a.code AS asset_code,
            a.title AS asset_title,
            a.asset_type,
            a.confidentiality AS asset_confidentiality,
            av.version_no,
            c.code AS collection_code,
            fkp.confidence
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
         ORDER BY f.id, fkp.confidence DESC, a.code, f.fragment_code
         LIMIT :limit
    """)
    if bindparams:
        statement = statement.bindparams(*bindparams)

    with engine.connect() as conn:
        rows = conn.execute(statement, params).fetchall()

    return [
        {
            "fragmentId": row.fragment_id,
            "fragmentCode": row.fragment_code,
            "heading": row.heading,
            "content": row.content,
            "pageFrom": row.page_from,
            "pageTo": row.page_to,
            "assetCode": row.asset_code,
            "assetTitle": row.asset_title,
            "assetType": row.asset_type,
            "assetConfidentiality": row.asset_confidentiality,
            "versionNo": row.version_no,
            "collectionCode": row.collection_code,
        }
        for row in rows
    ]


def _build_generation_query(inputs: dict[str, Any]) -> str:
    parts = [
        str(inputs.get("theme") or ""),
        str(inputs.get("targetAudience") or ""),
        str(inputs.get("examName") or ""),
    ]
    return " ".join(part for part in parts if part).strip()


def _max_confidentiality(values: list[str]) -> str:
    if not values:
        return "internal"
    return max(values, key=lambda value: CONFIDENTIALITY_RANK.get(value, 1))


def _model_route_for_confidentiality(confidentiality: str) -> str:
    if confidentiality == "restricted":
        return "internal"
    return "approved_external" if settings.dify_api_key else "internal"


def _build_local_cards(
    *,
    inputs: dict[str, Any],
    card_sequence: list[str],
    citations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    exam_name = str(inputs.get("examName") or inputs.get("exam_name") or "考试")
    exam_date = str(inputs.get("examDate") or inputs.get("exam_date") or "")
    target = str(inputs.get("targetAudience") or inputs.get("target_audience") or "备考人群")
    theme = str(inputs.get("theme") or "备考规划")
    sequence = card_sequence or ["cover", "plan", "notice", "cta"]
    source_hint = citations[0]["heading"] if citations else "待补充引用"

    cards: list[dict[str, Any]] = []
    for index, card_type in enumerate(sequence, start=1):
        cards.append(
            {
                "type": card_type,
                "title": f"{exam_name}{theme}" if index == 1 else f"{theme} · 第 {index} 张",
                "subtitle": f"面向{target}，考试日期 {exam_date or '待确认'}",
                "days": [],
                "items": [
                    {
                        "label": "资料依据",
                        "content": source_hint,
                    }
                ],
                "qrcode_url": "",
                "citations": [_public_citation(item) for item in citations],
            }
        )
    return cards


def _public_citation(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "assetCode": item["assetCode"],
        "assetTitle": item["assetTitle"],
        "assetType": item["assetType"],
        "versionNo": item["versionNo"],
        "fragmentCode": item["fragmentCode"],
        "heading": item["heading"],
        "pageFrom": item["pageFrom"],
        "pageTo": item["pageTo"],
        "confidentiality": item["assetConfidentiality"],
        "quote": item["content"][:160],
    }


def _generation_response(
    *,
    run: dict[str, Any],
    output: dict[str, Any] | None,
    citations: list[dict[str, Any]],
) -> dict[str, Any]:
    content = output["content"] if output is not None else {}
    return {
        "runId": run["id"],
        "status": run["status"],
        "applicationCode": run["application_code"],
        "outputType": output["output_type"] if output is not None else None,
        "confidentiality": run["confidentiality"],
        "modelRoute": run["model_route"],
        "cards": content.get("cards", []),
        "citations": [_public_citation(item) for item in citations],
        "createdAt": run["created_at"].isoformat(),
    }
