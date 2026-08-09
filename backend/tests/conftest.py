import asyncio
import os
import shutil
import tempfile
from pathlib import Path

_test_root = Path(tempfile.mkdtemp(prefix="duxue-pytest-"))
_database_path = (_test_root / "test.db").as_posix()
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_database_path}"
os.environ["UPLOAD_DIR"] = str(_test_root / "uploads")
os.environ["ENABLE_SCHEDULER"] = "false"
os.environ["SECRET_KEY"] = "pytest-only-secret-key-that-is-longer-than-thirty-two-bytes"
os.environ["BOOTSTRAP_ADMIN_STUDENT_ID"] = "admin001"
os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = "admin123"

import pytest
from fastapi.testclient import TestClient

from app.database import engine
from app.main import app
from seed import seed


@pytest.fixture(scope="session", autouse=True)
def database():
    asyncio.run(seed())
    yield
    asyncio.run(engine.dispose())
    shutil.rmtree(_test_root, ignore_errors=True)


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
