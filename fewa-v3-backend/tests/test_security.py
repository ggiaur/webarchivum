import pytest
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    has_required_role,
)


def test_password_hashing_and_verification():
    plain = "SuperSecretPassword123!"
    hashed = hash_password(plain)

    assert hashed != plain
    assert verify_password(plain, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_jwt_access_token_creation_and_decoding():
    token = create_access_token(
        subject="550e8400-e29b-41d4-a716-446655440000",
        role="curator",
        tenant_id="00000000-0000-0000-0000-000000000001",
    )
    decoded = decode_token(token)

    assert decoded["sub"] == "550e8400-e29b-41d4-a716-446655440000"
    assert decoded["role"] == "curator"
    assert decoded["type"] == "access"


def test_jwt_refresh_token_creation_and_decoding():
    token = create_refresh_token(
        subject="550e8400-e29b-41d4-a716-446655440000",
        tenant_id="00000000-0000-0000-0000-000000000001",
    )
    decoded = decode_token(token)

    assert decoded["sub"] == "550e8400-e29b-41d4-a716-446655440000"
    assert decoded["type"] == "refresh"


def test_invalid_jwt_token_fails():
    with pytest.raises(ValueError):
        decode_token("invalid.token.str")


def test_rbac_role_hierarchy():
    # admin > archivist > curator > indexer > viewer > guest
    assert has_required_role("admin", "curator") is True
    assert has_required_role("curator", "curator") is True
    assert has_required_role("curator", "archivist") is False
    assert has_required_role("viewer", "curator") is False
    assert has_required_role("guest", "viewer") is False
