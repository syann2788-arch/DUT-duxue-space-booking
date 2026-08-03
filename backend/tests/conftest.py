import asyncio
import os
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_pytest.db"
os.environ["ENABLE_SCHEDULER"] = "false"

import pytest
from fastapi.testclient import TestClient

from app.database import engine
from app.main import app
from seed import seed


@pytest.fixture(scope="session", autouse=True)
def database():
    path = Path("test_pytest.db")
    if path.exists():
        path.unlink()
    asyncio.run(seed())
    yield
    asyncio.run(engine.dispose())
    if path.exists():
        path.unlink()


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
