"""Core models — certificates, aliases, and exam subjects."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Identity, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from api.models import Base


class Certificate(Base):
    __tablename__ = "certificate"
    __table_args__ = (CheckConstraint("status IN ('active','inactive')"), {"schema": "core"})

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    category_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    issuing_authority: Mapped[str | None] = mapped_column(Text, nullable=True)
    exam_authority: Mapped[str | None] = mapped_column(Text, nullable=True)
    nationwide: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    status: Mapped[str] = mapped_column(Text, server_default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)


class CertificateAlias(Base):
    __tablename__ = "certificate_alias"
    __table_args__ = (CheckConstraint("alias_type IN ('short','common','legacy')"), {"schema": "core"})

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    certificate_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("core.certificate.id", ondelete="CASCADE"), nullable=False)
    alias: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_alias: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    alias_type: Mapped[str] = mapped_column(Text, nullable=False)


class ExamSubject(Base):
    __tablename__ = "exam_subject"
    __table_args__ = (UniqueConstraint("certificate_id", "name"), {"schema": "core"})

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    certificate_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("core.certificate.id"), nullable=False)
    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
