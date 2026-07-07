"""WP09 fixtures — papers, questions, and question-KP mappings."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from db.tests.fixtures_wp08 import seed_knowledge_point, seed_source_asset


def seed_paper_source_asset(
    engine: Engine,
    *,
    asset_code: str,
    collection_code: str = "coll_internal",
) -> dict[str, Any]:
    return seed_source_asset(
        engine,
        asset_code=asset_code,
        title=f"{asset_code} 题库源文件",
        collection_code=collection_code,
        asset_type="paper",
        confidentiality="internal",
        fragments=[
            ("Q001", "section", "第 1 题来源", 1),
            ("Q002", "section", "第 2 题来源", 2),
            ("CASE01", "section", "案例题来源", 3),
        ],
    )


def seed_paper(
    engine: Engine,
    *,
    code: str,
    source_asset_code: str,
    title: str = "WP09 试卷",
    paper_type: str = "mock",
    certificate_code: str = "c_constructor_1",
    subject_code: str | None = "subj_constructor_mgmt",
    exam_year: int | None = 2026,
    owner_org_code: str = "org_teaching_materials",
    status: str = "draft",
    review_status: str = "approved",
    reviewed_by: str | None = "wp09_reviewer",
) -> dict[str, Any]:
    with engine.begin() as conn:
        row = conn.execute(
            text("""
                INSERT INTO assessment.paper (
                    code, paper_type, certificate_id, subject_id, exam_year,
                    source_asset_version_id, owner_org_id, title,
                    status, review_status, reviewed_by
                )
                SELECT :code, :paper_type, cert.id, subj.id, :exam_year,
                       av.id, org.id, :title,
                       :status, :review_status, :reviewed_by
                  FROM core.certificate cert
                  JOIN knowledge.asset a ON a.code = :source_asset_code
                  JOIN knowledge.asset_version av ON av.asset_id = a.id AND av.version_no = 1
                  JOIN iam.organization_unit org ON org.code = :owner_org_code
                  LEFT JOIN core.exam_subject subj ON subj.code = :subject_code
                 WHERE cert.code = :certificate_code
                RETURNING id, code, paper_type, certificate_id, subject_id, exam_year,
                          source_asset_version_id, owner_org_id, title,
                          status, review_status, reviewed_by
            """),
            {
                "code": code,
                "paper_type": paper_type,
                "certificate_code": certificate_code,
                "subject_code": subject_code,
                "exam_year": exam_year,
                "source_asset_code": source_asset_code,
                "owner_org_code": owner_org_code,
                "title": title,
                "status": status,
                "review_status": review_status,
                "reviewed_by": reviewed_by,
            },
        ).fetchone()
    if row is None:
        raise ValueError("paper dependencies not found")
    return dict(row._mapping)


def seed_question(
    engine: Engine,
    *,
    paper_id: int,
    question_no: str,
    question_type: str,
    content: str,
    answer: Any,
    source_fragment_id: int | None = None,
    options: dict[str, Any] | None = None,
    analysis: str | None = None,
    difficulty: int = 2,
    review_status: str = "approved",
) -> dict[str, Any]:
    with engine.begin() as conn:
        row = conn.execute(
            text("""
                INSERT INTO assessment.question (
                    paper_id, source_fragment_id, question_no, question_type,
                    content, options, answer, analysis, difficulty, review_status
                )
                VALUES (
                    :paper_id, :source_fragment_id, :question_no, :question_type,
                    :content, CAST(:options_json AS jsonb), CAST(:answer_json AS jsonb),
                    :analysis, :difficulty, :review_status
                )
                RETURNING id, paper_id, source_fragment_id, question_no, question_type,
                          content, options, answer, analysis, difficulty, review_status
            """),
            {
                "paper_id": paper_id,
                "source_fragment_id": source_fragment_id,
                "question_no": question_no,
                "question_type": question_type,
                "content": content,
                "options_json": None if options is None else json.dumps(options, ensure_ascii=False),
                "answer_json": json.dumps(answer, ensure_ascii=False),
                "analysis": analysis,
                "difficulty": difficulty,
                "review_status": review_status,
            },
        ).fetchone()
    if row is None:
        raise RuntimeError("question insert failed")
    return dict(row._mapping)


def seed_question_knowledge_point(
    engine: Engine,
    *,
    question_id: int,
    kp_code: str,
    role: str = "primary",
    score_weight: Decimal | int | str | None = Decimal("1"),
) -> dict[str, Any]:
    with engine.begin() as conn:
        row = conn.execute(
            text("""
                INSERT INTO assessment.question_knowledge_point (
                    question_id, kp_id, role, score_weight
                )
                SELECT :question_id, kp.id, :role, :score_weight
                  FROM knowledge.knowledge_point kp
                 WHERE kp.code = :kp_code
                RETURNING question_id, kp_id, role, score_weight
            """),
            {
                "question_id": question_id,
                "kp_code": kp_code,
                "role": role,
                "score_weight": None if score_weight is None else Decimal(str(score_weight)),
            },
        ).fetchone()
    if row is None:
        raise ValueError("knowledge point not found")
    return dict(row._mapping)


__all__ = [
    "seed_knowledge_point",
    "seed_paper",
    "seed_paper_source_asset",
    "seed_question",
    "seed_question_knowledge_point",
]
