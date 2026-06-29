"""SQLAlchemy declarative base and model registry."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Import model modules after Base is defined so `from api.models import Base`
# always returns a fully populated registry.  Alembic and future work packages
# should not need to remember every model module by hand.
from api.models import assessment as assessment  # noqa: E402,F401
from api.models import content as content  # noqa: E402,F401
from api.models import core as core  # noqa: E402,F401
from api.models import generation as generation  # noqa: E402,F401
from api.models import iam as iam  # noqa: E402,F401
from api.models import ingestion as ingestion  # noqa: E402,F401
from api.models import knowledge as knowledge  # noqa: E402,F401
from api.models import policy as policy  # noqa: E402,F401

__all__ = ["Base", "assessment", "content", "core", "generation", "iam", "ingestion", "knowledge", "policy"]
