"""Migration round-trip tests."""

from alembic import command
from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from sqlalchemy import text


def test_alembic_config_loads(alembic_cfg: AlembicConfig):
    """Alembic can locate its script directory."""
    script = ScriptDirectory.from_config(alembic_cfg)
    assert script is not None
    # WP01: no revisions yet → head is base
    head = script.get_current_head()
    assert head is not None


def test_upgrade_head_to_base_is_noop(alembic_cfg: AlembicConfig):
    """Upgrading to head when no migrations exist is a no-op (does not crash)."""
    command.upgrade(alembic_cfg, "head")
    # Downgrade back to base
    command.downgrade(alembic_cfg, "base")


def test_downgrade_head_to_base_is_noop(alembic_cfg: AlembicConfig):
    """Downgrading when at base is a no-op."""
    command.downgrade(alembic_cfg, "base")


def test_database_connectivity(engine):
    """Verify the V2 database is reachable."""
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        assert result.scalar() == 1
