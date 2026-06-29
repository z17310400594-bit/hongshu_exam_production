"""SQLAlchemy engines — single source of truth, no circular imports."""

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine

from api.config import settings

engine = create_async_engine(settings.database_url_async, pool_size=5, max_overflow=10)
sync_engine = create_engine(settings.database_url, pool_size=1, pool_pre_ping=True)
