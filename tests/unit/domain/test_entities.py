"""Unit tests for domain entities."""
from __future__ import annotations

import pytest

from src.domain.entities.position import Position
from src.domain.entities.risk_snapshot import RiskSnapshot
from src.domain.entities.signal import ConfidenceLevel, SignalType, TradingSignal
from src.domain.entities.trade import OrderSide, OrderStatus, OrderType, Trade

from datetime import date


class TestTrade:
    def test_initial_status_is_pending(self):
        trade = Trade(ticker="005930", order_side=OrderSide.BUY, order_type=OrderType.LIMIT, quantity=10, price=75_000.0)
        assert trade.status == OrderStatus.PENDING
        assert not trade.is_terminal

    def test_mark_filled_updates_status(self):
        trade = Trade(ticker="005930", order_side=OrderSide.BUY, order_type=OrderType.LIMIT, quantity=10, price=75_000.0)
        trade.mark_filled(filled_price=75_100.0, filled_qty=10)
        assert trade.status == OrderStatus.FILLED
        assert trade.filled_price == 75_100.0
        assert trade.filled_quantity == 10
        assert trade.is_terminal

    def test_mark_failed_sets_error(self):
        trade = Trade(ticker="005930", order_side=OrderSide.BUY, order_type=OrderType.LIMIT, quantity=10, price=75_000.0)
        trade.mark_failed("API timeout")
        assert trade.status == OrderStatus.FAILED
        assert trade.error_message == "API timeout"
        assert trade.is_terminal

    def test_investment_krw_limit_order(self):
        trade = Trade(ticker="005930", order_side=OrderSide.BUY, order_type=OrderType.LIMIT, quantity=5, price=80_000.0)
        assert trade.investment_krw == 400_000.0

    def test_investment_krw_market_order_is_none(self):
        trade = Trade(ticker="005930", order_side=OrderSide.BUY, order_type=OrderType.MARKET, quantity=5, price=None)
        assert trade.investment_krw is None


class TestPosition:
    def test_unrealized_pnl_gain(self, active_position: Position):
        pnl = active_position.unrealized_pnl(current_price=80_000.0)
        assert pnl == 50_000.0

    def test_unrealized_pnl_loss(self, active_position: Position):
        pnl = active_position.unrealized_pnl(current_price=70_000.0)
        assert pnl == -50_000.0

    def test_unrealized_pnl_pct(self, active_position: Position):
        pct = active_position.unrealized_pnl_pct(current_price=82_500.0)
        assert pct == pytest.approx(10.0)

    def test_is_active_when_quantity_positive(self, active_position: Position):
        assert active_position.is_active

    def test_apply_fill_buy_updates_avg_cost(self, active_position: Position):
        active_position.apply_fill(filled_qty=10, filled_price=85_000.0, side="BUY")
        assert active_position.quantity == 20
        assert active_position.avg_cost == pytest.approx(80_000.0)

    def test_apply_fill_sell_reduces_quantity(self, active_position: Position):
        active_position.apply_fill(filled_qty=5, filled_price=80_000.0, side="SELL")
        assert active_position.quantity == 5
        assert active_position.realized_pnl == 25_000.0


class TestRiskSnapshot:
    def test_initial_state_not_halted(self):
        snap = RiskSnapshot(snapshot_date=date.today())
        assert not snap.trading_halted
        assert snap.halt_reason is None
        assert snap.daily_loss == 0.0

    def test_halt_sets_reason(self):
        snap = RiskSnapshot(snapshot_date=date.today())
        snap.halt("일일 손실 한도 초과")
        assert snap.trading_halted
        assert snap.halt_reason == "일일 손실 한도 초과"

    def test_resume_clears_halt(self):
        snap = RiskSnapshot(snapshot_date=date.today())
        snap.halt("test")
        snap.resume()
        assert not snap.trading_halted
        assert snap.halt_reason is None

    def test_add_pnl_tracks_loss(self):
        snap = RiskSnapshot(snapshot_date=date.today())
        snap.add_pnl(-100_000.0)
        assert snap.daily_pnl == -100_000.0
        assert snap.daily_loss == 100_000.0

    def test_add_pnl_profit_does_not_increase_loss(self):
        snap = RiskSnapshot(snapshot_date=date.today())
        snap.add_pnl(50_000.0)
        assert snap.daily_loss == 0.0


class TestTradingSignal:
    def test_is_actionable_for_buy_sell(self, buy_signal: TradingSignal):
        assert buy_signal.is_actionable

    def test_hold_not_actionable(self, samsung_ticker: str):
        sig = TradingSignal(
            ticker=samsung_ticker,
            signal_type=SignalType.HOLD,
            confidence=ConfidenceLevel.HIGH,
            analyst_report="Investment Opinion: HOLD\nConfidence: HIGH",
        )
        assert not sig.is_actionable

    def test_high_confidence_flag(self, buy_signal: TradingSignal):
        assert buy_signal.is_high_confidence

    def test_low_confidence_not_high(self, samsung_ticker: str):
        sig = TradingSignal(
            ticker=samsung_ticker,
            signal_type=SignalType.BUY,
            confidence=ConfidenceLevel.LOW,
            analyst_report="",
        )
        assert not sig.is_high_confidence

    def test_confidence_meets_minimum(self):
        assert ConfidenceLevel.HIGH.meets_minimum(ConfidenceLevel.MEDIUM)
        assert ConfidenceLevel.MEDIUM.meets_minimum(ConfidenceLevel.MEDIUM)
        assert not ConfidenceLevel.LOW.meets_minimum(ConfidenceLevel.MEDIUM)
