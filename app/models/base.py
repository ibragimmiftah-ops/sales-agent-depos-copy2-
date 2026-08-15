"""SQLAlchemy declarative base."""

import uuid

from sqlalchemy.orm import DeclarativeBase


def _gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class Base(DeclarativeBase):
    pass
