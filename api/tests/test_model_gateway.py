"""P5/P7 model gateway contract tests."""

from __future__ import annotations

import json

from api.config import settings
from api.services.model_gateway import (
    ModelGatewayError,
    _cards_for_requested_type,
    _cards_have_renderable_content,
    _dify_workflow_endpoint,
    _dify_workflow_payload,
    _extract_cards_from_dify_response,
    _facts_brief_from_citations,
    _generate_local,
    _generate_with_dify,
    _model_gateway_timeout,
)


def test_dify_workflow_endpoint_accepts_base_url_with_or_without_v1():
    assert _dify_workflow_endpoint("https://api.dify.ai") == "https://api.dify.ai/v1/workflows/run"
    assert _dify_workflow_endpoint("https://api.dify.ai/v1") == "https://api.dify.ai/v1/workflows/run"
    assert _dify_workflow_endpoint("https://dify.example.com/v1/") == "https://dify.example.com/v1/workflows/run"


def test_model_gateway_timeout_can_be_disabled(monkeypatch):
    monkeypatch.setattr(settings, "model_gateway_timeout_seconds", 0)
    assert _model_gateway_timeout() is None

    monkeypatch.setattr(settings, "model_gateway_timeout_seconds", -1)
    assert _model_gateway_timeout() is None

    monkeypatch.setattr(settings, "model_gateway_timeout_seconds", 600)
    assert _model_gateway_timeout() == 600


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
    generation_inputs = json.loads(inputs["generationInputs"])
    assert generation_inputs["examName"] == "示例考试"
    assert generation_inputs["sourcePack"]["requestedCards"] == ["cover", "plan"]
    assert json.loads(inputs["cardSequence"]) == ["cover", "plan"]
    assert json.loads(inputs["citations"]) == []
    assert "合成测试引用" in inputs["factsBrief"]


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


def test_dify_cards_are_filtered_to_requested_single_card_type():
    cards = _cards_for_requested_type(
        [
            {"type": "cover", "title": "封面标题"},
            {"type": "plan", "title": "计划标题"},
            {"type": "plan", "title": "额外计划标题"},
        ],
        expected_card_type="plan",
    )

    assert cards == [
        {
            "type": "plan",
            "title": "计划标题",
            "subtitle": "",
            "days": [],
            "items": [],
            "qrcode_url": "",
            "citations": [],
        }
    ]


def test_dify_cards_without_type_are_bound_to_requested_card_type():
    cards = _cards_for_requested_type(
        [{"title": "模型返回了内容但漏了类型"}],
        expected_card_type="notice",
    )

    assert cards == [
        {
            "type": "notice",
            "title": "模型返回了内容但漏了类型",
            "subtitle": "",
            "days": [],
            "items": [],
            "qrcode_url": "",
            "citations": [],
        }
    ]


def test_dify_card_shape_is_normalized_for_frontend_rendering():
    cards = _cards_for_requested_type(
        [
            {
                "type": "plan",
                "title": "执业药师考前30天冲刺规划",
                "days": [
                    {"days": "第1-10天", "phase": "基础速通"},
                    {"label": "考前99天-考前50天：强化突破", "items": ["攻克药代动力学", "整理错题本"]},
                ],
                "items": [
                    "第1-10天：快速过一遍药物化学结构与命名",
                    {"text": "AUC代表药时曲线下面积，注意单位换算"},
                ],
                "study_material": [
                    {"title": "执业药师内部教辅考点摘录", "assetCode": "P2_PHARMACIST_INTERNAL_KP_NOTES"},
                    "P2 执业药师内部教辅考点摘录",
                ],
            }
        ],
        expected_card_type="plan",
    )

    assert cards[0]["days"] == [
        {"date": "第1-10天", "weekday": "", "task": "基础速通", "duration": ""},
        {
            "date": "考前99天-考前50天：强化突破",
            "weekday": "",
            "task": "攻克药代动力学；整理错题本",
            "duration": "",
        },
    ]
    assert cards[0]["items"] == [
        {"label": "第1-10天", "content": "快速过一遍药物化学结构与命名"},
        {"label": "要点2", "content": "AUC代表药时曲线下面积，注意单位换算"},
    ]
    assert cards[0]["study_material"] == [
        {"module_title": "执业药师内部教辅考点摘录", "key_points": [], "memory_tips": []},
        {"module_title": "P2 执业药师内部教辅考点摘录", "key_points": [], "memory_tips": []},
    ]


def test_dify_plain_text_output_is_wrapped_as_requested_card_type():
    cards = _extract_cards_from_dify_response(
        {
            "data": {
                "outputs": {
                    "cards": [],
                    "result": '{"cards":[]}',
                    "text": "最后123天！执业药师AUC急救\n药一高频考点别再硬背\nAUC代表药时曲线下面积，复习时重点关注吸收程度与暴露量。",
                }
            }
        },
        expected_card_type="cover",
    )

    assert cards == [
        {
            "type": "cover",
            "title": "最后123天！执业药师AUC急救",
            "subtitle": "药一高频考点别再硬背",
            "days": [],
            "items": [{"label": "正文", "content": "AUC代表药时曲线下面积，复习时重点关注吸收程度与暴露量。"}],
            "qrcode_url": "",
            "citations": [],
        }
    ]


def test_dify_reasoning_text_is_removed_before_json_parsing():
    cards = _extract_cards_from_dify_response(
        {
            "data": {
                "outputs": {
                    "text": """
                    <think>
                    这里是模型思考过程，不能进入最终卡片。
                    </think>
                    {
                      "cards": [
                        {
                          "type": "cover",
                          "title": "最后123天AUC急救",
                          "subtitle": "药一高频考点别再硬背",
                          "items": [{"label": "重点", "content": "AUC代表药时曲线下面积。"}],
                          "days": [],
                          "citations": []
                        }
                      ]
                    }
                    """
                }
            }
        },
        expected_card_type="cover",
    )

    assert cards == [
        {
            "type": "cover",
            "title": "最后123天AUC急救",
            "subtitle": "药一高频考点别再硬背",
            "items": [{"label": "重点", "content": "AUC代表药时曲线下面积。"}],
            "days": [],
            "citations": [],
        }
    ]


def test_dify_nested_text_output_with_reasoning_is_parsed():
    cards = _extract_cards_from_dify_response(
        {
            "data": {
                "outputs": {
                    "text": {
                        "text": """
                        <think>
                        模型思考过程不应该进入前端。
                        </think>
                        {
                          "cards": [
                            {
                              "type": "cover",
                              "title": "非科班执业药师冲刺计划",
                              "subtitle": "按这三阶段走，别再散学",
                              "items": ["先建框架", "再刷错题"],
                              "days": [],
                              "citations": []
                            },
                            {
                              "type": "plan",
                              "title": "三阶段学习计划",
                              "subtitle": "每天照着做",
                              "items": [],
                              "days": [
                                {"date": "第1-10天", "task": "建立框架", "duration": "10天"},
                                {"date": "第11-20天", "task": "专题突破", "duration": "10天"},
                                {"date": "第21-30天", "task": "刷题复盘", "duration": "10天"}
                              ],
                              "citations": []
                            }
                          ]
                        }
                        """
                    }
                }
            }
        }
    )

    assert [card["type"] for card in cards] == ["cover", "plan"]
    assert cards[0]["title"] == "非科班执业药师冲刺计划"
    assert cards[1]["days"][0]["task"] == "建立框架"


def test_generate_with_dify_orchestrates_multi_card_requests_one_by_one(monkeypatch):
    monkeypatch.setattr(settings, "dify_api_url", "https://dify.example/v1")
    monkeypatch.setattr(settings, "dify_api_key", "test-key")
    monkeypatch.setattr(settings, "generation_orchestration_mode", "per_card")

    requested_sequences: list[list[str]] = []

    def fake_post_dify_workflow(*, endpoint: str, payload: dict, headers: dict) -> dict:
        assert endpoint == "https://dify.example/v1/workflows/run"
        assert headers["Authorization"] == "Bearer test-key"
        sequence = json.loads(payload["inputs"]["cardSequence"])
        requested_sequences.append(sequence)
        card_type = sequence[0]
        return {
            "data": {
                "workflow_run_id": f"run-{card_type}",
                "outputs": {
                    "cards": [
                        {
                            "type": card_type,
                            "title": f"{card_type} 标题",
                            "subtitle": "非空副标题",
                            "items": [{"label": "要点", "content": "非空内容"}],
                            "days": [],
                            "citations": [],
                        }
                    ]
                },
            }
        }

    monkeypatch.setattr("api.services.model_gateway._post_dify_workflow", fake_post_dify_workflow)

    result = _generate_with_dify(
        application_code="exam_article",
        output_type="card_set",
        certificate_code="c_demo",
        principal_code="org_teaching_materials",
        inputs={"examName": "示例考试"},
        card_sequence=["cover", "plan"],
        citations=[],
    )

    assert requested_sequences == [["cover"], ["plan"]]
    assert [card["type"] for card in result.cards] == ["cover", "plan"]
    assert result.raw_metadata["mode"] == "per_card_workflow"
    assert result.raw_metadata["requestedCardCount"] == 2
    assert [run["cardType"] for run in result.raw_metadata["runs"]] == ["cover", "plan"]


def test_generate_with_dify_v1_style_requests_group_card_set_once(monkeypatch):
    monkeypatch.setattr(settings, "dify_api_url", "https://dify.example/v1")
    monkeypatch.setattr(settings, "dify_api_key", "test-key")
    monkeypatch.setattr(settings, "generation_orchestration_mode", "v1_style")

    requested_sequences: list[list[str]] = []

    def fake_post_dify_workflow(*, endpoint: str, payload: dict, headers: dict) -> dict:
        assert endpoint == "https://dify.example/v1/workflows/run"
        assert headers["Authorization"] == "Bearer test-key"
        requested_sequences.append(json.loads(payload["inputs"]["cardSequence"]))
        source_pack = json.loads(payload["inputs"]["generationInputs"])["sourcePack"]
        assert source_pack["hookStrategy"]
        return {
            "data": {
                "workflow_run_id": "run-group",
                "outputs": {
                    "text": json.dumps(
                        {
                            "cards": [
                                {
                                    "type": "cover",
                                    "title": "最后123天执业药师这样冲",
                                    "subtitle": "非科班也能照着走的冲刺路线",
                                    "items": [{"label": "重点", "content": "先抓药代动力学"}],
                                    "days": [],
                                    "citations": [],
                                },
                                {
                                    "type": "plan",
                                    "title": "30天冲刺安排",
                                    "subtitle": "三阶段把重点啃下来",
                                    "items": [],
                                    "days": [
                                        {"date": "第1-10天", "task": "建立药一框架，重点看药代动力学", "duration": "每天2小时"},
                                        {"date": "第11-20天", "task": "突破药效学和药物剂型", "duration": "每天2小时"},
                                        {"date": "第21-30天", "task": "刷题复盘错题和公式", "duration": "每天2小时"},
                                    ],
                                    "citations": [],
                                },
                            ]
                        },
                        ensure_ascii=False,
                    )
                },
            }
        }

    monkeypatch.setattr("api.services.model_gateway._post_dify_workflow", fake_post_dify_workflow)

    citations = [
        {
            "assetCode": "A1",
            "assetTitle": "执业药师内部资料",
            "assetType": "textbook",
            "versionNo": 1,
            "fragmentCode": "F1",
            "heading": "药代动力学",
            "pageFrom": None,
            "pageTo": None,
            "assetConfidentiality": "internal",
            "content": "AUC代表药时曲线下面积。",
        }
    ]

    result = _generate_with_dify(
        application_code="exam_article",
        output_type="card_set",
        certificate_code="pharmacist_licensed",
        principal_code="org_teaching_materials",
        inputs={"examName": "执业药师职业资格考试"},
        card_sequence=["cover", "plan"],
        citations=citations,
    )

    assert requested_sequences == [["cover", "plan"]]
    assert [card["type"] for card in result.cards] == ["cover", "plan"]
    assert result.cards[0]["citations"][0]["assetCode"] == "A1"
    assert result.cards[1]["citations"][0]["assetTitle"] == "执业药师内部资料"
    assert result.raw_metadata["mode"] == "v1_style_group_workflow"
    assert result.raw_metadata["requestedCardCount"] == 2


def test_generate_with_dify_retries_then_fails_empty_requested_card(monkeypatch):
    monkeypatch.setattr(settings, "dify_api_url", "https://dify.example/v1")
    monkeypatch.setattr(settings, "dify_api_key", "test-key")
    monkeypatch.setattr(settings, "generation_orchestration_mode", "per_card")

    calls = 0

    def fake_post_dify_workflow(*, endpoint: str, payload: dict, headers: dict) -> dict:
        nonlocal calls
        calls += 1
        return {
            "data": {
                "outputs": {
                    "cards": [
                        {"type": "cover", "title": "", "subtitle": "", "items": [], "days": [], "citations": []}
                    ]
                }
            }
        }

    monkeypatch.setattr("api.services.model_gateway._post_dify_workflow", fake_post_dify_workflow)

    try:
        _generate_with_dify(
            application_code="exam_article",
            output_type="card_set",
            certificate_code="c_demo",
            principal_code="org_teaching_materials",
            inputs={"examName": "示例考试"},
            card_sequence=["cover"],
            citations=[],
        )
    except ModelGatewayError as exc:
        assert exc.code == "MODEL_GATEWAY_EMPTY_OUTPUT"
        assert "cover" in exc.message
    else:
        raise AssertionError("Expected empty Dify output to fail")

    assert calls == 4


def test_facts_brief_from_citations_makes_fact_boundary_explicit():
    brief = _facts_brief_from_citations(
        [
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
                "content": "只允许使用这段合成事实。",
            }
        ]
    )

    assert "V2 后端已完成权限过滤" in brief
    assert "只允许使用这段合成事实" in brief


def test_local_generator_supports_p8_resource_lead_structure():
    result = _generate_local(
        inputs={
            "examName": "执业药师",
            "examDate": "2026-10-18",
            "targetAudience": "宝妈备考",
            "contentGoal": "resource_lead",
            "leadAssets": ["三色笔记", "高频考点 PDF"],
            "commentKeyword": "药师资料",
            "scriptNodes": [
                {"id": "cover_hook", "label": "封面钩子", "cardType": "cover"},
                {"id": "resource_bait", "label": "资料诱饵", "cardType": "resources"},
            ],
        },
        card_sequence=["cover", "resources"],
        citations=[
            {
                "assetCode": "A1",
                "assetTitle": "执业药师资料",
                "assetType": "handout",
                "versionNo": 1,
                "fragmentCode": "F1",
                "heading": "高频资料",
                "pageFrom": 1,
                "pageTo": 1,
                "assetConfidentiality": "internal",
                "content": "资料片段",
            }
        ],
    )

    assert result.raw_metadata["mode"] == "deterministic_p8_resource_lead"
    assert [card["structureSlot"] for card in result.cards] == ["cover_hook", "resource_bait"]
    assert result.cards[0]["title"].startswith("执业药师资料别乱买")
    assert "药师资料" in result.cards[0]["cta"]
    assert "仅使用站内转化动作" in result.cards[0]["auditFlags"]


def test_dify_payload_embeds_p8_script_nodes_and_manual_brief_in_source_pack():
    payload = _dify_workflow_payload(
        application_code="exam_article",
        output_type="card_set",
        certificate_code="pharmacist_licensed",
        principal_code="org_teaching_materials",
        inputs={
            "examName": "执业药师",
            "contentGoal": "resource_lead",
            "structureTemplate": "resource_lead_v1",
            "leadAssets": ["三色笔记", "高频考点 PDF"],
            "commentKeyword": "药师资料",
            "conversionModes": ["comment", "collect"],
            "manualBrief": "专业内容只做信任背书",
            "scriptNodes": [
                {"id": "cover_hook", "label": "封面钩子", "purpose": "资料已整理", "cardType": "cover"},
                {"id": "receive_method", "label": "领取方式", "purpose": "评论关键词", "cardType": "cta"},
            ],
        },
        card_sequence=["cover", "cta"],
        citations=[],
    )

    generation_inputs = json.loads(payload["inputs"]["generationInputs"])
    source_pack = generation_inputs["sourcePack"]

    assert source_pack["contentGoal"] == "resource_lead"
    assert source_pack["scriptNodes"][0]["label"] == "封面钩子"
    assert source_pack["manualBrief"] == "专业内容只做信任背书"
    assert source_pack["commentKeyword"] == "药师资料"
