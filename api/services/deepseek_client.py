"""Small DeepSeek client for backend-only offline generation."""

from __future__ import annotations

import json
import re
from typing import Any

import requests

from api.config import settings


class DeepSeekClientError(RuntimeError):
    def __init__(self, code: str, message: str, raw_output: str = ""):
        super().__init__(message)
        self.code = code
        self.message = message
        self.raw_output = raw_output


def chat_json(*, system_prompt: str, user_prompt: str) -> tuple[dict[str, Any], str, str]:
    """Call DeepSeek chat completions and return parsed JSON, raw text, model."""
    if not settings.deepseek_api_key:
        raise DeepSeekClientError("DEEPSEEK_API_KEY_MISSING", "DEEPSEEK_API_KEY 未配置")
    if not settings.deepseek_model:
        raise DeepSeekClientError("DEEPSEEK_MODEL_MISSING", "DEEPSEEK_MODEL 未配置")

    base_url = settings.deepseek_base_url.rstrip("/")
    endpoint = f"{base_url}/chat/completions" if base_url.endswith("/v1") else f"{base_url}/v1/chat/completions"
    timeout = None if settings.deepseek_timeout_seconds <= 0 else settings.deepseek_timeout_seconds
    try:
        response = requests.post(
            endpoint,
            headers={"Authorization": f"Bearer {settings.deepseek_api_key}", "Content-Type": "application/json"},
            json={
                "model": settings.deepseek_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.2,
            },
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise DeepSeekClientError("DEEPSEEK_REQUEST_FAILED", "DeepSeek 请求失败") from exc

    try:
        body = response.json()
    except ValueError as exc:
        raise DeepSeekClientError("DEEPSEEK_RESPONSE_NOT_JSON", "DeepSeek 响应不是 JSON", response.text) from exc

    content = _extract_message_content(body)
    parsed = parse_json_object(content)
    return parsed, content, str(body.get("model") or settings.deepseek_model)


def parse_json_object(raw_output: str) -> dict[str, Any]:
    cleaned = re.sub(r"<think>.*?</think>", "", raw_output or "", flags=re.DOTALL).strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        cleaned = fence.group(1).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end >= start:
        cleaned = cleaned[start : end + 1]
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise DeepSeekClientError("DEEPSEEK_JSON_PARSE_ERROR", "DeepSeek 输出不是合法 JSON", raw_output) from exc
    if not isinstance(parsed, dict):
        raise DeepSeekClientError("DEEPSEEK_JSON_SCHEMA_ERROR", "DeepSeek 输出必须是 JSON 对象", raw_output)
    return parsed


def _extract_message_content(body: dict[str, Any]) -> str:
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        raise DeepSeekClientError("DEEPSEEK_EMPTY_RESPONSE", "DeepSeek 返回为空", json.dumps(body, ensure_ascii=False))
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise DeepSeekClientError("DEEPSEEK_EMPTY_RESPONSE", "DeepSeek 返回内容为空", json.dumps(body, ensure_ascii=False))
    return content
