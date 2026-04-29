"""Unit tests for RiskGuardService — all 5 rules."""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.services.risk_guard import RiskGuardService
from src.domain.entities.risk_rule import RiskRule
from src.domain.entities.risk_snapshot import RiskSnapshot
from src.domain.entities.signal import ConfidenceLevel, SignalType, TradingSignal
from src.domain.exceptions import (
    DailyLossLimitError,
    LowConfidenceError,
    PositionLimitError,
    PositionSizeError,
    TradingHaltedError,
)


def _make_rule(**overrides) -> RiskRule:
    defaults = dict(
        max_daily_loss_krw=300_000.0,
        max_position_count=5,
        max_position_krw=1_000_000.0,
        max_position_pct=10.0,
        min_signal_confidence=ConfidenceLevel.MEDIUM,
    )
    defaults.update(overrides)
    return RiskRule(**defaults)


def _make_snapshot(**overrides) -> RiskSnapshot:
    snap = RiskSnapshot(snapshot_date=date.today())
    for k, v in overrides.items():
        setattr(snap, k, v)
    return snap


def _make_guard(rule: RiskRule, snapshot: RiskSnapshot, position_count: int = 0) -> RiskGuardService:
    position_repo = AsyncMock()
    position_repo.count_active.return_value = position_count
    snapshot_repo = AsyncMock()
    snapshot_repo.get_or_create_today.return_value = snapshot
    snapshot_repo.update = AsyncMock()
    guard = RiskGuardService(rule=rule, position_repo=position_repo, snapshot_repo=snapshot_repo)
    return guard


def _make_signal(confidence: ConfidenceLevel = ConfidenceLevel.HIGH) -> TradingSignal:
    return TradingSignal(
        ticker="005930",
        signal_type=SignalType.BUY,
        confidence=confidence,
        analyst_report="",
    )


class TestRiskGuardRule1TradingHalted:
    @pytest.mark.asyncio
    async def test_raises_when_halted(self):
        snap = _make_snapshot(trading_halted=True, halt_reason="test halt")
        guard = _make_guard(_make_rule(), snap)
        with pytest.raises(TradingHaltedError):
            await guard.validate("005930", _make_signal(), quantity=10, price=75_000.0)

    @pytest.mark.asyncio
    async def test_passes_when_not_halted(self):
        guard = _make_guard(_make_rule(), _make_snapshot())
        await guard.validate("005930", _make_signal(), quantity=10, price=75_000.0)


class TestRiskGuardRule2DailyLoss:
    @pytest.mark.asyncio
    async def test_raises_when_loss_at_limit(self):
        snap = _make_snapshot(daily_loss=300_000.0)
        guard = _make_guard(_make_rule(), snap)
        with pytest.raises(DailyLossLimitError):
            await guard.validate("005930", _make_signal(), quantity=10, price=75_000.0)

    @pytest.mark.asyncio
    async def test_passes_when_below_limit(self):
        snap = _make_snapshot(daily_loss=100_000.0)
        guard = _make_guard(_make_rule(), snap)
        await guard.validate("005930", _make_signal(), quantity=10, price=75_000.0)


class TestRiskGuardRule3PositionCount:
    @pytest.mark.asyncio
    async def test_raises_when_at_max_positions(self):
        guard = _make_guard(_make_rule(max_position_count=5), _make_snapshot(), position_count=5)
        with pytest.raises(PositionLimitError):
            await guard.validate("005930", _make_signal(), quantity=10, price=75_000.0)

    @pytest.mark.asyncio
    async def test_passes_when_below_max(self):
        guard = _make_guard(_make_rule(max_position_count=5), _make_snapshot(), position_count=4)
        await guard.validate("005930", _make_signal(), quantity=10, price=75_000.0)


class TestRiskGuardRule4PositionSize:
    @pytest.mark.asyncio
    async def test_raises_when_investment_exceeds_limit(self):
        rule = _make_rule(max_position_krw=500_000.0)
        guard = _make_guard(rule, _make_snapshot())
        with pytest.raises(PositionSizeError):
            await guard.validate("005930", _make_signal(), quantity=10, price=75_000.0)  # 750k > 500k

    @pytest.mark.asyncio
    async def test_passes_when_investment_within_limit(self):
        rule = _make_rule(max_position_krw=1_000_000.0)
        guard = _make_guard(rule, _make_snapshot())
        await guard.validate("005930", _make_signal(), quantity=10, price=75_000.0)  # 750k <= 1M


class TestRiskGuardRule5Confidence:
    @pytest.mark.asyncio
    async def test_raises_when_confidence_too_low(self):
        rule = _make_rule(min_signal_confidence=ConfidenceLevel.HIGH)
        guard = _make_guard(rule, _make_snapshot())
        low_signal = _make_signal(confidence=ConfidenceLevel.LOW)
        with pytest.raises(LowConfidenceError):
            await guard.validate("005930", low_signal, quantity=5, price=75_000.0)

    @pytest.mark.asyncio
    async def test_passes_when_confidence_meets_minimum(self):
        rule = _make_rule(min_signal_confidence=ConfidenceLevel.MEDIUM)
        guard = _make_guard(rule, _make_snapshot())
        await guard.validate("005930", _make_signal(ConfidenceLevel.MEDIUM), quantity=5, price=75_000.0)


class TestRiskGuardRecordPnl:
    @pytest.mark.asyncio
    async def test_record_loss_triggers_halt_at_limit(self):
        snap = _make_snapshot(daily_loss=200_000.0)
        position_repo = AsyncMock()
        snapshot_repo = AsyncMock()
        snapshot_repo.get_or_create_today.return_value = snap
        snapshot_repo.update = AsyncMock()
        guard = RiskGuardService(rule=_make_rule(), position_repo=position_repo, snapshot_repo=snapshot_repo)
        await guard.record_pnl(-100_001.0)
        assert snap.trading_halted

    @pytest.mark.asyncio
    async def test_resume_clears_halt(self):
        snap = _make_snapshot(trading_halted=True, halt_reason="test")
        position_repo = AsyncMock()
        snapshot_repo = AsyncMock()
        snapshot_repo.get_or_create_today.return_value = snap
        snapshot_repo.update = AsyncMock()
        guard = RiskGuardService(rule=_make_rule(), position_repo=position_repo, snapshot_repo=snapshot_repo)
        await guard.resume_trading()
        assert not snap.trading_halted
        assert snap.halt_reason is None
