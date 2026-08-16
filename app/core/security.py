"""Authentication primitives: password hashing, JWT and request principal."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

ALGORITHM = "HS256"
PUBLIC_ROLE = "chat"


@dataclass(frozen=True)
class Principal:
    """Immutable request-scoped identity."""

    user_id: str | None
    tenant_id: str
    roles: frozenset[str]
    scopes: frozenset[str]
    is_anonymous: bool = False
    token: str | None = field(default=None, compare=False, repr=False, hash=False)

    def has_role(self, *roles: str) -> bool:
        return not self.roles.isdisjoint(roles)

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes


def verify_password(plain: str, hashed: str) -> bool:
    plain_bytes = plain.encode("utf-8")[:72]
    hashed_bytes = hashed.encode("utf-8")
    return bcrypt.checkpw(plain_bytes, hashed_bytes)


def get_password_hash(password: str) -> str:
    password_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


def principal_from_token(token: str) -> Principal | None:
    payload = decode_access_token(token)
    if payload is None:
        return None
    user_id = payload.get("sub")
    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        return None
    roles = payload.get("roles", [])
    scopes = payload.get("scopes", [])
    return Principal(
        user_id=user_id,
        tenant_id=tenant_id,
        roles=frozenset(roles),
        scopes=frozenset(scopes),
        is_anonymous=payload.get("anonymous", False),
    )
