"""WP09 database constraint tests — papers, questions, and question KP mappings."""

import json

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from db.tests.fixtures_wp02 import seed_fixtures as seed_wp02
from db.tests.fixtures_wp03 import seed_fixtures as seed_wp03
from db.tests.fixtures_wp09 import (
    seed_knowledge_point,
    seed_paper,
    seed_paper_source_asset,
    seed_question,
    seed_question_knowledge_point,
)


@pytest.fixture(scope="module", autouse=True)
def _migrate_module(alembic_cfg: AlembicConfig, engine: Engine):
    command.upgrade(alembic_cfg, "head")
    seed_wp02(engine)
    seed_wp03(engine)


def _seed_paper_graph(engine: Engine, *, prefix: str):
    source = seed_paper_source_asset(engine, asset_code=f"{prefix}_ASSET")
    paper = seed_paper(engine, code=f"{prefix}_PAPER", source_asset_code=source["asset_code"])
    return source, paper


def test_paper_type_year_status_review_and_fk_constraints(engine: Engine):
    source, paper = _seed_paper_graph(engine, prefix="WP09_PAPER")
    assert paper["paper_type"] == "mock"

    valid_types = [
        ("WP09_PAPER_OFFICIAL", "official"),
        ("WP09_PAPER_CHAPTER_TEST", "chapter_test"),
    ]
    for code, paper_type in valid_types:
        seeded = seed_paper(engine, code=code, source_asset_code=source["asset_code"], paper_type=paper_type)
        assert seeded["paper_type"] == paper_type

    bad_rows = [
        {"code": "WP09_BAD_TYPE", "paper_type": "daily", "exam_year": 2026, "status": "draft", "review": "approved", "reviewer": "r"},
        {"code": "WP09_BAD_YEAR", "paper_type": "mock", "exam_year": 1999, "status": "draft", "review": "approved", "reviewer": "r"},
        {"code": "WP09_BAD_STATUS", "paper_type": "mock", "exam_year": 2026, "status": "editing", "review": "approved", "reviewer": "r"},
        {"code": "WP09_BAD_REVIEW", "paper_type": "mock", "exam_year": 2026, "status": "draft", "review": "done", "reviewer": "r"},
        {
            "code": "WP09_BAD_PUBLISHED",
            "paper_type": "mock",
            "exam_year": 2026,
            "status": "published",
            "review": "pending",
            "reviewer": None,
        },
    ]
    for row in bad_rows:
        with pytest.raises(SQLAlchemyError), engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO assessment.paper (
                        code, paper_type, certificate_id, subject_id, exam_year,
                        source_asset_version_id, owner_org_id, title,
                        status, review_status, reviewed_by
                    )
                    SELECT :code, :paper_type, cert.id, subj.id, :exam_year,
                           :source_asset_version_id, org.id, 'Bad Paper',
                           :status, :review, :reviewer
                      FROM core.certificate cert
                      JOIN core.exam_subject subj ON subj.code = 'subj_constructor_mgmt'
                      JOIN iam.organization_unit org ON org.code = 'org_teaching_materials'
                     WHERE cert.code = 'c_constructor_1'
                """),
                {**row, "source_asset_version_id": source["asset_version_id"]},
            )

    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO assessment.paper (
                    code, paper_type, certificate_id, source_asset_version_id,
                    owner_org_id, title, status, review_status, reviewed_by
                )
                VALUES ('WP09_BAD_SOURCE_FK', 'mock', :certificate_id, 999999,
                        :owner_org_id, 'Bad FK', 'draft', 'approved', 'r')
            """),
            {"certificate_id": paper["certificate_id"], "owner_org_id": paper["owner_org_id"]},
        )


def test_question_type_json_difficulty_duplicate_and_source_constraints(engine: Engine):
    source, paper = _seed_paper_graph(engine, prefix="WP09_QUESTION")

    single = seed_question(
        engine,
        paper_id=paper["id"],
        source_fragment_id=source["fragment_ids"]["Q001"],
        question_no="1",
        question_type="single",
        content="单选题",
        options={"A": "正确", "B": "错误"},
        answer="A",
        difficulty=1,
    )
    multiple = seed_question(
        engine,
        paper_id=paper["id"],
        source_fragment_id=source["fragment_ids"]["Q002"],
        question_no="2",
        question_type="multiple",
        content="多选题",
        options={"A": "选项A", "B": "选项B", "C": "选项C"},
        answer=["A", "B"],
        difficulty=3,
    )
    true_false = seed_question(
        engine,
        paper_id=paper["id"],
        question_no="3",
        question_type="true_false",
        content="判断题",
        answer=True,
        difficulty=2,
    )
    case = seed_question(
        engine,
        paper_id=paper["id"],
        source_fragment_id=source["fragment_ids"]["CASE01"],
        question_no="4",
        question_type="case",
        content="案例题",
        answer={"points": ["要点1", "要点2"]},
        difficulty=5,
    )
    assert [single["question_type"], multiple["question_type"], true_false["question_type"], case["question_type"]] == [
        "single",
        "multiple",
        "true_false",
        "case",
    ]

    other_source = seed_paper_source_asset(engine, asset_code="WP09_OTHER_SOURCE_ASSET")
    bad_rows = [
        {"no": "1", "type": "single", "options": {"A": "重复"}, "answer": "A", "difficulty": 1, "fragment": None},
        {"no": "5", "type": "single", "options": {"A": "A"}, "answer": ["A"], "difficulty": 1, "fragment": None},
        {"no": "6", "type": "multiple", "options": {"A": "A"}, "answer": "A", "difficulty": 1, "fragment": None},
        {"no": "7", "type": "single", "options": ["A"], "answer": "A", "difficulty": 1, "fragment": None},
        {"no": "8", "type": "essay", "options": None, "answer": "答题要点", "difficulty": 0, "fragment": None},
        {"no": "9", "type": "case", "options": None, "answer": {"points": []}, "difficulty": 6, "fragment": None},
        {"no": "10", "type": "fill_blank", "options": None, "answer": "答案", "difficulty": 2, "fragment": None},
        {
            "no": "11",
            "type": "single",
            "options": {"A": "A"},
            "answer": "A",
            "difficulty": 1,
            "fragment": other_source["fragment_ids"]["Q001"],
        },
    ]
    for row in bad_rows:
        with pytest.raises(SQLAlchemyError), engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO assessment.question (
                        paper_id, source_fragment_id, question_no, question_type,
                        content, options, answer, difficulty, review_status
                    )
                    VALUES (
                        :paper_id, :fragment, :no, :type,
                        'Bad Question', CAST(:options_json AS jsonb),
                        CAST(:answer_json AS jsonb), :difficulty, 'approved'
                    )
                """),
                {
                    "paper_id": paper["id"],
                    "fragment": row["fragment"],
                    "no": row["no"],
                    "type": row["type"],
                    "options_json": None if row["options"] is None else json.dumps(row["options"], ensure_ascii=False),
                    "answer_json": json.dumps(row["answer"], ensure_ascii=False),
                    "difficulty": row["difficulty"],
                },
            )

    with pytest.raises(SQLAlchemyError), engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO assessment.question (
                    paper_id, question_no, question_type, content,
                    options, answer, difficulty, review_status
                )
                VALUES (
                    :paper_id, '12', 'single', 'Invalid JSON',
                    CAST(:options_json AS jsonb), CAST('A' AS jsonb), 1, 'approved'
                )
            """),
            {"paper_id": paper["id"], "options_json": "{not-json}"},
        )


def test_question_knowledge_point_constraints_and_paper_publish_gate(engine: Engine):
    source, paper = _seed_paper_graph(engine, prefix="WP09_QKP")
    approved = seed_question(
        engine,
        paper_id=paper["id"],
        source_fragment_id=source["fragment_ids"]["Q001"],
        question_no="1",
        question_type="single",
        content="已审核题",
        options={"A": "正确", "B": "错误"},
        answer="A",
        review_status="approved",
    )
    pending = seed_question(
        engine,
        paper_id=paper["id"],
        source_fragment_id=source["fragment_ids"]["Q002"],
        question_no="2",
        question_type="single",
        content="未审核题",
        options={"A": "正确", "B": "错误"},
        answer="A",
        review_status="pending",
    )
    kp = seed_knowledge_point(engine, code="WP09_KP_CONSTRAINT", name="WP09 知识点")
    seed_question_knowledge_point(engine, question_id=approved["id"], kp_code=kp["code"], role="primary", score_weight=1)

    bad_qkp_rows = [
        {"question_id": approved["id"], "kp_id": kp["id"], "role": "primary", "weight": 1},
        {"question_id": approved["id"], "kp_id": kp["id"], "role": "main", "weight": 1},
        {"question_id": approved["id"], "kp_id": kp["id"], "role": "secondary", "weight": 1.5},
        {"question_id": 999999, "kp_id": kp["id"], "role": "secondary", "weight": 0.5},
        {"question_id": approved["id"], "kp_id": 999999, "role": "secondary", "weight": 0.5},
    ]
    for row in bad_qkp_rows:
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO assessment.question_knowledge_point (
                        question_id, kp_id, role, score_weight
                    )
                    VALUES (:question_id, :kp_id, :role, :weight)
                """),
                row,
            )

    with pytest.raises(SQLAlchemyError), engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE assessment.paper
                   SET status = 'published', review_status = 'approved', reviewed_by = 'wp09_reviewer'
                 WHERE id = :paper_id
            """),
            {"paper_id": paper["id"]},
        )

    with engine.begin() as conn:
        conn.execute(
            text("UPDATE assessment.question SET review_status = 'approved' WHERE id = :question_id"),
            {"question_id": pending["id"]},
        )
        conn.execute(
            text("""
                UPDATE assessment.paper
                   SET status = 'published', review_status = 'approved', reviewed_by = 'wp09_reviewer'
                 WHERE id = :paper_id
            """),
            {"paper_id": paper["id"]},
        )
