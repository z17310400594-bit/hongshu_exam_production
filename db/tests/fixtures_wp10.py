"""WP10 fixtures — generation runs, citations, and outputs."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from db.tests.fixtures_wp08 import seed_source_asset


def seed_generation_source_asset(
    engine: Engine,
    *,
    asset_code: str,
    collection_code: str = "coll_internal",
    confidentiality: str = "internal",
) -> dict[str, Any]:
    return seed_source_asset(
        engine,
        asset_code=asset_code,
        title=f"{asset_code} 生成引用源文件",
        collection_code=collection_code,
        asset_type="private" if confidentiality == "restricted" else "textbook",
        confidentiality=confidentiality,
        fragments=[
            ("GEN_REF_01", "section", "生成引用 1", 1),
            ("GEN_REF_02", "section", "生成引用 2", 2),
        ],
    )


def seed_generation_run(
    engine: Engine,
    *,
    application_code: str = "xiaohongshu_writer",
    user_code: str = "operator_01",
    model_provider: str = "deepseek",
    model_name: str = "deepseek-chat",
    model_route: str = "approved_external",
    prompt_version: str = "soft_article_v1",
    confidentiality: str = "internal",
    status: str = "succeeded",
) -> dict[str, Any]:
    with engine.begin() as conn:
        row = conn.execute(
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
                "user_code": user_code,
                "model_provider": model_provider,
                "model_name": model_name,
                "model_route": model_route,
                "prompt_version": prompt_version,
                "confidentiality": confidentiality,
                "status": status,
            },
        ).fetchone()
    if row is None:
        raise RuntimeError("generation run insert failed")
    return dict(row._mapping)


def seed_generation_citation(
    engine: Engine,
    *,
    run_id: int,
    fragment_id: int,
    citation_order: int = 1,
    usage_type: str = "reference",
) -> dict[str, Any]:
    with engine.begin() as conn:
        row = conn.execute(
            text("""
                INSERT INTO generation.citation (
                    generation_run_id, fragment_id, citation_order, usage_type
                )
                VALUES (:run_id, :fragment_id, :citation_order, :usage_type)
                RETURNING generation_run_id, fragment_id, citation_order, usage_type
            """),
            {
                "run_id": run_id,
                "fragment_id": fragment_id,
                "citation_order": citation_order,
                "usage_type": usage_type,
            },
        ).fetchone()
    if row is None:
        raise RuntimeError("generation citation insert failed")
    return dict(row._mapping)


def seed_generation_output(
    engine: Engine,
    *,
    run_id: int,
    output_type: str = "article",
    content: dict[str, Any] | list[Any] | str | None = None,
    confidentiality: str = "internal",
    status: str = "reviewed",
    approved_by: str | None = None,
) -> dict[str, Any]:
    content = content if content is not None else {"title": "生成标题", "body": "生成正文"}
    with engine.begin() as conn:
        row = conn.execute(
            text("""
                INSERT INTO generation.output (
                    generation_run_id, output_type, content,
                    confidentiality, status, approved_by
                )
                VALUES (
                    :run_id, :output_type, CAST(:content_json AS jsonb),
                    :confidentiality, :status, :approved_by
                )
                RETURNING id, generation_run_id, output_type, content,
                          confidentiality, status, approved_by, approved_at, created_at
            """),
            {
                "run_id": run_id,
                "output_type": output_type,
                "content_json": json.dumps(content, ensure_ascii=False),
                "confidentiality": confidentiality,
                "status": status,
                "approved_by": approved_by,
            },
        ).fetchone()
    if row is None:
        raise RuntimeError("generation output insert failed")
    return dict(row._mapping)
