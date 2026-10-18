import os
from alembic.config import Config
from alembic import command
from app.core.config import settings


def test_migrations_clean_upgrade_and_downgrade():
    alembic_ini_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    alembic_cfg = Config(alembic_ini_path)
    alembic_cfg.set_main_option("script_location", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "alembic")))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.sync_test_database_url)

    # Downgrade to base (clean database state)
    command.downgrade(alembic_cfg, "base")

    # Upgrade to head (apply all migrations from scratch)
    command.upgrade(alembic_cfg, "head")

    # Verify downgrade works cleanly
    command.downgrade(alembic_cfg, "base")

    # Re-upgrade to head for subsequent tests
    command.upgrade(alembic_cfg, "head")
