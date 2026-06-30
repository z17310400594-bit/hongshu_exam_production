"""Generation workflow service — WP14 MVP backendized generation.

This is deliberately small: it creates an auditable generation run, gathers
approved ACL-readable citations, stores a draft output, and returns a card set.
P5 adds a backend-only model gateway boundary. The browser still only receives
task/result/citation data; provider credentials stay on the server.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Engine

from api.auth import check_collection_access
from api.config import settings
from api.services import model_gateway

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
    requested_collections = [code for code in collection_codes if code]
    is_pharmacist_generation = _is_pharmacist_generation(certificate_code=certificate_code, inputs=inputs)
    requested_knowledge_points = [code for code in knowledge_point_codes if code]
    asset_code_prefix = None
    asset_types: list[str] = []
    random_seed = idempotency_key or _build_generation_query(inputs)
    if is_pharmacist_generation:
        requested_knowledge_points = ["pharm_2026_general"]
        asset_code_prefix = "pharm_2026_%"
        asset_types = ["textbook", "handout", "manual"]

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
        knowledge_point_codes=requested_knowledge_points,
        query=_build_generation_query(inputs),
        asset_code_prefix=asset_code_prefix,
        asset_types=asset_types,
        random_seed=random_seed,
        randomize=is_pharmacist_generation,
        limit=5,
    )
    if not citations:
        run = _insert_generation_run(
            engine,
            application_code=application_code,
            principal_code=principal_code,
            model_provider="local",
            model_name="local-draft-generator",
            model_route="internal",
            prompt_version="p5_model_gateway_v1",
            confidentiality="internal",
            status="failed",
        )
        return _generation_response(
            run=run,
            output=None,
            citations=[],
            requested_output_type=output_type,
            error={
                "code": "GENERATION_REQUIRES_CITATION",
                "message": "Generation requires at least one readable citation",
                "provider": "local",
            },
        )

    confidentiality = _max_confidentiality([item["assetConfidentiality"] for item in citations])
    model_route = _model_route_for_confidentiality(confidentiality)
    initial_provider = _configured_model_provider(model_route)
    initial_model_name = "dify-workflow" if initial_provider == "dify" else "local-draft-generator"
    run = _insert_generation_run(
        engine,
        application_code=application_code,
        principal_code=principal_code,
        model_provider=initial_provider,
        model_name=initial_model_name,
        model_route=model_route,
        prompt_version="p5_model_gateway_v1",
        confidentiality=confidentiality,
        status="running",
    )
    with engine.begin() as conn:
        for index, item in enumerate(citations, start=1):
            conn.execute(
                text("""
                    INSERT INTO generation.citation (
                        generation_run_id, fragment_id, citation_order, usage_type
                    )
                    VALUES (:run_id, :fragment_id, :citation_order, 'prompt_context')
                """),
                {
                    "run_id": run["id"],
                    "fragment_id": item["fragmentId"],
                    "citation_order": index,
                },
            )

    try:
        gateway_result = model_gateway.generate_cards(
            application_code=application_code,
            output_type=output_type,
            certificate_code=certificate_code,
            principal_code=principal_code,
            model_route=model_route,
            inputs=inputs,
            card_sequence=card_sequence or [],
            citations=citations,
        )
    except model_gateway.ModelGatewayError as exc:
        failed_run = _update_generation_run_status(engine, run_id=run["id"], status="failed")
        return _generation_response(
            run=failed_run,
            output=None,
            citations=citations,
            requested_output_type=output_type,
            error=exc.to_public_dict(),
        )

    output_content = {
        "cards": _cards_with_citations(gateway_result.cards, citations),
        "citations": [_public_citation(item) for item in citations],
        "idempotencyKey": idempotency_key,
        "gateway": {
            "provider": gateway_result.provider,
            "modelName": gateway_result.model_name,
            "metadata": gateway_result.raw_metadata,
        },
    }

    with engine.begin() as conn:
        run_row = conn.execute(
            text("""
                UPDATE generation.run
                   SET status = 'succeeded',
                       model_provider = :model_provider,
                       model_name = :model_name
                 WHERE id = :run_id
             RETURNING id, application_code, user_code, model_provider, model_name,
                       model_route, prompt_version, confidentiality, status, created_at
            """),
            {
                "run_id": run["id"],
                "model_provider": gateway_result.provider,
                "model_name": gateway_result.model_name,
            },
        ).fetchone()
        if run_row is None:
            raise RuntimeError("generation run update failed")
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
                "run_id": run["id"],
                "output_type": output_type,
                "content_json": json.dumps(output_content, ensure_ascii=False),
                "confidentiality": confidentiality,
            },
        ).fetchone()
        if output is None:
            raise RuntimeError("generation output insert failed")

    return _generation_response(run=dict(run_row._mapping), output=dict(output._mapping), citations=citations)


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
    asset_code_prefix: str | None = None,
    asset_types: list[str] | None = None,
    random_seed: str | None = None,
    randomize: bool = False,
    limit: int,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {
        "principal_type": principal_type,
        "principal_code": principal_code,
        "query": query,
        "query_like": f"%{query.lower()}%",
        "randomize": randomize,
        "random_seed": random_seed or query or "generation",
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
    if asset_code_prefix:
        params["asset_code_prefix"] = asset_code_prefix
        filters.append("a.code LIKE :asset_code_prefix")
    if asset_types:
        params["asset_types"] = tuple(asset_types)
        filters.append("a.asset_type IN :asset_types")
        bindparams.append(bindparam("asset_types", expanding=True))
    statement = text(f"""
        WITH candidates AS (
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
        )
        SELECT *
          FROM candidates
         ORDER BY
            CASE WHEN :randomize THEN md5(fragment_id::text || :random_seed) END,
            confidence DESC,
            asset_code,
            fragment_code
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


def _is_pharmacist_generation(*, certificate_code: str | None, inputs: dict[str, Any]) -> bool:
    certificate_value = (certificate_code or "").lower()
    if "pharmacist" in certificate_value or "药师" in certificate_value:
        return True
    text_values = [
        str(inputs.get("examName") or ""),
        str(inputs.get("theme") or ""),
        str(inputs.get("targetAudience") or ""),
    ]
    return any("执业药师" in value or "药师" in value for value in text_values)


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
    return "approved_external" if _configured_model_provider("approved_external") == "dify" else "internal"


def _configured_model_provider(model_route: str) -> str:
    provider = settings.generation_provider.strip().lower() or "local"
    if provider == "dify" and model_route == "approved_external":
        return "dify"
    return "local"


def _insert_generation_run(
    engine: Engine,
    *,
    application_code: str,
    principal_code: str,
    model_provider: str,
    model_name: str,
    model_route: str,
    prompt_version: str,
    confidentiality: str,
    status: str,
) -> dict[str, Any]:
    with engine.begin() as conn:
        run = conn.execute(
            text("""
                INSERT INTO generation.run (
                    application_code, user_code, model_provider, model_name,
                    model_route, prompt_version, confidentiality, status
                )
                VALUES (
                    :application_code, :user_code, :model_provider, :model_name,
                    :model_route, :prompt_version, :confidentiality, :status
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
                "prompt_version": prompt_version,
                "confidentiality": confidentiality,
                "status": status,
            },
        ).fetchone()
    if run is None:
        raise RuntimeError("generation run insert failed")
    return dict(run._mapping)


def _update_generation_run_status(engine: Engine, *, run_id: int, status: str) -> dict[str, Any]:
    with engine.begin() as conn:
        run = conn.execute(
            text("""
                UPDATE generation.run
                   SET status = :status
                 WHERE id = :run_id
             RETURNING id, application_code, user_code, model_provider, model_name,
                       model_route, prompt_version, confidentiality, status, created_at
            """),
            {"run_id": run_id, "status": status},
        ).fetchone()
    if run is None:
        raise RuntimeError("generation run update failed")
    return dict(run._mapping)


def _cards_with_citations(cards: list[dict[str, Any]], citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    public_citations = [_public_citation(item) for item in citations]
    normalized_cards: list[dict[str, Any]] = []
    for card in cards:
        normalized = dict(card)
        if not normalized.get("citations"):
            normalized["citations"] = public_citations
        normalized_cards.append(normalized)
    return normalized_cards


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
    requested_output_type: str | None = None,
    error: dict[str, str] | None = None,
) -> dict[str, Any]:
    content = output["content"] if output is not None else {}
    response = {
        "runId": run["id"],
        "status": run["status"],
        "applicationCode": run["application_code"],
        "outputType": output["output_type"] if output is not None else requested_output_type,
        "confidentiality": run["confidentiality"],
        "modelRoute": run["model_route"],
        "cards": content.get("cards", []),
        "citations": [_public_citation(item) for item in citations],
        "createdAt": run["created_at"].isoformat(),
    }
    if error is not None:
        response["error"] = error
    return response
