"""Generation models — auditable runs, citations, and outputs."""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Identity, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from api.models import Base


class GenerationRun(Base):
    __tablename__ = "run"
    __table_args__ = (
        CheckConstraint("confidentiality IN ('public','internal','confidential','restricted')"),
        CheckConstraint("model_route IN ('internal','approved_external','unapproved_external')"),
        CheckConstraint("status IN ('pending','running','succeeded','failed','cancelled')"),
        Index("idx_generation_run_application_status", "application_code", "status"),
        {"schema": "generation"},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    application_code: Mapped[str] = mapped_column(Text, nullable=False)
    user_code: Mapped[str] = mapped_column(Text, nullable=False)
    model_provider: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str] = mapped_column(Text, nullable=False)
    model_route: Mapped[str] = mapped_column(Text, server_default="internal", nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    confidentiality: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, server_default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)


class GenerationCitation(Base):
    __tablename__ = "citation"
    __table_args__ = (
        CheckConstraint("citation_order > 0"),
        CheckConstraint("usage_type IN ('reference','evidence','prompt_context')"),
        UniqueConstraint("generation_run_id", "citation_order"),
        Index("idx_generation_citation_fragment", "fragment_id"),
        {"schema": "generation"},
    )

    generation_run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("generation.run.id", ondelete="CASCADE"),
        primary_key=True,
    )
    fragment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("knowledge.fragment.id"), primary_key=True)
    citation_order: Mapped[int] = mapped_column(Integer, nullable=False)
    usage_type: Mapped[str] = mapped_column(Text, server_default="reference", nullable=False)


class GenerationOutput(Base):
    __tablename__ = "output"
    __table_args__ = (
        CheckConstraint("output_type IN ('article','card_set','textbook_draft','question_draft','policy_article','policy_card')"),
        CheckConstraint("confidentiality IN ('public','internal','confidential','restricted')"),
        CheckConstraint("status IN ('draft','reviewed','approved','rejected')"),
        CheckConstraint("status <> 'approved' OR approved_by IS NOT NULL"),
        CheckConstraint("jsonb_typeof(content) = 'object'"),
        Index("idx_generation_output_run_status", "generation_run_id", "status"),
        {"schema": "generation"},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    generation_run_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("generation.run.id", ondelete="CASCADE"), nullable=False)
    output_type: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    confidentiality: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, server_default="draft", nullable=False)
    approved_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
