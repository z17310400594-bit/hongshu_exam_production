"""Knowledge models — collections, assets, fragments, and knowledge points."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    ARRAY,
    BigInteger,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import DATERANGE, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from api.models import Base


class Collection(Base):
    __tablename__ = "collection"
    __table_args__ = (
        CheckConstraint("confidentiality IN ('public','internal','confidential','restricted')"),
        {"schema": "knowledge"},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    owner_org_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("iam.organization_unit.id"), nullable=False)
    confidentiality: Mapped[str] = mapped_column(Text, nullable=False)
    default_allowed_use: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("ARRAY['retrieval']::text[]"), nullable=False)
    status: Mapped[str] = mapped_column(Text, server_default="active", nullable=False)


class CollectionACL(Base):
    __tablename__ = "collection_acl"
    __table_args__ = (
        CheckConstraint("principal_type IN ('user','role','org')"),
        CheckConstraint("permission IN ('read','contribute','review','admin')"),
        {"schema": "knowledge"},
    )

    collection_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("knowledge.collection.id", ondelete="CASCADE"), primary_key=True)
    principal_type: Mapped[str] = mapped_column(Text, primary_key=True)
    principal_code: Mapped[str] = mapped_column(Text, primary_key=True)
    permission: Mapped[str] = mapped_column(Text, primary_key=True)


class Asset(Base):
    __tablename__ = "asset"
    __table_args__ = (
        CheckConstraint("asset_type IN ('policy','textbook','handout','private','paper','manual')"),
        CheckConstraint("confidentiality IN ('public','internal','confidential','restricted')"),
        CheckConstraint("status IN ('draft','reviewed','published','deprecated')"),
        {"schema": "knowledge"},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    asset_type: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    collection_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("knowledge.collection.id"), nullable=False)
    owner_org_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("iam.organization_unit.id"), nullable=False)
    confidentiality: Mapped[str] = mapped_column(Text, nullable=False)
    copyright_owner: Mapped[str | None] = mapped_column(Text, nullable=True)
    allowed_use: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("ARRAY['retrieval']::text[]"), nullable=False)
    status: Mapped[str] = mapped_column(Text, server_default="draft", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)


class AssetVersion(Base):
    __tablename__ = "asset_version"
    __table_args__ = (
        CheckConstraint("version_no > 0"),
        CheckConstraint("review_status IN ('pending','approved','rejected')"),
        UniqueConstraint("asset_id", "version_no"),
        UniqueConstraint("content_sha256"),
        {"schema": "knowledge"},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    asset_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("knowledge.asset.id"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    object_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    valid_during: Mapped[object | None] = mapped_column(DATERANGE, nullable=True)
    review_status: Mapped[str] = mapped_column(Text, server_default="pending", nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)


class Fragment(Base):
    __tablename__ = "fragment"
    __table_args__ = (
        CheckConstraint("fragment_type IN ('chapter','section','clause','page','table')"),
        CheckConstraint("page_from IS NULL OR page_from > 0"),
        CheckConstraint("page_to IS NULL OR page_from IS NULL OR page_to >= page_from"),
        UniqueConstraint("asset_version_id", "fragment_code"),
        Index("idx_fragment_search", "search_tsv", postgresql_using="gin"),
        Index("idx_fragment_content_trgm", "content", postgresql_using="gin", postgresql_ops={"content": "gin_trgm_ops"}),
        {"schema": "knowledge"},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    asset_version_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("knowledge.asset_version.id", ondelete="CASCADE"), nullable=False)
    fragment_code: Mapped[str] = mapped_column(Text, nullable=False)
    fragment_type: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("knowledge.fragment.id"), nullable=True)
    sequence_no: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    heading: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    page_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_to: Mapped[int | None] = mapped_column(Integer, nullable=True)
    search_tsv: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('simple', coalesce(heading,'') || ' ' || content)", persisted=True),
    )


class KnowledgePoint(Base):
    __tablename__ = "knowledge_point"
    __table_args__ = (
        CheckConstraint("parent_id IS NULL OR parent_id <> id"),
        CheckConstraint("merged_into_kp_id IS NULL OR merged_into_kp_id <> id"),
        CheckConstraint(
            "cognitive_level IS NULL OR cognitive_level IN "
            "('remember','understand','apply','analyze','evaluate','create')"
        ),
        CheckConstraint("status IN ('active','deprecated','merged')"),
        CheckConstraint("(status = 'merged') = (merged_into_kp_id IS NOT NULL)"),
        Index("idx_knowledge_point_parent", "parent_id"),
        {"schema": "knowledge"},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("knowledge.knowledge_point.id"), nullable=True)
    domain_code: Mapped[str] = mapped_column(Text, nullable=False)
    cognitive_level: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, server_default="active", nullable=False)
    merged_into_kp_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("knowledge.knowledge_point.id"), nullable=True)


class KnowledgePointRelation(Base):
    __tablename__ = "knowledge_point_relation"
    __table_args__ = (
        CheckConstraint("from_kp_id <> to_kp_id"),
        CheckConstraint("relation_type IN ('prerequisite','related','contains','similar')"),
        Index("idx_knowledge_point_relation_to", "to_kp_id"),
        {"schema": "knowledge"},
    )

    from_kp_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("knowledge.knowledge_point.id", ondelete="CASCADE"),
        primary_key=True,
    )
    to_kp_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("knowledge.knowledge_point.id", ondelete="CASCADE"),
        primary_key=True,
    )
    relation_type: Mapped[str] = mapped_column(Text, primary_key=True)


class KnowledgePointScope(Base):
    __tablename__ = "knowledge_point_scope"
    __table_args__ = (
        CheckConstraint("scope_type IN ('certificate','exam_subject','curriculum','asset_type')"),
        UniqueConstraint("kp_id", "scope_type", "scope_code"),
        Index("idx_knowledge_point_scope_lookup", "scope_type", "scope_code"),
        {"schema": "knowledge"},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    kp_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("knowledge.knowledge_point.id", ondelete="CASCADE"), nullable=False)
    scope_type: Mapped[str] = mapped_column(Text, nullable=False)
    scope_code: Mapped[str] = mapped_column(Text, nullable=False)


class FragmentKnowledgePoint(Base):
    __tablename__ = "fragment_knowledge_point"
    __table_args__ = (
        CheckConstraint("relation_role IN ('definition','evidence','explanation','example','exercise')"),
        CheckConstraint("confidence BETWEEN 0 AND 1"),
        CheckConstraint("review_status IN ('pending','approved','rejected')"),
        CheckConstraint("review_status <> 'approved' OR reviewed_by IS NOT NULL"),
        Index("idx_fragment_knowledge_point_kp_review", "kp_id", "review_status"),
        {"schema": "knowledge"},
    )

    fragment_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("knowledge.fragment.id", ondelete="CASCADE"),
        primary_key=True,
    )
    kp_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("knowledge.knowledge_point.id", ondelete="CASCADE"),
        primary_key=True,
    )
    relation_role: Mapped[str] = mapped_column(Text, primary_key=True)
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), server_default="1", nullable=False)
    review_status: Mapped[str] = mapped_column(Text, server_default="pending", nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(Text, nullable=True)
