"""Knowledge models — collections and ACL."""

from sqlalchemy import ARRAY, BigInteger, CheckConstraint, ForeignKey, Identity, Text, text
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
