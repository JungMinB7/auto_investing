"""Shared pytest fixtures."""
from __future__ import annotations

import pytest

from src.domain.entities.risk_rule import RiskRule
from src.domain.entities.risk_snapshot import RiskSnapshot
from src.domain.entities.signal import ConfidenceLevel, SignalType, TradingSignal
from src.domain.entities.trade import OrderSide, OrderType, Trade
from src.domain.entities.position import Position
from src.domain.entities.watchlist import WatchlistItem

from datetime import date


@pytest.fixture
def samsung_ticker() -> str:
    return "005930"


@pytest.fixture
def buy_signal(samsung_ticker: str) -> TradingSignal:
    return TradingSignal(
        ticker=samsung_ticker,
        signal_type=SignalType.BUY,
        confidence=ConfidenceLevel.HIGH,
        analyst_report="Investment Opinion: BUY\nConfidence: HIGH\n12-Month Target Price: ₩90,000\nCurrent Price: ₩75,000",
        target_price=90_000.0,
        current_price=75_000.0,
        upside_pct=20.0,
    )


@pytest.fixture
def default_risk_rule() -> RiskRule:
    return RiskRule(
        max_daily_loss_krw=300_000.0,
        max_position_count=10,
        max_position_krw=1_000_000.0,
        max_position_pct=10.0,
        min_signal_confidence=ConfidenceLevel.MEDIUM,
    )


@pytest.fixture
def today_snapshot() -> RiskSnapshot:
    return RiskSnapshot(snapshot_date=date.today())


@pytest.fixture
def active_position(samsung_ticker: str) -> Position:
    return Position(ticker=samsung_ticker, quantity=10, avg_cost=75_000.0)
