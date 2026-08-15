import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///./test_agent_platform.db"
os.environ["ENABLE_LLM"] = "false"

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.db.base import Base
from src.db.session import engine


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield

@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
