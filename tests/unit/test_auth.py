"""
Tests unitarios de backend_python.auth: hashing y JWT, sin tocar la DB.
"""

import time

import pytest
from backend_python import config as _config  # noqa: F401  (triggers .env.local load)
from backend_python.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    """spec: RN-AUTH-001"""

    def test_hash_is_not_plaintext(self):
        assert hash_password("secreto123") != "secreto123"

    def test_verify_correct_password(self):
        h = hash_password("secreto123")
        assert verify_password("secreto123", h) is True

    def test_verify_incorrect_password(self):
        h = hash_password("secreto123")
        assert verify_password("otra-cosa", h) is False


class TestJWT:
    """spec: RN-AUTH-001"""

    def test_token_decodes_to_same_claims(self):
        token = create_access_token(user_id="u1", account_id="a1", role="dueño")
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "u1"
        assert payload["account_id"] == "a1"
        assert payload["role"] == "dueño"

    def test_invalid_token_returns_none(self):
        assert decode_access_token("esto-no-es-un-jwt") is None

    def test_tampered_token_returns_none(self):
        token = create_access_token(user_id="u1", account_id="a1", role="dueño")
        tampered = token[:-2] + ("aa" if token[-2:] != "aa" else "bb")
        assert decode_access_token(tampered) is None
