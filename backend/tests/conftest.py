import os
import sys
import uuid
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from typing import Generator, Dict
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.services.auth_service import auth_service
from app.core.security import create_access_token

# Test database engine
test_db_url = settings.sync_test_database_url
test_engine = create_engine(test_db_url, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    # Use alembic to ensure all tables and triggers are cleanly applied
    from alembic.config import Config
    from alembic import command
    alembic_ini_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    alembic_cfg = Config(alembic_ini_path)
    alembic_cfg.set_main_option("script_location", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "alembic")))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.sync_test_database_url)

    command.upgrade(alembic_cfg, "head")
    yield
    command.downgrade(alembic_cfg, "base")


@pytest.fixture
def db() -> Generator[Session, None, None]:
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    # Seed demo data for tests
    auth_service.seed_demo_data(session)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def tokens(db: Session) -> Dict[str, str]:
    """Pre-generate JWT access tokens for each demo user role"""
    users = {
        "admin": "admin@newtonite.io",
        "lead": "lead@newtonite.io",
        "engineer": "engineer@newtonite.io",
        "viewer": "viewer@newtonite.io",
        "outsider": "outsider@newtonite.io",
    }
    user_tokens = {}
    for role, email in users.items():
        user = auth_service.get_user_by_email(db, email)
        assert user is not None
        user_tokens[role] = create_access_token(subject=user.id)
    return user_tokens


@pytest.fixture
def auth_headers(tokens: Dict[str, str]):
    def _headers(role: str) -> Dict[str, str]:
        return {"Authorization": f"Bearer {tokens[role]}"}
    return _headers
