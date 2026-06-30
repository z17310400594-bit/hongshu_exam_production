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

    endpoint = f"{settings.dify_api_url.rstrip('/')}/v1/workflows/run"
    payload = {
        "inputs": {
            "applicationCode": application_code,
            "outputType": output_type,
            "certificateCode": certificate_code or "",
            "generationInputs": inputs,
            "cardSequence": card_sequence,
            "citations": [_public_citation(item) for item in citations],
        },
        "response_mode": "blocking",
        "user": principal_code,
    }
    headers = {
        "Authorization": f"Bearer {settings.dify_api_key}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=settings.model_gateway_timeout_seconds) as client:
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

    cards = _extract_cards_from_dify_response(body)
    if not cards:
        raise ModelGatewayError(
            code="MODEL_GATEWAY_EMPTY_OUTPUT",
            message="Model gateway returned no cards",
            provider="dify",
        )

    return ModelGatewayResult(
        provider="dify",
        model_name="dify-workflow",
        cards=cards,
        raw_metadata=_dify_metadata(body),
    )


def _extract_cards_from_dify_response(body: dict[str, Any]) -> list[dict[str, Any]]:
    outputs = body.get("data", {}).get("outputs", {}) if isinstance(body.get("data"), dict) else {}
    candidates = [
        outputs.get("cards") if isinstance(outputs, dict) else None,
        outputs.get("result") if isinstance(outputs, dict) else None,
        outputs.get("text") if isinstance(outputs, dict) else None,
        body.get("answer"),
    ]
    for candidate in candidates:
        parsed = _parse_cards_candidate(candidate)
        if parsed:
            return parsed
    return []


def _parse_cards_candidate(candidate: Any) -> list[dict[str, Any]]:
    if isinstance(candidate, list) and all(isinstance(item, dict) for item in candidate):
        return candidate
    if isinstance(candidate, dict):
        cards = candidate.get("cards")
        if isinstance(cards, list) and all(isinstance(item, dict) for item in cards):
            return cards
    if isinstance(candidate, str) and candidate.strip():
        try:
            parsed = json.loads(candidate)
        except ValueError:
            return [
                {
                    "type": "text",
                    "title": "模型生成结果",
                    "subtitle": "",
                    "days": [],
                    "items": [{"label": "正文", "content": candidate.strip()}],
                    "qrcode_url": "",
                    "citations": [],
                }
            ]
        return _parse_cards_candidate(parsed)
    return []


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

    cards: list[dict[str, Any]] = []
    public_citations = [_public_citation(item) for item in citations]
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
