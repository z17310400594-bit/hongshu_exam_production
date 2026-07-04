"""Prompt contract for Xi Yao 1 condensed handout generation."""

from __future__ import annotations

import json
from typing import Any

SYSTEM_PROMPT = """你是执业药师考试教研助理。
你只能基于输入的章节证据包生成内容。
不得编造教材页码、讲义页码、真题年份、题号、答案。
不得输出押题、今年必考、稳过、保过等预测性表达。
如果证据不足，写入 reviewWarnings，不要强行总结为确定结论。
输出必须是一个合法 JSON 对象。
不要输出 Markdown。
不要输出代码块。
不要输出解释说明。"""


def build_user_prompt(evidence_pack: dict[str, Any]) -> str:
    schema = {
        "subjectCode": "xi_yao_1",
        "chapterCode": evidence_pack.get("chapterCode", ""),
        "title": evidence_pack.get("chapterTitle", ""),
        "summary": "本章短摘要",
        "status": "ready",
        "content": {
            "sourceSummary": ["说明原始材料覆盖范围"],
            "condensedBody": ["浓缩讲义正文，分段输出"],
            "learningGoals": ["学习目标"],
            "corePoints": [{"name": "考点名", "content": "考点解释"}],
            "typicalQuestionPatterns": ["典型问法"],
            "reviewWarnings": ["待人工复核项"],
        },
        "sources": [
            {"sourceType": "textbook", "sourceTitle": "来源标题", "page": "p1", "quote": "短引用或摘要"}
        ],
        "examEvidence": [{"year": 2025, "questionNo": "Q2", "summary": "问法摘要"}],
        "feedback": {"status": None, "note": ""},
    }
    return "\n".join(
        [
            "请基于以下章节证据包生成西药一章节浓缩讲义 JSON。",
            "输出字段必须匹配这个结构：",
            json.dumps(schema, ensure_ascii=False, indent=2),
            "章节证据包：",
            json.dumps(evidence_pack, ensure_ascii=False, indent=2),
        ]
    )
