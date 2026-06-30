"""P5/P7 model gateway contract tests."""

from __future__ import annotations

import json

from api.services.model_gateway import _cards_have_renderable_content, _dify_workflow_endpoint, _dify_workflow_payload


def test_dify_workflow_endpoint_accepts_base_url_with_or_without_v1():
    assert _dify_workflow_endpoint("https://api.dify.ai") == "https://api.dify.ai/v1/workflows/run"
    assert _dify_workflow_endpoint("https://api.dify.ai/v1") == "https://api.dify.ai/v1/workflows/run"
    assert _dify_workflow_endpoint("https://dify.example.com/v1/") == "https://dify.example.com/v1/workflows/run"


def test_dify_workflow_payload_serializes_paragraph_json_inputs():
    payload = _dify_workflow_payload(
        application_code="exam_article",
        output_type="card_set",
        certificate_code="synthetic_cert",
        principal_code="org_teaching_materials",
        inputs={"examName": "示例考试"},
        card_sequence=["cover", "plan"],
        citations=[
            {
                "assetCode": "A1",
                "assetTitle": "资料",
                "assetType": "policy",
                "versionNo": 1,
                "fragmentCode": "F1",
                "heading": "标题",
                "pageFrom": 1,
                "pageTo": 1,
                "assetConfidentiality": "public",
                "content": "合成测试引用",
            }
        ],
    )

    inputs = payload["inputs"]
    assert payload["response_mode"] == "blocking"
    assert payload["user"] == "org_teaching_materials"
    assert json.loads(inputs["generationInputs"]) == {"examName": "示例考试"}
    assert json.loads(inputs["cardSequence"]) == ["cover", "plan"]
    assert json.loads(inputs["citations"])[0]["assetCode"] == "A1"
    assert inputs["factsBrief"] == ""


def test_empty_dify_cards_are_not_renderable_content():
    assert _cards_have_renderable_content(
        [
            {"type": "cover", "title": "", "subtitle": "", "items": [], "days": [], "citations": [{"assetCode": "A1"}]},
            {"type": "plan", "title": "", "subtitle": "", "items": [], "days": [], "citations": [{"assetCode": "A1"}]},
        ]
    ) is False
    assert _cards_have_renderable_content(
        [{"type": "cover", "title": "示例标题", "subtitle": "", "items": [], "days": []}]
    ) is True
