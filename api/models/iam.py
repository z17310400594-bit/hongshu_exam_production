"""IAM models — organization units."""

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Identity, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.models import Base


class OrganizationUnit(Base):
    __tablename__ = "organization_unit"
    __table_args__ = (CheckConstraint("status IN ('active','inactive')"), {"schema": "iam"})

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("iam.organization_unit.id"), nullable=True)
    status: Mapped[str] = mapped_column(Text, server_default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    parent: Mapped["OrganizationUnit | None"] = relationship(
        "OrganizationUnit", remote_side="OrganizationUnit.id", back_populates="children"
    )
    children: Mapped[list["OrganizationUnit"]] = relationship(
        "OrganizationUnit", back_populates="parent"
    )
