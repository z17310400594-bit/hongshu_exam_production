"""Migration round-trip tests — all run against an isolated test database."""

from alembic import command
from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from sqlalchemy import text


def test_alembic_config_loads(alembic_cfg: AlembicConfig):
    """Alembic can locate its script directory."""
    script = ScriptDirectory.from_config(alembic_cfg)
    assert script is not None
    head = script.get_current_head()
    assert head is not None


def test_upgrade_downgrade_cycle(alembic_cfg: AlembicConfig):
    """Alembic can upgrade to head and downgrade back to base on an isolated test DB."""
    command.upgrade(alembic_cfg, "head")
    command.downgrade(alembic_cfg, "base")
    command.upgrade(alembic_cfg, "head")


def test_database_connectivity(engine):
    """Verify the isolated test database is reachable."""
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        assert result.scalar() == 1
