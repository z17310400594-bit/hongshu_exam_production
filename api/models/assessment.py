"""Assessment models — exam events, phases, and score rules."""

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from api.models import Base


class ExamEvent(Base):
    __tablename__ = "exam_event"
    __table_args__ = (
        CheckConstraint("exam_year BETWEEN 2000 AND 2100"),
        CheckConstraint("status IN ('scheduled','published','completed','cancelled','needs_review')"),
        UniqueConstraint("certificate_id", "exam_year", "region_code"),
        {"schema": "assessment"},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    certificate_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("core.certificate.id"), nullable=False)
    exam_year: Mapped[int] = mapped_column(Integer, nullable=False)
    region_code: Mapped[str] = mapped_column(Text, server_default="CN", nullable=False)
    status: Mapped[str] = mapped_column(Text, server_default="scheduled", nullable=False)


class ExamPhase(Base):
    __tablename__ = "exam_phase"
    __table_args__ = (
        CheckConstraint("phase_type IN ('registration','practical','written','interview','result')"),
        CheckConstraint("ends_on IS NULL OR starts_on <= ends_on"),
        UniqueConstraint("exam_event_id", "phase_type", "starts_on"),
        {"schema": "assessment"},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    exam_event_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("assessment.exam_event.id", ondelete="CASCADE"), nullable=False)
    phase_type: Mapped[str] = mapped_column(Text, nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class SubjectScoreRule(Base):
    __tablename__ = "subject_score_rule"
    __table_args__ = (
        CheckConstraint("full_mark > 0"),
        CheckConstraint("pass_mark BETWEEN 0 AND full_mark"),
        UniqueConstraint("exam_event_id", "subject_id"),
        {"schema": "assessment"},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    exam_event_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("assessment.exam_event.id", ondelete="CASCADE"), nullable=False)
    subject_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("core.exam_subject.id"), nullable=False)
    full_mark: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    pass_mark: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)


class Paper(Base):
    __tablename__ = "paper"
    __table_args__ = (
        CheckConstraint("paper_type IN ('official','mock','chapter_test')"),
        CheckConstraint("exam_year IS NULL OR exam_year BETWEEN 2000 AND 2100"),
        CheckConstraint("status IN ('draft','published','archived')"),
        CheckConstraint("review_status IN ('pending','approved','rejected')"),
        CheckConstraint("status <> 'published' OR review_status = 'approved'"),
        Index("idx_assessment_paper_certificate_year", "certificate_id", "exam_year"),
        {"schema": "assessment"},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    paper_type: Mapped[str] = mapped_column(Text, nullable=False)
    certificate_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("core.certificate.id"), nullable=False)
    subject_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("core.exam_subject.id"), nullable=True)
    exam_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_asset_version_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("knowledge.asset_version.id"), nullable=False)
    owner_org_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("iam.organization_unit.id"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, server_default="draft", nullable=False)
    review_status: Mapped[str] = mapped_column(Text, server_default="pending", nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(Text, nullable=True)


class Question(Base):
    __tablename__ = "question"
    __table_args__ = (
        CheckConstraint("question_type IN ('single','multiple','true_false','case','essay')"),
        CheckConstraint("difficulty BETWEEN 1 AND 5"),
        CheckConstraint("review_status IN ('pending','approved','rejected')"),
        CheckConstraint("options IS NULL OR jsonb_typeof(options) = 'object'"),
        CheckConstraint("jsonb_typeof(answer) IN ('array','string','object','boolean')"),
        CheckConstraint(
            """
            (
                question_type = 'single'
                AND jsonb_typeof(options) = 'object'
                AND jsonb_typeof(answer) = 'string'
            ) OR (
                question_type = 'multiple'
                AND jsonb_typeof(options) = 'object'
                AND jsonb_typeof(answer) = 'array'
            ) OR (
                question_type = 'true_false'
                AND (options IS NULL OR jsonb_typeof(options) = 'object')
                AND jsonb_typeof(answer) IN ('boolean','string')
            ) OR (
                question_type IN ('case','essay')
                AND jsonb_typeof(answer) IN ('array','string','object')
            )
            """
        ),
        UniqueConstraint("paper_id", "question_no"),
        Index("idx_assessment_question_paper_review", "paper_id", "review_status"),
        {"schema": "assessment"},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    paper_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("assessment.paper.id", ondelete="CASCADE"), nullable=False)
    source_fragment_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("knowledge.fragment.id"), nullable=True)
    question_no: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    answer: Mapped[Any] = mapped_column(JSONB, nullable=False)
    analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    review_status: Mapped[str] = mapped_column(Text, server_default="pending", nullable=False)


class QuestionKnowledgePoint(Base):
    __tablename__ = "question_knowledge_point"
    __table_args__ = (
        CheckConstraint("role IN ('primary','secondary')"),
        CheckConstraint("score_weight IS NULL OR score_weight BETWEEN 0 AND 1"),
        Index("idx_assessment_question_kp_lookup", "kp_id", "role"),
        {"schema": "assessment"},
    )

    question_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("assessment.question.id", ondelete="CASCADE"),
        primary_key=True,
    )
    kp_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("knowledge.knowledge_point.id"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    score_weight: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)
