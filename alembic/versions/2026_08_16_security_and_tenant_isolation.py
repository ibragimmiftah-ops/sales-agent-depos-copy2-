"""Security and tenant isolation

Revision ID: 20260816_security
Revises: 20260815_initial
Create Date: 2026-08-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260816_security"
down_revision: Union[str, None] = "20260815_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create tenant/auth tables.
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("is_public", sa.Boolean(), nullable=False, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "memberships",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False, default="operator"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "tenant_id", name="uix_user_tenant"),
    )

    # Add tenant_id columns.
    op.add_column("conversations", sa.Column("tenant_id", sa.String(), nullable=True))
    op.add_column("leads", sa.Column("tenant_id", sa.String(), nullable=True))
    op.add_column("messages", sa.Column("tenant_id", sa.String(), nullable=True))
    op.add_column("lead_events", sa.Column("tenant_id", sa.String(), nullable=True))
    op.add_column("meetings", sa.Column("tenant_id", sa.String(), nullable=True))

    # Create indexes.
    op.create_index("ix_conversations_tenant_id", "conversations", ["tenant_id"])
    op.create_index("ix_leads_tenant_id", "leads", ["tenant_id"])
    op.create_index("ix_leads_email", "leads", ["email"])
    op.create_index("ix_leads_phone", "leads", ["phone"])
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("ix_messages_tenant_id", "messages", ["tenant_id"])
    op.create_index("ix_lead_events_lead_id", "lead_events", ["lead_id"])
    op.create_index("ix_lead_events_tenant_id", "lead_events", ["tenant_id"])
    op.create_index("ix_meetings_tenant_id", "meetings", ["tenant_id"])
    op.create_index("ix_meetings_datetime", "meetings", ["datetime"])

    # Add foreign keys.
    op.create_foreign_key(
        "fk_conversations_tenant",
        "conversations",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_leads_tenant", "leads", "tenants", ["tenant_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "fk_messages_tenant",
        "messages",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_lead_events_tenant",
        "lead_events",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_meetings_tenant",
        "meetings",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Check constraints.
    op.create_check_constraint(
        "ck_leads_score_range", "leads", "lead_score IS NULL OR (lead_score >= 0 AND lead_score <= 100)"
    )
    op.create_check_constraint(
        "ck_meetings_duration_positive", "meetings", "duration_minutes > 0"
    )

    # Backfill tenant_id for existing rows (assign to public tenant).
    op.execute("INSERT INTO tenants (id, name, is_public, created_at) VALUES ('tenant_public', 'Public widget tenant', true, now())")
    op.execute("UPDATE conversations SET tenant_id = 'tenant_public' WHERE tenant_id IS NULL")
    op.execute("UPDATE leads SET tenant_id = 'tenant_public' WHERE tenant_id IS NULL")
    op.execute("UPDATE messages SET tenant_id = 'tenant_public' WHERE tenant_id IS NULL")
    op.execute("UPDATE lead_events SET tenant_id = 'tenant_public' WHERE tenant_id IS NULL")
    op.execute("UPDATE meetings SET tenant_id = 'tenant_public' WHERE tenant_id IS NULL")

    # Now make tenant_id non-nullable.
    op.alter_column("conversations", "tenant_id", nullable=False)
    op.alter_column("leads", "tenant_id", nullable=False)
    op.alter_column("messages", "tenant_id", nullable=False)
    op.alter_column("lead_events", "tenant_id", nullable=False)
    op.alter_column("meetings", "tenant_id", nullable=False)


def downgrade() -> None:
    op.drop_constraint("fk_meetings_tenant", "meetings", type_="foreignkey")
    op.drop_constraint("fk_lead_events_tenant", "lead_events", type_="foreignkey")
    op.drop_constraint("fk_messages_tenant", "messages", type_="foreignkey")
    op.drop_constraint("fk_leads_tenant", "leads", type_="foreignkey")
    op.drop_constraint("fk_conversations_tenant", "conversations", type_="foreignkey")

    op.drop_index("ix_meetings_datetime", table_name="meetings")
    op.drop_index("ix_meetings_tenant_id", table_name="meetings")
    op.drop_index("ix_lead_events_tenant_id", table_name="lead_events")
    op.drop_index("ix_lead_events_lead_id", table_name="lead_events")
    op.drop_index("ix_messages_tenant_id", table_name="messages")
    op.drop_index("ix_messages_conversation_id", table_name="messages")
    op.drop_index("ix_leads_phone", table_name="leads")
    op.drop_index("ix_leads_email", table_name="leads")
    op.drop_index("ix_leads_tenant_id", table_name="leads")
    op.drop_index("ix_conversations_tenant_id", table_name="conversations")

    op.drop_column("meetings", "tenant_id")
    op.drop_column("lead_events", "tenant_id")
    op.drop_column("messages", "tenant_id")
    op.drop_column("leads", "tenant_id")
    op.drop_column("conversations", "tenant_id")

    op.drop_table("memberships")
    op.drop_table("users")
    op.drop_table("tenants")
