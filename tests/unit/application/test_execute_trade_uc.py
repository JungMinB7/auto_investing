"""Unit tests for ExecuteTradeUseCase."""
from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.application.use_cases.execute_trade import ExecuteTradeRequest, ExecuteTradeUseCase
from src.domain.entities.signal import ConfidenceLevel, SignalType, TradingSignal
from src.domain.entities.trade import OrderSide, OrderStatus
from src.domain.exceptions import DuplicateOrderError


def _make_signal(side: SignalType = SignalType.BUY) -> TradingSignal:
    return TradingSignal(
        ticker="005930",
        signal_type=side,
        confidence=ConfidenceLevel.HIGH,
        analyst_report="",
        target_price=90_000.0,
        current_price=75_000.0,
    )


@asynccontextmanager
async def _noop_lock(*args, **kwargs):
    yield


@pytest.fixture
def broker():
    mock = AsyncMock()
    mock.get_current_price.return_value = 75_000.0
    mock.place_order.return_value = "PAPER-005930-123456"
    return mock


@pytest.fixture
def risk_guard():
    mock = AsyncMock()
    mock.validate = AsyncMock(return_value=None)
    return mock


@pytest.fixture
def trade_repo():
    mock = AsyncMock()
    mock.find_by_ticker_today.return_value = []
    mock.save = AsyncMock()
    return mock


@pytest.fixture
def distributed_lock():
    mock = MagicMock()
    mock.acquire = _noop_lock
    return mock


@pytest.fixture
def use_case(broker, risk_guard, trade_repo, distributed_lock):
    return ExecuteTradeUseCase(
        broker=broker,
        risk_guard=risk_guard,
        trade_repo=trade_repo,
        lock=distributed_lock,
        audit=AsyncMock(),
        notifier=AsyncMock(),
        max_position_krw=1_000_000.0,
    )


class TestExecuteTradeUseCase:
    @pytest.mark.asyncio
    async def test_returns_pending_trade(self, use_case):
        trade = await use_case.execute(ExecuteTradeRequest(ticker="005930", signal=_make_signal()))
        assert trade.status == OrderStatus.PENDING
        assert trade.ticker == "005930"
        assert trade.order_side == OrderSide.BUY

    @pytest.mark.asyncio
    async def test_sell_signal_creates_sell_order(self, use_case):
        trade = await use_case.execute(ExecuteTradeRequest(ticker="005930", signal=_make_signal(SignalType.SELL)))
        assert trade.order_side == OrderSide.SELL

    @pytest.mark.asyncio
    async def test_raises_duplicate_order_error(self, use_case, trade_repo, active_position):
        from src.domain.entities.trade import Trade, OrderType
        existing = Trade(ticker="005930", order_side=OrderSide.BUY, order_type=OrderType.LIMIT, quantity=5, price=75_000.0)
        trade_repo.find_by_ticker_today.return_value = [existing]
        with pytest.raises(DuplicateOrderError):
            await use_case.execute(ExecuteTradeRequest(ticker="005930", signal=_make_signal()))

    @pytest.mark.asyncio
    async def test_quantity_calculated_from_max_investment(self, use_case, broker):
        broker.get_current_price.return_value = 100_000.0
        # trade_score=90 → sizing_factor=1.0 → full max_position_krw
        trade = await use_case.execute(ExecuteTradeRequest(ticker="005930", signal=_make_signal(), trade_score=90.0))
        assert trade.quantity == 10  # 1_000_000 * 1.0 / 100_000

    @pytest.mark.asyncio
    async def test_saves_trade_to_repo(self, use_case, trade_repo):
        await use_case.execute(ExecuteTradeRequest(ticker="005930", signal=_make_signal()))
        trade_repo.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_risk_guard_called(self, use_case, risk_guard):
        await use_case.execute(ExecuteTradeRequest(ticker="005930", signal=_make_signal()))
        risk_guard.validate.assert_called_once()
