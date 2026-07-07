"""Policy models — versioned documents, clauses, and eligibility rules."""

from datetime import date, datetime

from sqlalchemy import BigInteger, CheckConstraint, Date, DateTime, ForeignKey, Identity, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import DATERANGE, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from api.models import Base


class PolicyDocument(Base):
    __tablename__ = "document"
    __table_args__ = ({"schema": "policy"},)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    asset_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("knowledge.asset.id"), unique=True, nullable=False)
    document_code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    doc_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    issuing_authority: Mapped[str] = mapped_column(Text, nullable=False)
    official_url: Mapped[str | None] = mapped_column(Text, nullable=True)


class PolicyDocumentVersion(Base):
    __tablename__ = "document_version"
    __table_args__ = (
        CheckConstraint("version_no > 0"),
        CheckConstraint("status IN ('draft','reviewed','published','superseded','repealed')"),
        CheckConstraint("NOT isempty(valid_during)"),
        UniqueConstraint("document_id", "version_no"),
        {"schema": "policy"},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    document_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("policy.document.id"), nullable=False)
    asset_version_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("knowledge.asset_version.id"), unique=True, nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    published_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_during: Mapped[object] = mapped_column(DATERANGE, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    supersedes_version_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("policy.document_version.id"), nullable=True)


class PolicyClause(Base):
    __tablename__ = "clause"
    __table_args__ = (UniqueConstraint("document_version_id", "clause_code"), {"schema": "policy"})

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    document_version_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("policy.document_version.id", ondelete="CASCADE"),
        nullable=False,
    )
    fragment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("knowledge.fragment.id"), unique=True, nullable=False)
    clause_code: Mapped[str] = mapped_column(Text, nullable=False)
    section_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class EligibilityRule(Base):
    __tablename__ = "eligibility_rule"
    __table_args__ = (
        CheckConstraint("route_code IN ('normal','grandfathered','title_substitute')"),
        CheckConstraint("min_total_work_months >= 0"),
        CheckConstraint("min_relevant_work_months >= 0"),
        CheckConstraint("jsonb_typeof(extra_conditions) = 'object'"),
        CheckConstraint("status IN ('draft','published','superseded','repealed')"),
        CheckConstraint("review_status IN ('pending','approved','rejected')"),
        CheckConstraint("review_status <> 'approved' OR reviewed_by IS NOT NULL"),
        CheckConstraint("NOT isempty(valid_during)"),
        Index(
            "idx_eligibility_lookup",
            "certificate_id",
            "region_code",
            "degree_level_code",
            "major_category_code",
            postgresql_where=text("status = 'published' AND review_status = 'approved'"),
        ),
        {"schema": "policy"},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    certificate_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("core.certificate.id"), nullable=False)
    knowledge_point_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("knowledge.knowledge_point.id"), nullable=False)
    qualification_level: Mapped[str | None] = mapped_column(Text, nullable=True)
    route_code: Mapped[str] = mapped_column(Text, server_default="normal", nullable=False)
    degree_level_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    major_category_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    education_type_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    min_total_work_months: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    min_relevant_work_months: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    admission_before: Mapped[date | None] = mapped_column(Date, nullable=True)
    region_code: Mapped[str] = mapped_column(Text, server_default="CN", nullable=False)
    extra_conditions: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"), nullable=False)
    valid_during: Mapped[object] = mapped_column(DATERANGE, nullable=False)
    status: Mapped[str] = mapped_column(Text, server_default="draft", nullable=False)
    review_status: Mapped[str] = mapped_column(Text, server_default="pending", nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)


class EligibilityRuleEvidence(Base):
    __tablename__ = "eligibility_rule_evidence"
    __table_args__ = (
        CheckConstraint("evidence_role IN ('primary','supporting','exception')"),
        {"schema": "policy"},
    )

    eligibility_rule_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("policy.eligibility_rule.id", ondelete="CASCADE"),
        primary_key=True,
    )
    clause_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("policy.clause.id"), primary_key=True)
    evidence_role: Mapped[str] = mapped_column(Text, nullable=False)
