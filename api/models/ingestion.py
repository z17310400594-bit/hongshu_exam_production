"""Ingestion models — import batches and validation errors."""

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Identity, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from api.models import Base


class ImportBatch(Base):
    __tablename__ = "import_batch"
    __table_args__ = (
        CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'"),
        CheckConstraint("status IN ('uploaded','validating','failed','committed')"),
        CheckConstraint("total_rows >= 0"),
        CheckConstraint("success_rows >= 0"),
        CheckConstraint("failed_rows >= 0"),
        CheckConstraint("success_rows + failed_rows <= total_rows"),
        Index("idx_ingestion_import_batch_status", "status"),
        {"schema": "ingestion"},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    content_sha256: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    imported_by: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, server_default="uploaded", nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    success_rows: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    failed_rows: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)


class ValidationError(Base):
    __tablename__ = "validation_error"
    __table_args__ = (
        CheckConstraint("row_number IS NULL OR row_number > 0"),
        CheckConstraint("severity IN ('P0','P1','P2','P3')"),
        CheckConstraint("error_code ~ '^[A-Z0-9_]+$'"),
        UniqueConstraint("batch_id", "row_key", "field_name", "error_code"),
        Index("idx_ingestion_validation_error_batch", "batch_id", "severity"),
        {"schema": "ingestion"},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    batch_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ingestion.import_batch.id", ondelete="CASCADE"), nullable=False)
    row_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    row_key: Mapped[str] = mapped_column(Text, nullable=False)
    field_name: Mapped[str] = mapped_column(Text, nullable=False)
    error_code: Mapped[str] = mapped_column(Text, nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, server_default="P1", nullable=False)
