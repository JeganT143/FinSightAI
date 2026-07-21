"""phase 2 SaaS: identity columns, subscriptions, usage, conversations, audit

Revision ID: b7d8e9f0a1b2
Revises: a1f2c3d4e5f6
Create Date: 2026-07-21

Expand step of expand-contract (SAAS_ARCHITECTURE.md §14): every change is
additive — new nullable columns on users, five new tables. No existing rows
are touched, so this deploys against live data with zero downtime. The
contract step (e.g. making external_auth_id NOT NULL once every row has one)
is deliberately a later, separate migration.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "b7d8e9f0a1b2"
down_revision: str | Sequence[str] | None = "a1f2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JsonB = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    # --- users: identity + denormalized plan (SAAS §3) ---
    op.add_column("users", sa.Column("external_auth_id", sa.String(64), nullable=True))
    op.add_column("users", sa.Column("plan", sa.String(20), nullable=False, server_default="free"))
    op.create_index("ix_users_external_auth_id", "users", ["external_auth_id"], unique=True)

    # --- subscriptions: local Stripe mirror (SAAS §4) ---
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("stripe_customer_id", sa.String(64), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(64), nullable=True),
        sa.Column("plan", sa.String(20), nullable=False, server_default="free"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("current_period_end", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_subscriptions_stripe_customer_id", "subscriptions", ["stripe_customer_id"])

    # --- usage_counters: one row per user per period (SAAS §6) ---
    op.create_table(
        "usage_counters",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("period_start", sa.DateTime(), nullable=False),
        sa.Column("period_end", sa.DateTime(), nullable=False),
        sa.Column("research_runs_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd_accrued", sa.Float(), nullable=False, server_default="0"),
    )
    op.create_index("ix_usage_counters_user_id", "usage_counters", ["user_id"])
    op.create_index(
        "ix_usage_counters_user_period",
        "usage_counters",
        ["user_id", "period_start"],
        unique=True,
    )

    # --- conversations + messages: the Concierge (SAAS §8) ---
    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(120), nullable=False, server_default="New conversation"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])

    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(12), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tool_calls", JsonB, nullable=True),
        sa.Column(
            "linked_report_id", sa.Uuid(), sa.ForeignKey("research_reports.id"), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])

    # --- audit_log: independent compliance trail (SAAS §9) ---
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("metadata", JsonB, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_audit_log_event_type", "audit_log", ["event_type"])
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("usage_counters")
    op.drop_table("subscriptions")
    op.drop_index("ix_users_external_auth_id", table_name="users")
    op.drop_column("users", "plan")
    op.drop_column("users", "external_auth_id")
