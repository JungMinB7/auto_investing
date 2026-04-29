"""001 — Initial schema: signals, trades, positions, audit_events, risk_snapshots, watchlist.

Revision ID: 001
Revises:
Create Date: 2026-04-29
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── signals ──────────────────────────────────────────────
    op.create_table(
        "signals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("signal_type", sa.String(10), nullable=False),
        sa.Column("confidence", sa.String(20), nullable=False),
        sa.Column("target_price", sa.Numeric(15, 2), nullable=True),
        sa.Column("current_price", sa.Numeric(15, 2), nullable=True),
        sa.Column("upside_pct", sa.Numeric(8, 2), nullable=True),
        sa.Column("analyst_report", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint("signal_type IN ('BUY', 'HOLD', 'SELL')", name="ck_signals_signal_type"),
    )
    op.create_index("ix_signals_ticker", "signals", ["ticker"])
    op.create_index("ix_signals_created_at", "signals", ["created_at"])

    # ── trades ───────────────────────────────────────────────
    op.create_table(
        "trades",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("order_side", sa.String(10), nullable=False),
        sa.Column("order_type", sa.String(20), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("price", sa.Numeric(15, 2), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("kiwoom_order_id", sa.String(50), nullable=True),
        sa.Column("signal_id", UUID(as_uuid=True), sa.ForeignKey("signals.id"), nullable=True),
        sa.Column("filled_price", sa.Numeric(15, 2), nullable=True),
        sa.Column("filled_quantity", sa.Integer, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("filled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("order_side IN ('BUY', 'SELL')", name="ck_trades_order_side"),
        sa.CheckConstraint("order_type IN ('MARKET', 'LIMIT')", name="ck_trades_order_type"),
    )
    op.create_index("ix_trades_ticker", "trades", ["ticker"])
    op.create_index("ix_trades_created_at", "trades", ["created_at"])
    op.create_index("ix_trades_status", "trades", ["status"])

    # ── positions ────────────────────────────────────────────
    op.create_table(
        "positions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("ticker", sa.String(10), nullable=False, unique=True),
        sa.Column("quantity", sa.Integer, nullable=False, server_default="0"),
        sa.Column("avg_cost", sa.Numeric(15, 2), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    # ── audit_events (append-only) ───────────────────────────
    op.create_table(
        "audit_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_audit_events_type", "audit_events", ["event_type"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])

    # ── risk_snapshots ───────────────────────────────────────
    op.create_table(
        "risk_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("snapshot_date", sa.Date, nullable=False, unique=True),
        sa.Column("daily_pnl", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("daily_loss", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("trading_halted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("halt_reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    # ── watchlist ────────────────────────────────────────────
    op.create_table(
        "watchlist",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("ticker", sa.String(10), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=True),
        sa.Column("market", sa.String(10), nullable=False, server_default="KRX"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )


def downgrade() -> None:
    op.drop_table("watchlist")
    op.drop_table("risk_snapshots")
    op.drop_table("audit_events")
    op.drop_table("positions")
    op.drop_table("trades")
    op.drop_table("signals")
