import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Any
import bcrypt
from jose import jwt, JWTError
from app.core.config import settings

logger = logging.getLogger(__name__)

# RBAC Role hierarchy weight mapping
ROLE_HIERARCHY = {
    "guest": 0,
    "viewer": 1,
    "indexer": 2,
    "curator": 3,
    "archivist": 4,
    "admin": 5,
}


def hash_password(password: str) -> str:
    """Hashes plain password using bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies plain password against stored bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception as e:
        logger.warning(f"Password verification error: {e}")
        return False


def create_access_token(subject: str, role: str, tenant_id: str, expires_delta: Optional[timedelta] = None) -> str:
    """Creates a JWT access token with user_id (sub), role, and tenant_id claims."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "sub": str(subject),
        "role": role,
        "tenant_id": str(tenant_id),
        "type": "access",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }

    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt


def create_refresh_token(subject: str, tenant_id: str, expires_delta: Optional[timedelta] = None) -> str:
    """Creates a JWT refresh token."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode = {
        "sub": str(subject),
        "tenant_id": str(tenant_id),
        "type": "refresh",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }

    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt


def decode_token(token: str) -> dict[str, Any]:
    """Decodes and validates JWT token signature and expiration."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload
    except JWTError as e:
        raise ValueError(f"Invalid or expired JWT token: {e}")


def has_required_role(user_role: str, min_required_role: str) -> bool:
    """Returns True if user_role has equal or higher privilege than min_required_role."""
    user_weight = ROLE_HIERARCHY.get(user_role, -1)
    required_weight = ROLE_HIERARCHY.get(min_required_role, 99)
    return user_weight >= required_weight
