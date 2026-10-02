import os
from unittest.mock import patch

import pytest

from app.config import Settings


def test_demo_seed_requires_explicit_opt_in():
    from demo_seed import create_demo_data

    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(RuntimeError, match="ALLOW_DEMO_SEED"):
            import asyncio
            asyncio.run(create_demo_data())


def test_demo_accounts_are_obviously_synthetic():
    from demo_seed import DEMO_PASSWORD, DEMO_USERS

    assert DEMO_PASSWORD == "Demo1234"
    assert {item[0] for item in DEMO_USERS} == {"20269901", "20269902"}
    assert all("演示" in item[1] for item in DEMO_USERS)


def test_production_settings_are_not_eligible_for_demo_seed():
    runtime = Settings(
        APP_ENV="production",
        DATABASE_URL="postgresql+asyncpg://example.invalid/demo",
        SECRET_KEY="x" * 32,
    )
    assert runtime.is_production is True
    assert runtime.DATABASE_URL.startswith("sqlite") is False
