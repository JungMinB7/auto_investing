"""SQLAlchemy 2.0 ORM models — Infrastructure layer only.

Design Ref: §3.4 PostgreSQL Schema
Maps to domain entities via _to_domain() / _to_model() helpers in each repository.
Domain layer never imports this module.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SignalModel(Base):
    __tablename__ = "signals"
    __table_args__ = (
        Index("ix_signals_ticker_date", "ticker", func.date(func.cast("created_at", Date))),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    signal_type: Mapped[str] = mapped_column(String(10), nullable=False)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    target_price: Mapped[Optional[float]] = mapped_column(Numeric(15, 2), nullable=True)
    current_price: Mapped[Optional[float]] = mapped_column(Numeric(15, 2), nullable=True)
    upside_pct: Mapped[Optional[float]] = mapped_column(Numeric(8, 2), nullable=True)
    analyst_report: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TradeModel(Base):
    __tablename__ = "trades"
    __table_args__ = (
        Index("ix_trades_ticker_date", "ticker", func.date(func.cast("created_at", Date))),
        Index("ix_trades_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    order_side: Mapped[str] = mapped_column(String(10), nullable=False)
    order_type: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[Optional[float]] = mapped_column(Numeric(15, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="PENDING")
    kiwoom_order_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    signal_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    filled_price: Mapped[Optional[float]] = mapped_column(Numeric(15, 2), nullable=True)
    filled_quantity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    filled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class PositionModel(Base):
    __tablename__ = "positions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    avg_cost: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    realized_pnl: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False, server_default="0")
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AuditEventModel(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_type_date", "event_type", func.date(func.cast("created_at", Date))),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RiskSnapshotModel(Base):
    __tablename__ = "risk_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    daily_pnl: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False, server_default="0")
    daily_loss: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False, server_default="0")
    trading_halted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    halt_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class WatchlistModel(Base):
    __tablename__ = "watchlist"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    market: Mapped[str] = mapped_column(String(10), nullable=False, server_default="KRX")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
