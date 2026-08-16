"""Reusable model mixins."""

from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, declared_attr, mapped_column


class TenantMixin:
    """Adds a required tenant_id column and enforces tenant isolation."""

    @declared_attr.directive
    @classmethod
    def tenant_id(cls) -> Mapped[str]:
        return mapped_column(
            String,
            ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
