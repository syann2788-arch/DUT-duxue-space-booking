"""Application authentication contract when upgrading the JWT dependency."""
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException

from app.auth import create_access_token, decode_token
from app.config import settings


@pytest.fixture
def token_key(monkeypatch):
    key = "jwt-regression-only-key-" + "x" * 64
    monkeypatch.setattr(settings, "SECRET_KEY", key)
    monkeypatch.setattr(settings, "ALGORITHM", "HS256")
    return key


def test_valid_application_token_preserves_identity_and_expiry(token_key):
    payload = {"sub": "123", "student_id": "synthetic", "role": "student", "version": 2}
    decoded = decode_token(create_access_token(payload))
    assert all(decoded[name] == value for name, value in payload.items())
    assert decoded["exp"] > datetime.now(timezone.utc).timestamp()
    assert "exp" not in payload


@pytest.mark.parametrize("kind", ["expired", "wrong-key", "wrong-algorithm", "unsigned", "malformed"])
def test_invalid_application_token_is_rejected(token_key, kind):
    payload = {"sub": "123", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}
    if kind == "expired":
        payload["exp"] = datetime.now(timezone.utc) - timedelta(minutes=5)
    key = "another-regression-only-key-with-32-characters" if kind == "wrong-key" else token_key
    algorithm = "HS512" if kind == "wrong-algorithm" else "HS256"
    if kind == "unsigned":
        key, algorithm = None, "none"
    token = "not-a-jwt" if kind == "malformed" else jwt.encode(payload, key, algorithm=algorithm)
    with pytest.raises(HTTPException) as rejected:
        decode_token(token)
    assert rejected.value.status_code == 401
