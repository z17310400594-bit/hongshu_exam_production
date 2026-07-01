"""Xiaohongshu content generator MVP service.

This service intentionally uses knowledge.fragment as a temporary
"chapter/fragment" source. The content.chapter tables exist for the future
chapter tree, but the current MVP data lives in knowledge fragments.
"""

from __future__ import annotations

import json
import re
from typing import Any

import requests
from sqlalchemy import text
from sqlalchemy.engine import Engine

from api.config import settings

MAX_SOURCE_TEXT_CHARS = 3000
DEFAULT_CERTIFICATE_CODE = "pharmacist_licensed"

ANGLE_TYPES = {"错因诊断", "口诀记忆", "避坑纠偏", "阶段补救"}
CTA_TYPES = {"收藏+评论卡点", "收藏复习", "评论下一篇", "评论补救"}
DENSITY_TYPES = {"短平快", "信息稍密"}


class XhsContentError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def list_xhs_chapters(
    engine: Engine,
    *,
    principal_type: str,
    principal_code: str,
    certificate_code: str = DEFAULT_CERTIFICATE_CODE,
    query: str = "",
    asset_type: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Return ACL-readable knowledge fragments as temporary chapter options."""

    terms = _certificate_asset_terms(certificate_code)
    params: dict[str, Any] = {
        "principal_type": principal_type,
        "principal_code": principal_code,
        "query": query.strip(),
        "query_like": f"%{query.strip().lower()}%",
        "limit": max(1, min(limit, 100)),
    }
    filters = [
        "a.status = 'published'",
        "av.review_status = 'approved'",
        "acl.permission = 'read'",
        """
        (
            :query = ''
            OR lower(coalesce(f.heading, '')) LIKE :query_like
            OR lower(f.content) LIKE :query_like
            OR lower(a.code) LIKE :query_like
        )
        """,
    ]
    term_filters = []
    for index, term in enumerate(terms):
        key = f"asset_term_{index}"
        params[key] = term
        term_filters.append(f"lower(a.code) LIKE :{key}")
    filters.append(f"({' OR '.join(term_filters)})")
    if asset_type:
        params["asset_type"] = asset_type
        filters.append("a.asset_type = :asset_type")

    statement = text(f"""
        SELECT
            f.id AS chapter_id,
            f.fragment_code,
            coalesce(nullif(f.heading, ''), f.fragment_code) AS title,
            f.content,
            a.code AS asset_code,
            a.title AS asset_title,
            a.asset_type,
            c.code AS collection_code
          FROM knowledge.fragment f
          JOIN knowledge.asset_version av ON av.id = f.asset_version_id
          JOIN knowledge.asset a ON a.id = av.asset_id
          JOIN knowledge.collection c ON c.id = a.collection_id
          JOIN knowledge.collection_acl acl ON acl.collection_id = c.id
         WHERE acl.principal_type = :principal_type
           AND acl.principal_code = :principal_code
           AND {" AND ".join(filters)}
         ORDER BY a.asset_type, a.code, f.sequence_no, f.id
         LIMIT :limit
    """)

    with engine.connect() as conn:
        rows = conn.execute(statement, params).fetchall()

    return {
        "items": [
            {
                "chapterId": str(row.chapter_id),
                "chapterCode": row.fragment_code,
                "title": row.title,
                "assetCode": row.asset_code,
                "assetTitle": row.asset_title,
                "assetType": row.asset_type,
                "collectionCode": row.collection_code,
                "textPreview": _clip(row.content or "", 120),
                "textLength": len(row.content or ""),
            }
            for row in rows
        ],
        "nextCursor": None,
    }


def get_xhs_chapter(
    engine: Engine,
    *,
    principal_type: str,
    principal_code: str,
    chapter_id: str,
) -> dict[str, Any]:
    row = _get_fragment_row(
        engine,
        principal_type=principal_type,
        principal_code=principal_code,
        chapter_id=chapter_id,
    )
    if row is None:
        raise XhsContentError("CHAPTER_NOT_FOUND", "章节/片段不存在或无权访问")
    source_text, truncated = _truncate_source(row.content or "")
    return {
        "chapterId": str(row.chapter_id),
        "chapterCode": row.fragment_code,
        "title": row.title,
        "assetCode": row.asset_code,
        "assetTitle": row.asset_title,
        "assetType": row.asset_type,
        "sourceText": source_text,
        "textLength": len(row.content or ""),
        "sourceTruncated": truncated,
    }


def generate_xhs_content(
    engine: Engine,
    *,
    principal_type: str,
    principal_code: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    try:
        request = _normalize_generate_payload(payload)
        source = _resolve_source_text(
            engine,
            principal_type=principal_type,
            principal_code=principal_code,
            request=request,
        )
        dify_inputs = {
            **request,
            "source_text": source["sourceText"],
            "source_label": source["sourceLabel"],
            "source_truncated": "true" if source["sourceTruncated"] else "false",
        }
        raw_output = _call_xhs_dify(dify_inputs)
        data = _parse_xhs_json(raw_output)
        return {"ok": True, "data": data, "raw_output": raw_output, "error": None}
    except XhsContentError as exc:
        return {
            "ok": False,
            "data": None,
            "raw_output": getattr(exc, "raw_output", ""),
            "error": {"code": exc.code, "message": exc.message},
        }


def _resolve_source_text(
    engine: Engine,
    *,
    principal_type: str,
    principal_code: str,
    request: dict[str, Any],
) -> dict[str, Any]:
    if request["source_mode"] == "custom_text":
        text_value = request["custom_text"].strip()
        if not text_value:
            raise XhsContentError("CUSTOM_TEXT_REQUIRED", "请先粘贴自定义素材")
        if len(text_value) > MAX_SOURCE_TEXT_CHARS:
            raise XhsContentError("CUSTOM_TEXT_TOO_LONG", "自定义素材最多 3000 字")
        return {"sourceText": text_value, "sourceLabel": "自定义粘贴素材", "sourceTruncated": False}

    chapter_id = request["chapter_id"].strip()
    if not chapter_id:
        raise XhsContentError("CHAPTER_REQUIRED", "请选择章节/片段")
    chapter = get_xhs_chapter(
        engine,
        principal_type=principal_type,
        principal_code=principal_code,
        chapter_id=chapter_id,
    )
    return {
        "sourceText": chapter["sourceText"],
        "sourceLabel": f"{chapter['assetTitle']} / {chapter['title']}",
        "sourceTruncated": chapter["sourceTruncated"],
    }


def _normalize_generate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    source_mode = str(payload.get("source_mode") or payload.get("sourceMode") or "database")
    angle_type = str(payload.get("angle_type") or payload.get("angleType") or "错因诊断")
    cta_type = str(payload.get("cta_type") or payload.get("ctaType") or "收藏+评论卡点")
    density = str(payload.get("density") or "短平快")

    if source_mode not in {"database", "custom_text"}:
        raise XhsContentError("INVALID_SOURCE_MODE", "素材来源只能是 database 或 custom_text")
    if angle_type not in ANGLE_TYPES:
        raise XhsContentError("INVALID_ANGLE_TYPE", "内容角度不支持")
    if cta_type not in CTA_TYPES:
        raise XhsContentError("INVALID_CTA_TYPE", "CTA 类型不支持")
    if density not in DENSITY_TYPES:
        raise XhsContentError("INVALID_DENSITY", "卡片密度不支持")

    return {
        "source_mode": source_mode,
        "chapter_id": str(payload.get("chapter_id") or payload.get("chapterId") or ""),
        "custom_text": str(payload.get("custom_text") or payload.get("customText") or ""),
        "knowledge_keyword": str(payload.get("knowledge_keyword") or payload.get("knowledgeKeyword") or ""),
        "angle_type": angle_type,
        "target_user": str(payload.get("target_user") or payload.get("targetUser") or "学了一段但做题总错"),
        "tone": str(payload.get("tone") or "备考陪跑"),
        "density": density,
        "cta_type": cta_type,
        "extra_requirement": str(payload.get("extra_requirement") or payload.get("extraRequirement") or ""),
    }


def _call_xhs_dify(inputs: dict[str, Any]) -> str:
    api_key = settings.xhs_content_dify_api_key or settings.dify_api_key
    if not settings.dify_api_url or not api_key:
        return json.dumps(_local_xhs_draft(inputs), ensure_ascii=False)

    base = settings.dify_api_url.rstrip("/")
    endpoint = f"{base}/workflows/run" if base.endswith("/v1") else f"{base}/v1/workflows/run"
    timeout = None if settings.model_gateway_timeout_seconds <= 0 else settings.model_gateway_timeout_seconds
    try:
        response = requests.post(
            endpoint,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"inputs": inputs, "response_mode": "blocking", "user": "xhs-content-generator"},
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise XhsContentError("DIFY_REQUEST_FAILED", "Dify 请求失败") from exc

    try:
        body = response.json()
    except ValueError as exc:
        error = XhsContentError("DIFY_RESPONSE_NOT_JSON", "Dify 响应不是 JSON")
        error.raw_output = response.text  # type: ignore[attr-defined]
        raise error from exc

    outputs = body.get("data", {}).get("outputs", {})
    text_output = outputs.get("text") or outputs.get("result") or outputs.get("answer")
    if isinstance(text_output, str) and text_output.strip():
        return text_output
    if isinstance(outputs, dict) and outputs:
        return json.dumps(outputs, ensure_ascii=False)
    raise XhsContentError("DIFY_EMPTY_OUTPUT", "Dify 返回为空")


def _parse_xhs_json(raw_output: str) -> dict[str, Any]:
    cleaned = _strip_non_json(raw_output)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        error = XhsContentError("LLM_JSON_PARSE_ERROR", "生成结果格式异常")
        error.raw_output = raw_output  # type: ignore[attr-defined]
        raise error from exc
    if not isinstance(data, dict):
        error = XhsContentError("LLM_JSON_PARSE_ERROR", "生成结果格式异常")
        error.raw_output = raw_output  # type: ignore[attr-defined]
        raise error
    for key in ("meta", "internal", "external", "next_topics"):
        if key not in data:
            error = XhsContentError("LLM_JSON_SCHEMA_ERROR", f"生成结果缺少字段 {key}")
            error.raw_output = raw_output  # type: ignore[attr-defined]
            raise error
    return data


def _strip_non_json(raw_output: str) -> str:
    text_value = re.sub(r"<think>.*?</think>", "", raw_output or "", flags=re.DOTALL).strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text_value, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        text_value = fence.group(1).strip()
    start = text_value.find("{")
    end = text_value.rfind("}")
    if start >= 0 and end >= start:
        return text_value[start : end + 1]
    return text_value


def _get_fragment_row(
    engine: Engine,
    *,
    principal_type: str,
    principal_code: str,
    chapter_id: str,
):
    statement = text("""
        SELECT
            f.id AS chapter_id,
            f.fragment_code,
            coalesce(nullif(f.heading, ''), f.fragment_code) AS title,
            f.content,
            a.code AS asset_code,
            a.title AS asset_title,
            a.asset_type
          FROM knowledge.fragment f
          JOIN knowledge.asset_version av ON av.id = f.asset_version_id
          JOIN knowledge.asset a ON a.id = av.asset_id
          JOIN knowledge.collection c ON c.id = a.collection_id
          JOIN knowledge.collection_acl acl ON acl.collection_id = c.id
         WHERE acl.principal_type = :principal_type
           AND acl.principal_code = :principal_code
           AND acl.permission = 'read'
           AND (CAST(f.id AS text) = :chapter_id OR f.fragment_code = :chapter_id)
         LIMIT 1
    """)
    with engine.connect() as conn:
        return conn.execute(
            statement,
            {"principal_type": principal_type, "principal_code": principal_code, "chapter_id": chapter_id},
        ).fetchone()


def _certificate_asset_terms(certificate_code: str) -> list[str]:
    value = certificate_code.lower()
    if "pharmacist" in value or "药师" in value:
        return ["%pharm%", "%pharmacist%"]
    return [f"%{value}%"]


def _truncate_source(text_value: str) -> tuple[str, bool]:
    if len(text_value) <= MAX_SOURCE_TEXT_CHARS:
        return text_value, False
    return text_value[:MAX_SOURCE_TEXT_CHARS], True


def _clip(text_value: str, max_chars: int) -> str:
    compact = re.sub(r"\s+", " ", text_value).strip()
    return compact[:max_chars]


def _local_xhs_draft(inputs: dict[str, Any]) -> dict[str, Any]:
    keyword = inputs.get("knowledge_keyword") or "这个考点"
    angle = inputs.get("angle_type") or "错因诊断"
    return {
        "meta": {
            "angle_type": angle,
            "target_user": inputs.get("target_user", ""),
            "tone": inputs.get("tone", ""),
            "length_style": inputs.get("density", ""),
            "cta_type": inputs.get("cta_type", ""),
        },
        "internal": {
            "source_basis": [{"source": inputs.get("source_label", ""), "quote": _clip(inputs.get("source_text", ""), 80)}],
            "core_point": "把原文信息转成做题时能用的判断抓手。",
            "risk_notes": ["本地草稿仅用于开发自测，正式内容需调用 Dify。", "禁止将内容理解为实际用药建议。"],
            "self_check": ["字段完整", "无保过承诺", "无实际用药建议"],
        },
        "external": {
            "title_candidates": [
                {"index": 0, "title": f"{keyword}总错，先别急着重背", "style": "轻松陪跑"},
                {"index": 1, "title": f"你可能没抓住{keyword}的判断点", "style": "轻焦虑痛点"},
                {"index": 2, "title": f"{keyword}这样拆，刷题更清楚", "style": "轻松陪跑"},
            ],
            "selected_title_index": 0,
            "cover_copy": f"{keyword}总错？先抓判断点",
            "cards": [
                {"card_no": 1, "title": "先把问题缩小", "body": f"今天只看 {keyword} 一个小点，不重背整章。", "layout_hint": "大标题"},
                {"card_no": 2, "title": "原文抓手要圈出来", "body": "圈出题干能对应的关键词。", "layout_hint": "关键词高亮"},
                {"card_no": 3, "title": "今天小动作", "body": f"把 {keyword} 对应原文里 3 个关键词圈出来。", "layout_hint": "行动清单"},
            ],
            "caption": f"今天只拆 {keyword} 一个小点，先让一个点变清楚。",
            "hashtags": ["#执业药师", "#执业药师备考"],
            "cta": "如果你也总卡在这里，可以把卡点打在评论区。",
            "today_action": f"把 {keyword} 原文里 3 个关键词圈出来。",
        },
        "next_topics": [{"title": f"{keyword}还能怎么考？", "angle_type": "错因诊断", "reason": "延续同一知识点。"}],
    }
