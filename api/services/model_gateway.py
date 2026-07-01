"""Backend-only model gateway for generation workflows.

The browser must never call a model provider directly or receive provider
secrets. This module keeps the provider boundary behind the API service while
preserving a deterministic local generator for MVP/dev environments.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

from api.config import settings


@dataclass(frozen=True)
class ModelGatewayResult:
    provider: str
    model_name: str
    cards: list[dict[str, Any]]
    raw_metadata: dict[str, Any]


class ModelGatewayError(RuntimeError):
    """A sanitized model-gateway failure that is safe to return/log."""

    def __init__(self, *, code: str, message: str, provider: str = "unknown") -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.provider = provider

    def to_public_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "message": self.message,
            "provider": self.provider,
        }


DEFAULT_CARD_SEQUENCE = ["cover", "plan", "notice", "cta"]
DIFY_CARD_MAX_ATTEMPTS = 4
V1_STYLE_MAX_ATTEMPTS = 2
V1_STYLE_SOURCE_QUOTE_CHARS = 1100


def generate_cards(
    *,
    application_code: str,
    output_type: str,
    certificate_code: str | None,
    principal_code: str,
    model_route: str,
    inputs: dict[str, Any],
    card_sequence: list[str],
    citations: list[dict[str, Any]],
) -> ModelGatewayResult:
    """Generate cards via the configured gateway.

    `GENERATION_PROVIDER=local` is the safe default. Set
    `GENERATION_PROVIDER=dify` with backend-only `DIFY_API_URL` and
    `DIFY_API_KEY` to call Dify for non-restricted approved external routes.
    Restricted/internal routes always stay on the local generator.
    """
    provider = settings.generation_provider.strip().lower() or "local"
    if provider == "dify" and model_route == "approved_external":
        return _generate_with_dify(
            application_code=application_code,
            output_type=output_type,
            certificate_code=certificate_code,
            principal_code=principal_code,
            inputs=inputs,
            card_sequence=card_sequence,
            citations=citations,
        )
    if provider not in {"local", "dify"}:
        raise ModelGatewayError(
            code="MODEL_PROVIDER_UNSUPPORTED",
            message="Configured model provider is not supported",
            provider=provider,
        )
    return _generate_local(inputs=inputs, card_sequence=card_sequence, citations=citations)


def _generate_with_dify(
    *,
    application_code: str,
    output_type: str,
    certificate_code: str | None,
    principal_code: str,
    inputs: dict[str, Any],
    card_sequence: list[str],
    citations: list[dict[str, Any]],
) -> ModelGatewayResult:
    if not settings.dify_api_url or not settings.dify_api_key:
        raise ModelGatewayError(
            code="MODEL_GATEWAY_NOT_CONFIGURED",
            message="Dify gateway is not configured",
            provider="dify",
        )

    endpoint = _dify_workflow_endpoint(settings.dify_api_url)
    headers = {
        "Authorization": f"Bearer {settings.dify_api_key}",
        "Content-Type": "application/json",
    }
    sequence = _normalize_card_sequence(card_sequence)
    mode = settings.generation_orchestration_mode.strip().lower() or "v1_style"
    if mode in {"v1_style", "v1", "group", "grouped"}:
        return _generate_group_with_dify(
            endpoint=endpoint,
            headers=headers,
            application_code=application_code,
            output_type=output_type,
            certificate_code=certificate_code,
            principal_code=principal_code,
            inputs=inputs,
            card_sequence=sequence,
            citations=citations,
        )

    return _generate_per_card_with_dify(
        endpoint=endpoint,
        headers=headers,
        application_code=application_code,
        output_type=output_type,
        certificate_code=certificate_code,
        principal_code=principal_code,
        inputs=inputs,
        card_sequence=sequence,
        citations=citations,
    )


def _generate_per_card_with_dify(
    *,
    endpoint: str,
    headers: dict[str, str],
    application_code: str,
    output_type: str,
    certificate_code: str | None,
    principal_code: str,
    inputs: dict[str, Any],
    card_sequence: list[str],
    citations: list[dict[str, Any]],
) -> ModelGatewayResult:

    all_cards: list[dict[str, Any]] = []
    runs: list[dict[str, Any]] = []
    for card_type in card_sequence:
        body, cards = _request_renderable_cards(
            endpoint=endpoint,
            headers=headers,
            expected_card_type=card_type,
            payload=_dify_workflow_payload(
                application_code=application_code,
                output_type=output_type,
                certificate_code=certificate_code,
                principal_code=principal_code,
                inputs=inputs,
                card_sequence=[card_type],
                citations=citations,
            ),
        )
        all_cards.extend(_cards_with_default_citations(cards, citations))
        runs.append({"cardType": card_type, **_dify_metadata(body)})

    return ModelGatewayResult(
        provider="dify",
        model_name="dify-workflow",
        cards=all_cards,
        raw_metadata={"mode": "per_card_workflow", "requestedCardCount": len(card_sequence), "runs": runs},
    )


def _generate_group_with_dify(
    *,
    endpoint: str,
    headers: dict[str, str],
    application_code: str,
    output_type: str,
    certificate_code: str | None,
    principal_code: str,
    inputs: dict[str, Any],
    card_sequence: list[str],
    citations: list[dict[str, Any]],
) -> ModelGatewayResult:
    payload = _dify_workflow_payload(
        application_code=application_code,
        output_type=output_type,
        certificate_code=certificate_code,
        principal_code=principal_code,
        inputs=inputs,
        card_sequence=card_sequence,
        citations=citations,
    )
    last_body: dict[str, Any] = {}
    last_cards: list[dict[str, Any]] = []
    for _attempt in range(V1_STYLE_MAX_ATTEMPTS):
        last_body = _post_dify_workflow(endpoint=endpoint, payload=payload, headers=headers)
        extracted = _extract_cards_from_dify_response(last_body)
        cards = _cards_with_default_citations(
            _cards_for_requested_sequence(extracted, expected_sequence=card_sequence),
            citations,
        )
        last_cards = cards
        if _cards_have_renderable_content(cards) and _cards_pass_quality_gate(cards, expected_sequence=card_sequence):
            return ModelGatewayResult(
                provider="dify",
                model_name="dify-workflow",
                cards=cards,
                raw_metadata={
                    "mode": "v1_style_group_workflow",
                    "requestedCardCount": len(card_sequence),
                    **_dify_metadata(last_body),
                },
            )

    problem = _quality_problem(last_cards, expected_sequence=card_sequence)
    raise ModelGatewayError(
        code="MODEL_GATEWAY_LOW_QUALITY_OUTPUT",
        message=f"Model gateway returned incomplete v1-style card set: {problem}",
        provider="dify",
    )


def _normalize_card_sequence(card_sequence: list[str]) -> list[str]:
    sequence = [str(item).strip() for item in card_sequence if str(item).strip()]
    return sequence or DEFAULT_CARD_SEQUENCE.copy()


def _list_input(inputs: dict[str, Any], key: str) -> list[Any]:
    value = inputs.get(key)
    return value if isinstance(value, list) else []


def _request_renderable_cards(
    *,
    endpoint: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    expected_card_type: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    for _attempt in range(DIFY_CARD_MAX_ATTEMPTS):
        body = _post_dify_workflow(endpoint=endpoint, payload=payload, headers=headers)
        cards = _cards_for_requested_type(
            _extract_cards_from_dify_response(body, expected_card_type=expected_card_type),
            expected_card_type=expected_card_type,
        )
        if _cards_have_renderable_content(cards):
            return body, cards

    raise ModelGatewayError(
        code="MODEL_GATEWAY_EMPTY_OUTPUT",
        message=f"Model gateway returned no renderable {expected_card_type} card",
        provider="dify",
    ) from None


def _cards_for_requested_type(
    cards: list[dict[str, Any]],
    *,
    expected_card_type: str,
) -> list[dict[str, Any]]:
    requested = str(expected_card_type).strip()
    matched: list[dict[str, Any]] = []
    for card in cards:
        card_type = str(card.get("type") or "").strip()
        if not card_type:
            normalized = {**card, "type": requested}
            matched.append(_normalize_card_for_frontend(normalized, expected_card_type=requested))
        elif card_type == requested:
            matched.append(_normalize_card_for_frontend(card, expected_card_type=requested))
    return matched[:1]


def _cards_for_requested_sequence(cards: list[dict[str, Any]], *, expected_sequence: list[str]) -> list[dict[str, Any]]:
    expected = [str(item).strip() for item in expected_sequence if str(item).strip()]
    if not expected:
        expected = DEFAULT_CARD_SEQUENCE.copy()
    buckets: dict[str, list[dict[str, Any]]] = {card_type: [] for card_type in expected}
    fallback_cards: list[dict[str, Any]] = []
    for card in cards:
        card_type = str(card.get("type") or "").strip()
        if card_type in buckets:
            buckets[card_type].append(card)
        else:
            fallback_cards.append(card)

    normalized: list[dict[str, Any]] = []
    used_fallback = 0
    for card_type in expected:
        raw_card: dict[str, Any] | None = None
        if buckets[card_type]:
            raw_card = buckets[card_type].pop(0)
        elif used_fallback < len(fallback_cards):
            raw_card = {**fallback_cards[used_fallback], "type": card_type}
            used_fallback += 1
        if raw_card is not None:
            normalized.append(_normalize_card_for_frontend(raw_card, expected_card_type=card_type))
    return normalized


def _normalize_card_for_frontend(card: dict[str, Any], *, expected_card_type: str) -> dict[str, Any]:
    normalized: dict[str, Any] = {
        "type": str(card.get("type") or expected_card_type).strip() or expected_card_type,
        "title": str(card.get("title") or "").strip(),
        "subtitle": str(card.get("subtitle") or "").strip(),
        "days": _normalize_plan_days(card.get("days")),
        "items": _normalize_card_items(card.get("items")),
        "qrcode_url": str(card.get("qrcode_url") or ""),
        "citations": card.get("citations") if isinstance(card.get("citations"), list) else [],
    }
    study_material = _normalize_study_material(card.get("study_material"))
    if study_material:
        normalized["study_material"] = study_material
    if str(card.get("mentor_note") or "").strip():
        normalized["mentor_note"] = str(card.get("mentor_note")).strip()
    return normalized


def _normalize_plan_days(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    days: list[dict[str, str]] = []
    for item in value:
        if isinstance(item, str):
            days.append({"date": "", "weekday": "", "task": item.strip(), "duration": ""})
            continue
        if not isinstance(item, dict):
            continue
        nested_items = item.get("items")
        nested_task = "；".join(str(part).strip() for part in nested_items if str(part).strip()) if isinstance(nested_items, list) else ""
        date = _first_text(item, "date", "day", "days", "range", "label", "unit")
        weekday = _first_text(item, "weekday", "week")
        task = nested_task or _first_text(item, "task", "content", "phase", "title", "name", "label", "value")
        duration = _first_text(item, "duration", "time", "period", "value")
        days.append(
            {
                "date": date,
                "weekday": weekday,
                "task": task,
                "duration": duration,
            }
        )
    return [day for day in days if day["date"] or day["task"] or day["duration"]]


def _normalize_card_items(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    items: list[dict[str, str]] = []
    for index, item in enumerate(value, start=1):
        if isinstance(item, str):
            items.append(_split_item_text(item, fallback_label=f"要点{index}"))
            continue
        if not isinstance(item, dict):
            continue
        label = _first_text(item, "label", "title", "name", "chapter", "subject", "topic")
        content = _first_text(item, "content", "text", "description", "desc", "detail", "value")
        if not label and content:
            split = _split_item_text(content, fallback_label=f"要点{index}")
            items.append(split)
            continue
        if label and not content:
            text = _first_text(item, "text", "description", "desc", "detail", "value")
            content = text if text != label else ""
        items.append({"label": label or f"要点{index}", "content": content})
    return items


def _normalize_study_material(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    modules: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, str):
            modules.append({"module_title": item.strip(), "key_points": [], "memory_tips": []})
            continue
        if not isinstance(item, dict):
            continue
        title = _first_text(item, "module_title", "title", "name", "assetTitle", "assetCode")
        key_points = _string_list(item.get("key_points") or item.get("points") or item.get("items"))
        description = _first_text(item, "description", "content", "text", "desc")
        if description and not key_points:
            key_points = [description]
        memory_tips = _string_list(item.get("memory_tips") or item.get("tips"))
        module: dict[str, Any] = {
            "module_title": title or "资料模块",
            "key_points": key_points,
            "memory_tips": memory_tips,
        }
        source = _first_text(item, "source")
        if source in {"knowledge_base", "llm_search"}:
            module["source"] = source
        modules.append(module)
    return modules


def _cards_pass_quality_gate(cards: list[dict[str, Any]], *, expected_sequence: list[str]) -> bool:
    return _quality_problem(cards, expected_sequence=expected_sequence) == "ok"


def _quality_problem(cards: list[dict[str, Any]], *, expected_sequence: list[str]) -> str:
    expected = [str(item).strip() for item in expected_sequence if str(item).strip()]
    if expected and len(cards) < len(expected):
        return f"expected {len(expected)} cards, got {len(cards)}"
    joined = json.dumps(cards, ensure_ascii=False)
    bad_tokens = ["undefined", "null null", "（）", "(）", "（)", "()"]
    if any(token in joined for token in bad_tokens):
        return "contains placeholder/undefined text"

    for index, card in enumerate(cards, start=1):
        card_type = str(card.get("type") or "").strip()
        title = str(card.get("title") or "").strip()
        subtitle = str(card.get("subtitle") or "").strip()
        raw_items = card.get("items")
        raw_days = card.get("days")
        raw_study_material = card.get("study_material")
        items: list[Any] = raw_items if isinstance(raw_items, list) else []
        days: list[Any] = raw_days if isinstance(raw_days, list) else []
        study_material: list[Any] = raw_study_material if isinstance(raw_study_material, list) else []

        if card_type == "cover":
            if len(title) < 10 or len(subtitle) < 8:
                return f"cover card {index} lacks hook title/subtitle"
        elif card_type == "plan":
            usable_days = [
                day
                for day in days
                if isinstance(day, dict) and str(day.get("date") or "").strip() and str(day.get("task") or "").strip()
            ]
            if len(usable_days) < 3:
                return f"plan card {index} has fewer than 3 usable phases"
        elif card_type == "study_material":
            usable_modules = [
                module
                for module in study_material
                if isinstance(module, dict)
                and str(module.get("module_title") or "").strip()
                and len(_list_input(module, "key_points")) >= 2
            ]
            if len(usable_modules) < 2:
                return f"study_material card {index} has too few modules"
        elif card_type == "cta":
            if len(subtitle) < 8 and len(items) < 1:
                return f"cta card {index} lacks action guidance"
        else:
            usable_items = [
                item
                for item in items
                if isinstance(item, dict)
                and str(item.get("label") or "").strip()
                and str(item.get("content") or "").strip()
            ]
            if len(usable_items) < 2:
                return f"{card_type or 'unknown'} card {index} has too few usable items"
    return "ok"


def _first_text(source: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = source.get(key)
        if isinstance(value, (str, int, float)) and str(value).strip():
            return str(value).strip()
    return ""


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _split_item_text(text: str, *, fallback_label: str) -> dict[str, str]:
    clean = text.strip()
    for separator in ("：", ":", "——", "—", " - ", "-"):
        if separator in clean:
            label, content = clean.split(separator, 1)
            if label.strip() and content.strip():
                return {"label": label.strip(), "content": content.strip()}
    return {"label": fallback_label, "content": clean}


def _post_dify_workflow(*, endpoint: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=_model_gateway_timeout()) as client:
            response = client.post(endpoint, json=payload, headers=headers)
    except httpx.TimeoutException as exc:
        raise ModelGatewayError(
            code="MODEL_GATEWAY_TIMEOUT",
            message="Model gateway request timed out",
            provider="dify",
        ) from exc
    except httpx.HTTPError as exc:
        raise ModelGatewayError(
            code="MODEL_GATEWAY_UNAVAILABLE",
            message="Model gateway is unavailable",
            provider="dify",
        ) from exc

    if response.status_code >= 400:
        raise ModelGatewayError(
            code="MODEL_GATEWAY_HTTP_ERROR",
            message=f"Model gateway returned HTTP {response.status_code}",
            provider="dify",
        )

    try:
        body = response.json()
    except ValueError as exc:
        raise ModelGatewayError(
            code="MODEL_GATEWAY_BAD_RESPONSE",
            message="Model gateway returned invalid JSON",
            provider="dify",
        ) from exc
    if not isinstance(body, dict):
        raise ModelGatewayError(
            code="MODEL_GATEWAY_BAD_RESPONSE",
            message="Model gateway returned invalid JSON",
            provider="dify",
        )
    return body


def _model_gateway_timeout() -> float | None:
    timeout = settings.model_gateway_timeout_seconds
    return timeout if timeout > 0 else None


def _dify_workflow_endpoint(api_url: str) -> str:
    base = api_url.rstrip("/")
    return f"{base}/workflows/run" if base.endswith("/v1") else f"{base}/v1/workflows/run"


def _dify_workflow_payload(
    *,
    application_code: str,
    output_type: str,
    certificate_code: str | None,
    principal_code: str,
    inputs: dict[str, Any],
    card_sequence: list[str],
    citations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a Dify workflow payload matching the exported V2 workflow.

    The workflow declares JSON-ish values as paragraph variables, so send them
    as JSON strings instead of raw objects. Its adapter code still accepts both,
    but string inputs avoid Dify start-node type validation surprises.
    """
    source_pack = _source_pack_from_citations(inputs=inputs, card_sequence=card_sequence, citations=citations)
    enriched_inputs = {**inputs, "sourcePack": source_pack}
    return {
        "inputs": {
            "applicationCode": application_code,
            "outputType": output_type,
            "certificateCode": certificate_code or "",
            "generationInputs": json.dumps(enriched_inputs, ensure_ascii=False),
            "cardSequence": json.dumps(card_sequence, ensure_ascii=False),
            # Dify should use factsBrief/sourcePack for grounding, but it must
            # not echo long citations into every card. Repeated citation arrays
            # can exceed Dify output limits and truncate the JSON response. The
            # V2 API owns citations and attaches them after parsing.
            "citations": "[]",
            "factsBrief": _facts_brief_from_citations(citations),
        },
        "response_mode": "blocking",
        "user": principal_code,
    }


def _facts_brief_from_citations(citations: list[dict[str, Any]]) -> str:
    if not citations:
        return "暂无权威引用。事实不足时必须写“以官方通知为准”或“待官方发布”，不得编造具体数字。"
    lines = ["以下为 V2 后端已完成权限过滤的引用片段，只能使用这些事实；可改写表达，不要编造未出现的事实："]
    for index, item in enumerate(citations[:6], start=1):
        public = _public_citation(item)
        source = public.get("assetTitle") or public.get("assetCode") or "资料"
        heading = public.get("heading") or public.get("fragmentCode") or "片段"
        page = f" p.{public['pageFrom']}" if public.get("pageFrom") else ""
        quote = _clip_text(str(item.get("content") or public.get("quote") or ""), V1_STYLE_SOURCE_QUOTE_CHARS)
        lines.append(f"{index}. [{source}{page}] {heading}：{quote}")
    return "\n".join(lines)


def _source_pack_from_citations(
    *,
    inputs: dict[str, Any],
    card_sequence: list[str],
    citations: list[dict[str, Any]],
) -> dict[str, Any]:
    exam_name = str(inputs.get("examName") or inputs.get("exam_name") or "考试")
    target = str(inputs.get("targetAudience") or inputs.get("target_audience") or "备考人群")
    theme = str(inputs.get("theme") or "高效备考")
    content_goal = str(inputs.get("contentGoal") or "")
    lead_assets = _list_input(inputs, "leadAssets")
    script_nodes = _list_input(inputs, "scriptNodes")
    comment_keyword = str(inputs.get("commentKeyword") or "资料")
    conversion_modes = _list_input(inputs, "conversionModes")
    grouped: dict[str, list[dict[str, str]]] = {"textbook": [], "handout": [], "manual": [], "paper": [], "other": []}
    for item in citations[:8]:
        asset_type = str(item.get("assetType") or item.get("asset_type") or "").strip() or "other"
        bucket = asset_type if asset_type in grouped else "other"
        grouped[bucket].append(
            {
                "source": str(item.get("assetTitle") or item.get("assetCode") or "资料"),
                "heading": str(item.get("heading") or item.get("fragmentCode") or "片段"),
                "text": _clip_text(str(item.get("content") or ""), V1_STYLE_SOURCE_QUOTE_CHARS),
            }
        )

    priority_topics = _topic_hints_from_citations(citations)
    narrative_structure = [
        "封面先给强钩子和明确承诺",
        "计划卡给阶段路径，不要空日期或空任务",
        "重点卡给可执行章节/模块清单",
        "资料卡把教材、考点、秘籍转成领取/打印/复习清单",
        "收尾卡给收藏、评论、领取资料的行动引导",
    ]
    hook_strategy = "用倒计时/人群身份/少走弯路/资料已整理制造点击理由，表达像小红书经验帖，不要像政策公告。"
    if content_goal == "resource_lead":
        narrative_structure = [
            str(node.get("purpose") or node.get("label") or node.get("id"))
            for node in script_nodes
            if isinstance(node, dict)
        ] or [
            "封面钩子：用资料已整理制造点击理由",
            "痛点：说明备考资料太散、时间不够",
            "解决方案：先固定几类资料，不要到处找",
            "干货预览：只放少量高频点做信任背书",
            "资料诱饵：展示三色笔记、考点 PDF、打卡表等清单",
            "领取方式：引导评论关键词、私信或收藏等站内动作",
        ]
        hook_strategy = (
            "资料型引流：目标是生成 80%+ 可用小红书成稿。"
            "系统以引流转化脚本为中心，不以固定卡片类型为中心；"
            "专业内容只做信任背书，不要写成完整讲义。"
        )

    return {
        "examBrief": f"{exam_name}备考内容生成。目标人群：{target}。主题方向：{theme}。",
        "hookStrategy": hook_strategy,
        "narrativeStructure": narrative_structure,
        "requestedCards": card_sequence,
        "contentGoal": content_goal,
        "structureTemplate": str(inputs.get("structureTemplate") or ""),
        "leadAssets": [str(item) for item in lead_assets],
        "commentKeyword": comment_keyword,
        "conversionModes": [str(item) for item in conversion_modes],
        "priorityTopics": priority_topics,
        "studyPlanMaterial": [
            "第1阶段：先建立科目框架，抓高频模块和常见计算/记忆点",
            "第2阶段：围绕重点章节做专题突破，把公式、概念、易混点整理成表格",
            "第3阶段：刷题复盘，错题反推教材与考点，考前只看高频清单",
        ],
        "resourceMaterial": [
            "教材：适合建立体系和查漏补缺",
            "考点资料：适合冲刺阶段快速抓重点",
            "考霸秘籍：适合做记忆口诀、易混点和考前速记",
            "题库：适合验证掌握度，文章生成阶段暂不作为主要口吻素材",
        ],
        "sourcesByType": grouped,
    }


def _topic_hints_from_citations(citations: list[dict[str, Any]]) -> list[str]:
    text = "\n".join(str(item.get("heading") or "") + "\n" + str(item.get("content") or "") for item in citations)
    candidates = [
        "药代动力学：AUC、半衰期、表观分布容积、单位换算",
        "药效学：受体理论、量效关系、作用机制和不良反应",
        "药物化学：母核、官能团、命名和代谢转化",
        "药物剂型与制剂：片剂、注射剂、缓控释和靶向制剂",
        "法规与综合：官方通知、准考证、考场安排以最新公告为准",
    ]
    matched = [item for item in candidates if any(keyword in text for keyword in item.split("：", 1)[1].split("、")[:2])]
    return matched or candidates[:3]


def _clip_text(value: str, limit: int) -> str:
    clean = " ".join(value.split())
    if len(clean) <= limit:
        return clean
    return clean[:limit].rstrip() + "..."


def _extract_cards_from_dify_response(
    body: dict[str, Any],
    *,
    expected_card_type: str | None = None,
) -> list[dict[str, Any]]:
    outputs = body.get("data", {}).get("outputs", {}) if isinstance(body.get("data"), dict) else {}
    candidates = [
        outputs.get("cards") if isinstance(outputs, dict) else None,
        outputs.get("result") if isinstance(outputs, dict) else None,
        outputs.get("text") if isinstance(outputs, dict) else None,
        body.get("answer"),
    ]
    for candidate in candidates:
        parsed = _parse_cards_candidate(candidate, expected_card_type=expected_card_type)
        if parsed:
            return parsed
    return []


def _parse_cards_candidate(candidate: Any, *, expected_card_type: str | None = None) -> list[dict[str, Any]]:
    if isinstance(candidate, list) and all(isinstance(item, dict) for item in candidate):
        return candidate
    if isinstance(candidate, dict):
        cards = candidate.get("cards")
        if isinstance(cards, list) and all(isinstance(item, dict) for item in cards):
            return cards
        for nested_key in ("result", "text", "answer", "output"):
            nested = candidate.get(nested_key)
            if nested is candidate:
                continue
            parsed = _parse_cards_candidate(nested, expected_card_type=expected_card_type)
            if parsed:
                return parsed
    if isinstance(candidate, str) and candidate.strip():
        text = _strip_model_reasoning(candidate)
        try:
            parsed = json.loads(text)
        except ValueError:
            parsed = _extract_json_value_from_text(text)
            if parsed is None:
                return [_plain_text_card(text, expected_card_type=expected_card_type)]
        return _parse_cards_candidate(parsed, expected_card_type=expected_card_type)
    return []


def _cards_with_default_citations(
    cards: list[dict[str, Any]],
    citations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not cards or not citations:
        return cards
    public_citations = [_public_citation(item) for item in citations]
    enriched: list[dict[str, Any]] = []
    for card in cards:
        if isinstance(card.get("citations"), list) and card["citations"]:
            enriched.append(card)
        else:
            enriched.append({**card, "citations": public_citations})
    return enriched


def _strip_model_reasoning(text: str) -> str:
    stripped = text.strip()
    while stripped.startswith("<think>"):
        closing = stripped.find("</think>")
        if closing < 0:
            break
        stripped = stripped[closing + len("</think>") :].strip()
    return stripped


def _extract_json_value_from_text(text: str) -> Any | None:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.removeprefix("```json").removeprefix("```").strip()
        if stripped.endswith("```"):
            stripped = stripped[:-3].strip()
    for opener, closer in (("{", "}"), ("[", "]")):
        start = stripped.find(opener)
        end = stripped.rfind(closer)
        if start >= 0 and end > start:
            try:
                return json.loads(stripped[start : end + 1])
            except ValueError:
                continue
    return None


def _plain_text_card(text: str, *, expected_card_type: str | None = None) -> dict[str, Any]:
    """Wrap non-JSON model text without generating replacement content."""
    lines = [line.strip(" \t\r\n#*-") for line in text.splitlines() if line.strip()]
    title = lines[0] if lines else text.strip()
    subtitle = lines[1] if len(lines) > 1 else ""
    body = "\n".join(lines[2:]).strip() if len(lines) > 2 else text.strip()
    return {
        "type": (expected_card_type or "text").strip() or "text",
        "title": title[:80],
        "subtitle": subtitle[:120],
        "days": [],
        "items": [{"label": "正文", "content": body}],
        "qrcode_url": "",
        "citations": [],
    }


def _cards_have_renderable_content(cards: list[dict[str, Any]]) -> bool:
    for card in cards:
        if str(card.get("title") or "").strip():
            return True
        if str(card.get("subtitle") or "").strip():
            return True
        if card.get("items"):
            return True
        if card.get("days"):
            return True
        if card.get("study_material"):
            return True
    return False


def _dify_metadata(body: dict[str, Any]) -> dict[str, Any]:
    raw_data = body.get("data")
    data: dict[str, Any] = raw_data if isinstance(raw_data, dict) else {}
    return {
        "workflowRunId": data.get("workflow_run_id"),
        "taskId": body.get("task_id") or data.get("task_id"),
        "elapsedTime": data.get("elapsed_time"),
        "totalTokens": data.get("total_tokens"),
    }


def _generate_local(
    *,
    inputs: dict[str, Any],
    card_sequence: list[str],
    citations: list[dict[str, Any]],
) -> ModelGatewayResult:
    exam_name = str(inputs.get("examName") or inputs.get("exam_name") or "考试")
    exam_date = str(inputs.get("examDate") or inputs.get("exam_date") or "")
    target = str(inputs.get("targetAudience") or inputs.get("target_audience") or "备考人群")
    theme = str(inputs.get("theme") or "备考规划")
    sequence = card_sequence or ["cover", "plan", "notice", "cta"]
    source_hint = citations[0]["heading"] if citations else "待补充引用"
    public_citations = [_public_citation(item) for item in citations]
    if str(inputs.get("contentGoal") or "") == "resource_lead":
        lead_assets = _list_input(inputs, "leadAssets")
        asset_names = [str(item).strip() for item in lead_assets if str(item).strip()] or [
            "三色笔记",
            "高频考点 PDF",
            "30 天打卡表",
            "历年真题解析",
        ]
        comment_keyword = str(inputs.get("commentKeyword") or "资料")
        script_nodes = _list_input(inputs, "scriptNodes")
        cards: list[dict[str, Any]] = []
        for index, card_type in enumerate(sequence, start=1):
            slot = ""
            if index - 1 < len(script_nodes) and isinstance(script_nodes[index - 1], dict):
                slot = str(script_nodes[index - 1].get("id") or script_nodes[index - 1].get("label") or "")
            title = f"{exam_name}资料别乱买，这几份打印出来直接用" if index == 1 else ""
            subtitle = f"面向{target}，用资料诱饵承接评论/私信/收藏；专业内容只做信任背书。"
            items = [{"label": name, "content": "系统推荐，可由运营按实际资料名称修改"} for name in asset_names[:5]]
            if card_type == "priority":
                items = [
                    {"label": "高频点", "content": source_hint},
                    {"label": "专业边界", "content": "只做信任背书，不展开完整讲义"},
                    {"label": "使用方式", "content": "配合资料清单和真题解析复盘"},
                ]
            elif card_type == "notice":
                items = [
                    {"label": "痛点", "content": "资料太散、时间太碎，不知道先背哪里"},
                    {"label": "风险", "content": "不要堆资料，不要承诺官方资料或押题必中"},
                ]
            cards.append(
                {
                    "type": card_type,
                    "structureSlot": slot,
                    "title": title,
                    "subtitle": subtitle,
                    "body": f"围绕{asset_names[0]}等资料组织内容，目标是生成 80%+ 可用成稿。",
                    "cta": f"先收藏，评论“{comment_keyword}”领取资料清单；需要完整清单可以私信。",
                    "days": [],
                    "items": items,
                    "qrcode_url": "",
                    "citations": public_citations,
                    "auditFlags": ["不得写官方资料", "不得写押题必中或包过", "仅使用站内转化动作"],
                }
            )
        return ModelGatewayResult(
            provider="local",
            model_name="local-draft-generator",
            cards=cards,
            raw_metadata={"mode": "deterministic_p8_resource_lead"},
        )

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
                "citations": public_citations,
            }
        )
    return ModelGatewayResult(
        provider="local",
        model_name="local-draft-generator",
        cards=cards,
        raw_metadata={"mode": "deterministic_mvp"},
    )


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
