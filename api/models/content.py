"""Content models — learning products, versions, chapters, and KP mappings."""

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Identity, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from api.models import Base


class Product(Base):
    __tablename__ = "product"
    __table_args__ = (
        CheckConstraint("product_type IN ('textbook','teaching_aid','handout','courseware')"),
        CheckConstraint("status IN ('active','deprecated')"),
        {"schema": "content"},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    certificate_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("core.certificate.id"), nullable=False)
    product_type: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    owner_org_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("iam.organization_unit.id"), nullable=False)
    status: Mapped[str] = mapped_column(Text, server_default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)


class ProductVersion(Base):
    __tablename__ = "product_version"
    __table_args__ = (
        CheckConstraint("version_no > 0"),
        CheckConstraint("confidentiality IN ('public','internal','confidential','restricted')"),
        CheckConstraint("status IN ('drafting','reviewing','approved','published','archived')"),
        CheckConstraint("review_status IN ('pending','approved','rejected')"),
        CheckConstraint("status <> 'published' OR (review_status = 'approved' AND reviewed_by IS NOT NULL)"),
        UniqueConstraint("product_id", "version_no"),
        {"schema": "content"},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("content.product.id", ondelete="CASCADE"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    source_asset_version_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("knowledge.asset_version.id"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidentiality: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, server_default="drafting", nullable=False)
    review_status: Mapped[str] = mapped_column(Text, server_default="pending", nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)


class Chapter(Base):
    __tablename__ = "chapter"
    __table_args__ = (
        CheckConstraint("parent_id IS NULL OR parent_id <> id"),
        CheckConstraint("sequence_no >= 0"),
        CheckConstraint("confidentiality IN ('public','internal','confidential','restricted')"),
        CheckConstraint("review_status IN ('pending','approved','rejected')"),
        CheckConstraint("status IN ('draft','published','archived')"),
        CheckConstraint("status <> 'published' OR review_status = 'approved'"),
        UniqueConstraint("product_version_id", "chapter_code"),
        Index("idx_content_chapter_parent", "parent_id"),
        Index("idx_content_chapter_version_order", "product_version_id", "sequence_no"),
        {"schema": "content"},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    product_version_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("content.product_version.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("content.chapter.id"), nullable=True)
    source_fragment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("knowledge.fragment.id"), nullable=False)
    chapter_code: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    sequence_no: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    confidentiality: Mapped[str] = mapped_column(Text, nullable=False)
    review_status: Mapped[str] = mapped_column(Text, server_default="pending", nullable=False)
    status: Mapped[str] = mapped_column(Text, server_default="draft", nullable=False)


class ChapterKnowledgePoint(Base):
    __tablename__ = "chapter_knowledge_point"
    __table_args__ = (
        CheckConstraint("teaching_role IN ('core','example','extension','exercise')"),
        CheckConstraint("review_status IN ('pending','approved','rejected')"),
        CheckConstraint("review_status <> 'approved' OR reviewed_by IS NOT NULL"),
        Index("idx_content_chapter_kp_lookup", "kp_id", "review_status"),
        {"schema": "content"},
    )

    chapter_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("content.chapter.id", ondelete="CASCADE"),
        primary_key=True,
    )
    kp_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("knowledge.knowledge_point.id", ondelete="CASCADE"),
        primary_key=True,
    )
    teaching_role: Mapped[str] = mapped_column(Text, primary_key=True)
    review_status: Mapped[str] = mapped_column(Text, server_default="pending", nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(Text, nullable=True)
