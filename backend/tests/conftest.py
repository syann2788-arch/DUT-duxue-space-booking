import asyncio
import os
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

_test_run_id = f"{os.getpid()}-{uuid4().hex}"
_test_root = Path(tempfile.gettempdir()) / f"duxue-pytest-{_test_run_id}"
_test_root.mkdir(parents=True, exist_ok=False)
_test_database = _test_root / "test.db"
_test_uploads = _test_root / "uploads"
_test_private_uploads = _test_root / "private_uploads"

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_test_database}"
os.environ["ENABLE_SCHEDULER"] = "false"
os.environ["UPLOAD_DIR"] = str(_test_uploads)
os.environ["PRIVATE_UPLOAD_DIR"] = str(_test_private_uploads)

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
