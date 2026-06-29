"""Question bank service — WP09 MVP paper/question lookup and stats."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from api.auth import check_collection_access


def _to_float(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def get_paper_questions(
    engine: Engine,
    *,
    paper_code: str,
    principal_type: str,
    principal_code: str,
) -> dict[str, Any]:
    """Return approved questions for one governed paper and lightweight stats."""
    with engine.connect() as conn:
        paper = conn.execute(
            text("""
                SELECT
                    p.id AS paper_id,
                    p.code AS paper_code,
                    p.title,
                    p.paper_type,
                    p.exam_year,
                    p.status AS paper_status,
                    p.review_status,
                    c.code AS certificate_code,
                    c.name AS certificate_name,
                    s.code AS subject_code,
                    s.name AS subject_name,
                    ou.code AS owner_org_code,
                    a.code AS source_asset_code,
                    a.title AS source_asset_title,
                    av.version_no AS source_asset_version_no,
                    kc.code AS collection_code
                  FROM assessment.paper p
                  JOIN core.certificate c ON c.id = p.certificate_id
                  LEFT JOIN core.exam_subject s ON s.id = p.subject_id
                  JOIN iam.organization_unit ou ON ou.id = p.owner_org_id
                  JOIN knowledge.asset_version av ON av.id = p.source_asset_version_id
                  JOIN knowledge.asset a ON a.id = av.asset_id
                  JOIN knowledge.collection kc ON kc.id = a.collection_id
                 WHERE p.code = :paper_code
                   AND p.status = 'published'
                   AND p.review_status = 'approved'
            """),
            {"paper_code": paper_code},
        ).fetchone()
        if paper is None:
            raise ValueError("paper not found")

    check_collection_access(
        engine,
        principal_type=principal_type,
        principal_code=principal_code,
        collection_code=paper.collection_code,
        required_permission="read",
    )

    with engine.connect() as conn:
        question_rows = conn.execute(
            text("""
                SELECT
                    q.id,
                    q.question_no,
                    q.question_type,
                    q.content,
                    q.options,
                    q.answer,
                    q.analysis,
                    q.difficulty,
                    f.fragment_code AS source_fragment_code
                  FROM assessment.question q
                  LEFT JOIN knowledge.fragment f ON f.id = q.source_fragment_id
                 WHERE q.paper_id = :paper_id
                   AND q.review_status = 'approved'
                 ORDER BY q.question_no
            """),
            {"paper_id": paper.paper_id},
        ).fetchall()
        kp_rows = conn.execute(
            text("""
                SELECT
                    q.question_no,
                    kp.code AS kp_code,
                    kp.name AS kp_name,
                    qkp.role,
                    qkp.score_weight
                  FROM assessment.question_knowledge_point qkp
                  JOIN assessment.question q ON q.id = qkp.question_id
                  JOIN knowledge.knowledge_point kp ON kp.id = qkp.kp_id
                 WHERE q.paper_id = :paper_id
                   AND q.review_status = 'approved'
                 ORDER BY q.question_no, qkp.role, kp.code
            """),
            {"paper_id": paper.paper_id},
        ).fetchall()

    kps_by_question: dict[str, list[dict[str, Any]]] = {}
    coverage: dict[str, dict[str, Any]] = {}
    for row in kp_rows:
        kp_payload = {
            "code": row.kp_code,
            "name": row.kp_name,
            "role": row.role,
            "scoreWeight": _to_float(row.score_weight),
        }
        kps_by_question.setdefault(row.question_no, []).append(kp_payload)
        entry = coverage.setdefault(
            row.kp_code,
            {"code": row.kp_code, "name": row.kp_name, "questionCount": 0, "primaryCount": 0},
        )
        entry["questionCount"] += 1
        if row.role == "primary":
            entry["primaryCount"] += 1

    difficulty_distribution = {str(level): 0 for level in range(1, 6)}
    questions: list[dict[str, Any]] = []
    for row in question_rows:
        difficulty_distribution[str(row.difficulty)] += 1
        questions.append(
            {
                "questionNo": row.question_no,
                "questionType": row.question_type,
                "content": row.content,
                "options": row.options,
                "answer": row.answer,
                "analysis": row.analysis,
                "difficulty": row.difficulty,
                "sourceFragmentCode": row.source_fragment_code,
                "knowledgePoints": kps_by_question.get(row.question_no, []),
            }
        )

    return {
        "paper": {
            "code": paper.paper_code,
            "title": paper.title,
            "paperType": paper.paper_type,
            "examYear": paper.exam_year,
            "status": paper.paper_status,
            "certificate": {
                "code": paper.certificate_code,
                "name": paper.certificate_name,
            },
            "subject": None
            if paper.subject_code is None
            else {
                "code": paper.subject_code,
                "name": paper.subject_name,
            },
            "ownerOrgCode": paper.owner_org_code,
            "sourceAsset": {
                "code": paper.source_asset_code,
                "title": paper.source_asset_title,
                "versionNo": paper.source_asset_version_no,
            },
        },
        "questions": questions,
        "stats": {
            "questionCount": len(questions),
            "knowledgePointCount": len(coverage),
            "difficultyDistribution": difficulty_distribution,
            "knowledgePointCoverage": sorted(coverage.values(), key=lambda item: item["code"]),
        },
    }
