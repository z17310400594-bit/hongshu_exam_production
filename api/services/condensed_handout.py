"""Xi Yao 1 condensed handout MVP service.

The public API is read-first: frontend users review already prepared chapter
drafts and submit business feedback. Offline generation can later write the
same JSON shape into generation.output.
"""

from __future__ import annotations

import copy
import json
import socket
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from api.config import settings

SUBJECT_CODE = "xi_yao_1"
APPLICATION_CODE = "xi_yao_1_condensed_handout"
OUTPUT_TYPE = "textbook_draft"
PROMPT_VERSION = "xi_yao_1_condensed_handout_v1"
VALID_FEEDBACK_STATUSES = {"usable", "needs_revision", "not_usable"}
FORBIDDEN_OUTPUT_TERMS = ("押题", "今年必考", "稳过", "保过")


class CondensedHandoutError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


SAMPLE_CHAPTERS: list[dict[str, Any]] = [
    {
        "subjectCode": SUBJECT_CODE,
        "chapterCode": "chapter_01",
        "title": "第一章 药品与药品质量体系",
        "summary": "概念、药品名称、质量标准、稳定性与检验",
        "status": "ready",
        "content": {
            "sourceSummary": [
                "本章原始材料来自 2026 教材第一章与 2026 深度精讲第一章，内容覆盖药物与药品定义、药品名称、药品质量属性、药典检验和稳定性试验。",
                "历年真题中，药品商品名、药品贮藏术语、稳定性试验等内容出现过直接或变形问法。",
            ],
            "condensedBody": [
                "本章不要死背长定义，重点抓“用药目的、质量要求、名称体系、贮藏与检验”四条线。",
                "药品名称中，通用名称用于识别活性成分，化学名称用于准确表达结构，商品名称面向具体产品和企业品牌，可注册和申请保护。",
                "质量标准部分重点区分鉴别、检查、含量测定。稳定性试验常见问法集中在影响因素试验、加速试验、长期试验的目的和条件。",
            ],
            "learningGoals": [
                "区分药物、药品、剂型、制剂、通用名称、商品名称和化学名称。",
                "掌握药品质量属性、质量标准、稳定性和药典检验项目的基本判断。",
                "识别“避光/遮光”“密闭/密封”等概念偷换。",
            ],
            "corePoints": [
                {"name": "药品名称", "content": "通用名称、化学名称、商品名称的用途和保护属性。"},
                {"name": "药品贮藏", "content": "避光、遮光、密闭、密封、阴凉处等术语容易被交换。"},
                {"name": "质量检验", "content": "鉴别、检查、含量测定各自解决的问题不同。"},
                {"name": "稳定性试验", "content": "影响因素、加速、长期试验的目的不同。"},
            ],
            "typicalQuestionPatterns": [
                "给出药品商品名、通用名、化学名的描述，判断哪项正确。",
                "给出贮藏术语，判断“遮光/避光”“密闭/密封”是否混淆。",
                "给出稳定性试验描述，判断属于影响因素、加速还是长期试验。",
            ],
            "reviewWarnings": [
                "部分真题解析来源为回忆版，年份和题号需抽检。",
                "质量标准相关表述需与最新教材页码再核对。",
            ],
        },
        "sources": [
            {"sourceType": "textbook", "sourceTitle": "2026西药一教材", "page": "p7", "quote": "商品名称由制药企业选择，和商标一样可以注册和申请专利保护。"},
            {"sourceType": "handout", "sourceTitle": "2026西药一讲义", "page": "p8", "quote": "考点：3 大药品名称：通用名称、化学名称和商品名称。"},
            {"sourceType": "handout", "sourceTitle": "2026西药一讲义", "page": "p25", "quote": "考点：药品稳定性试验。"},
        ],
        "examEvidence": [
            {"year": 2024, "questionNo": "Q3", "summary": "关于药品商品名的说法。"},
            {"year": 2023, "questionNo": "Q3", "summary": "关于药品稳定性试验方法的说法。"},
            {"year": 2022, "questionNo": "Q4", "summary": "根据《中国药典》药品贮存规定进行判断。"},
        ],
        "feedback": {"status": "needs_revision", "note": ""},
    },
    {
        "subjectCode": SUBJECT_CODE,
        "chapterCode": "chapter_03",
        "title": "第三章 药物的体内过程",
        "summary": "吸收、分布、代谢、排泄、药动学参数",
        "status": "ready",
        "content": {
            "sourceSummary": [
                "本章原始材料来自 2026 教材第三章与 2026 深度精讲第三章，内容覆盖 ADME、生物利用度、生物等效性、药动学参数及临床意义。",
                "历年真题中，生物半衰期、生物等效性、清除率、表观分布容积等内容有直接考查。",
            ],
            "condensedBody": [
                "药物的体内过程可以按 ADME 理解：吸收决定药物进入体循环的速度与程度，分布决定药物在血液和组织间的去向，代谢和排泄共同影响消除。",
                "生物半衰期是体内药量或血药浓度降低一半所需时间，反映药物从体内消除的快慢。不要理解成药效下降一半、吸收一半或肾脏排出一半。",
                "生物利用度关注药物被吸收入体循环的速度和程度；生物等效性研究常用于评价仿制药与参比制剂在吸收程度和速度上的一致性。",
            ],
            "learningGoals": [
                "掌握吸收、分布、代谢、排泄的基本路径和影响因素。",
                "区分生物半衰期、清除率、表观分布容积、生物利用度和生物等效性。",
                "识别真题中对“定义换说法”和“参数临床意义”的考查。",
            ],
            "corePoints": [
                {"name": "生物半衰期", "content": "血药浓度降低一半所需时间，反映消除快慢。"},
                {"name": "清除率", "content": "单位时间内从机体清除的含药血浆体积。"},
                {"name": "表观分布容积", "content": "体内药量与血药浓度之间的比例常数。"},
                {"name": "生物等效性", "content": "重点看研究设计、参比制剂和 PK 参数判断。"},
            ],
            "typicalQuestionPatterns": [
                "给出某药半衰期，问其含义。",
                "给出一致性评价或仿制药情境，判断生物等效性研究要求。",
                "给出药动学参数描述，判断清除率、表观分布容积、米氏常数。",
            ],
            "reviewWarnings": [
                "生物等效性研究要求需确认与当前考试教材表述一致。",
                "真题佐证可说明“曾考查”，不能直接说明“高频必考”。",
            ],
        },
        "sources": [
            {"sourceType": "textbook", "sourceTitle": "2026西药一教材", "page": "p78", "quote": "生物半衰期指体内药量或血药浓度降低一半所需要的时间。"},
            {"sourceType": "handout", "sourceTitle": "2026西药一讲义", "page": "p56", "quote": "考点：生物半衰期 t1/2 及临床意义。"},
            {"sourceType": "handout", "sourceTitle": "2026西药一讲义", "page": "p66", "quote": "考点：生物等效性研究的基本要求。"},
        ],
        "examEvidence": [
            {"year": 2025, "questionNo": "Q2", "summary": "关于瑞舒伐他汀钙生物半衰期为 19 小时的说法。"},
            {"year": 2025, "questionNo": "Q3", "summary": "关于生物等效性研究基本要求的说法。"},
            {"year": 2022, "questionNo": "Q20", "summary": "关于药物动力学参数的说法。"},
        ],
        "feedback": {"status": "usable", "note": ""},
    },
    {
        "subjectCode": SUBJECT_CODE,
        "chapterCode": "chapter_09",
        "title": "第九章 皮肤和黏膜给药途径制剂与临床应用",
        "summary": "气雾剂、贴剂、眼用制剂、栓剂、灌肠剂",
        "status": "locked",
        "content": {
            "sourceSummary": [],
            "condensedBody": [],
            "learningGoals": [],
            "corePoints": [],
            "typicalQuestionPatterns": [],
            "reviewWarnings": ["备选章节，第一轮 MVP 不要求交付。"],
        },
        "sources": [],
        "examEvidence": [],
        "feedback": {"status": None, "note": ""},
    },
]


def list_condensed_handout_chapters(engine: Engine, *, subject_code: str = SUBJECT_CODE) -> dict[str, Any]:
    chapters = _chapters_with_db_overrides(engine, subject_code=subject_code)
    return {
        "subjectCode": subject_code,
        "chapters": [
            {
                "chapterCode": chapter["chapterCode"],
                "title": chapter["title"],
                "summary": chapter.get("summary", ""),
                "status": chapter.get("status", "ready"),
                "feedbackStatus": chapter.get("feedback", {}).get("status"),
            }
            for chapter in chapters
        ],
    }


def get_condensed_handout_chapter(engine: Engine, *, chapter_code: str, subject_code: str = SUBJECT_CODE) -> dict[str, Any]:
    chapter = _chapter_with_db_override(engine, chapter_code=chapter_code, subject_code=subject_code)
    if chapter is None:
        raise CondensedHandoutError("CHAPTER_NOT_FOUND", "章节不存在")
    return _detail_response(chapter)


def save_condensed_handout_feedback(
    engine: Engine,
    *,
    chapter_code: str,
    status: str,
    note: str,
    principal_code: str,
    subject_code: str = SUBJECT_CODE,
) -> dict[str, Any]:
    if status not in VALID_FEEDBACK_STATUSES:
        raise CondensedHandoutError("INVALID_FEEDBACK_STATUS", "反馈状态不支持")
    chapter = _chapter_with_db_override(engine, chapter_code=chapter_code, subject_code=subject_code)
    if chapter is None or chapter.get("status") == "locked":
        raise CondensedHandoutError("CHAPTER_NOT_FOUND", "章节不存在或未开放")

    updated = _detail_response(chapter)
    updated["feedback"] = {"status": status, "note": note.strip()}
    _upsert_chapter_output(engine, chapter=updated, principal_code=principal_code)
    return {"chapterCode": chapter_code, "feedback": updated["feedback"]}


def save_generated_handout_chapter(
    engine: Engine,
    *,
    chapter: dict[str, Any],
    principal_code: str,
    model_provider: str,
    model_name: str,
) -> dict[str, Any]:
    validate_handout_output(chapter)
    normalized = _normalize_chapter(chapter)
    _insert_chapter_output(
        engine,
        chapter=normalized,
        principal_code=principal_code,
        model_provider=model_provider,
        model_name=model_name,
        model_route="approved_external",
        prompt_version=PROMPT_VERSION,
    )
    return {"chapterCode": normalized["chapterCode"], "status": normalized.get("status", "ready")}


def validate_handout_output(data: dict[str, Any]) -> None:
    required_top = ["chapterCode", "title", "content", "sources", "examEvidence", "feedback"]
    missing = [key for key in required_top if key not in data]
    if missing:
        raise CondensedHandoutError("OUTPUT_SCHEMA_ERROR", f"生成结果缺少字段: {', '.join(missing)}")
    content = data["content"]
    if not isinstance(content, dict):
        raise CondensedHandoutError("OUTPUT_SCHEMA_ERROR", "生成结果 content 必须是对象")
    required_content = ["sourceSummary", "condensedBody", "learningGoals", "corePoints", "typicalQuestionPatterns", "reviewWarnings"]
    missing_content = [key for key in required_content if key not in content]
    if missing_content:
        raise CondensedHandoutError("OUTPUT_SCHEMA_ERROR", f"生成结果 content 缺少字段: {', '.join(missing_content)}")
    serialized = json.dumps(data, ensure_ascii=False)
    forbidden = [term for term in FORBIDDEN_OUTPUT_TERMS if term in serialized]
    if forbidden:
        raise CondensedHandoutError("OUTPUT_POLICY_ERROR", f"生成结果包含禁止表达: {', '.join(forbidden)}")


def _chapters_with_db_overrides(engine: Engine, *, subject_code: str) -> list[dict[str, Any]]:
    by_code = {chapter["chapterCode"]: copy.deepcopy(chapter) for chapter in SAMPLE_CHAPTERS}
    if not _should_read_database(engine):
        return [by_code[chapter["chapterCode"]] for chapter in SAMPLE_CHAPTERS]
    for row in _load_latest_outputs(engine, subject_code=subject_code):
        content = dict(row.content)
        validate_handout_output(content)
        by_code[content["chapterCode"]] = _normalize_chapter(content)
    return [by_code[chapter["chapterCode"]] for chapter in SAMPLE_CHAPTERS if chapter["chapterCode"] in by_code]


def _chapter_with_db_override(engine: Engine, *, chapter_code: str, subject_code: str) -> dict[str, Any] | None:
    if not _should_read_database(engine):
        for chapter in SAMPLE_CHAPTERS:
            if chapter["chapterCode"] == chapter_code:
                return copy.deepcopy(chapter)
        return None
    row = _load_latest_output(engine, chapter_code=chapter_code, subject_code=subject_code)
    if row is not None:
        content = dict(row.content)
        validate_handout_output(content)
        return _normalize_chapter(content)
    for chapter in SAMPLE_CHAPTERS:
        if chapter["chapterCode"] == chapter_code:
            return copy.deepcopy(chapter)
    return None


def _load_latest_outputs(engine: Engine, *, subject_code: str):
    with engine.connect() as conn:
        return conn.execute(
            text("""
                SELECT DISTINCT ON (o.content ->> 'chapterCode')
                       o.id, o.content
                  FROM generation.output o
                  JOIN generation.run r ON r.id = o.generation_run_id
                 WHERE r.application_code = :application_code
                   AND o.output_type = :output_type
                   AND coalesce(o.content ->> 'subjectCode', :subject_code) = :subject_code
                 ORDER BY o.content ->> 'chapterCode', o.id DESC
            """),
            {"application_code": APPLICATION_CODE, "output_type": OUTPUT_TYPE, "subject_code": subject_code},
        ).fetchall()


def _load_latest_output(engine: Engine, *, chapter_code: str, subject_code: str):
    with engine.connect() as conn:
        return conn.execute(
            text("""
                SELECT o.id, o.content
                  FROM generation.output o
                  JOIN generation.run r ON r.id = o.generation_run_id
                 WHERE r.application_code = :application_code
                   AND o.output_type = :output_type
                   AND coalesce(o.content ->> 'subjectCode', :subject_code) = :subject_code
                   AND o.content ->> 'chapterCode' = :chapter_code
                 ORDER BY o.id DESC
                 LIMIT 1
            """),
            {
                "application_code": APPLICATION_CODE,
                "output_type": OUTPUT_TYPE,
                "subject_code": subject_code,
                "chapter_code": chapter_code,
            },
        ).fetchone()


def _upsert_chapter_output(engine: Engine, *, chapter: dict[str, Any], principal_code: str) -> None:
    validate_handout_output(chapter)
    if not _should_read_database(engine):
        raise CondensedHandoutError("DATABASE_UNAVAILABLE", "数据库不可用，反馈暂未保存")
    _insert_chapter_output(
        engine,
        chapter=chapter,
        principal_code=principal_code,
        model_provider="local",
        model_name="review-feedback",
        model_route="internal",
        prompt_version=PROMPT_VERSION,
    )


def _insert_chapter_output(
    engine: Engine,
    *,
    chapter: dict[str, Any],
    principal_code: str,
    model_provider: str,
    model_name: str,
    model_route: str,
    prompt_version: str,
) -> None:
    with engine.begin() as conn:
        run = conn.execute(
            text("""
                INSERT INTO generation.run (
                    application_code, user_code, model_provider, model_name,
                    model_route, prompt_version, confidentiality, status
                )
                VALUES (
                    :application_code, :user_code, :model_provider, :model_name,
                    :model_route, :prompt_version, 'internal', 'succeeded'
                )
                RETURNING id
            """),
            {
                "application_code": APPLICATION_CODE,
                "user_code": principal_code,
                "model_provider": model_provider,
                "model_name": model_name,
                "model_route": model_route,
                "prompt_version": prompt_version,
            },
        ).fetchone()
        if run is None:
            raise RuntimeError("generation run insert failed")
        conn.execute(
            text("""
                INSERT INTO generation.output (
                    generation_run_id, output_type, content, confidentiality, status
                )
                VALUES (:run_id, :output_type, CAST(:content_json AS jsonb), 'internal', 'draft')
            """),
            {
                "run_id": run.id,
                "output_type": OUTPUT_TYPE,
                "content_json": json.dumps(chapter, ensure_ascii=False),
            },
        )


def _normalize_chapter(chapter: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(chapter)
    normalized.setdefault("subjectCode", SUBJECT_CODE)
    normalized.setdefault("summary", "")
    normalized.setdefault("status", "ready")
    normalized.setdefault("feedback", {"status": None, "note": ""})
    return normalized


def _detail_response(chapter: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_chapter(chapter)
    return {
        "subjectCode": normalized["subjectCode"],
        "chapterCode": normalized["chapterCode"],
        "title": normalized["title"],
        "summary": normalized.get("summary", ""),
        "status": normalized.get("status", "ready"),
        "content": normalized["content"],
        "sources": normalized["sources"],
        "examEvidence": normalized["examEvidence"],
        "feedback": normalized["feedback"],
    }


def _database_port_open(engine: Engine, *, timeout_seconds: float = 0.3) -> bool:
    url = getattr(engine, "url", None)
    host = getattr(url, "host", None)
    port = getattr(url, "port", None)
    if not host or not port:
        return True
    try:
        with socket.create_connection((host, int(port)), timeout=timeout_seconds):
            return True
    except OSError:
        return False


def _should_read_database(engine: Engine) -> bool:
    return settings.condensed_handout_use_db and _database_port_open(engine)
