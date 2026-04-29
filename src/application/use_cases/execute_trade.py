from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from src.application.ports.audit_port import AuditLogger
from src.application.ports.broker_port import BrokerPort
from src.application.ports.distributed_lock_port import DistributedLock
from src.application.ports.notifier_port import NotifierPort
from src.application.services.risk_guard import RiskGuardService
from src.domain.entities.signal import SignalType, TradingSignal
from src.domain.entities.trade import OrderSide, OrderType, Trade
from src.domain.exceptions import DuplicateOrderError
from src.domain.repositories.trade_repository import TradeRepository

logger = logging.getLogger(__name__)


@dataclass
class ExecuteTradeRequest:
    ticker: str
    signal: TradingSignal


class ExecuteTradeUseCase:
    """신호 → 리스크 검증 → 중복방지 → 주문 실행 → 감사 로그."""

    def __init__(
        self,
        broker: BrokerPort,
        risk_guard: RiskGuardService,
        trade_repo: TradeRepository,
        lock: DistributedLock,
        audit: AuditLogger,
        notifier: NotifierPort,
        max_position_krw: float,
    ) -> None:
        self._broker = broker
        self._risk_guard = risk_guard
        self._trade_repo = trade_repo
        self._lock = lock
        self._audit = audit
        self._notifier = notifier
        self._max_position_krw = max_position_krw

    async def execute(self, request: ExecuteTradeRequest) -> Trade:
        lock_key = f"trade:{request.ticker}:{date.today().isoformat()}"

        async with self._lock.acquire(lock_key, ttl=300):
            # 오늘 이미 처리한 ticker → 조용히 스킵 (idempotency guard)
            existing = await self._trade_repo.find_by_ticker_today(request.ticker)
            if existing:
                raise DuplicateOrderError(
                    f"Already processed {request.ticker} today ({len(existing)} trade(s) found)"
                )

            # 현재가 조회
            current_price = await self._broker.get_current_price(request.ticker)

            # 주문 수량 계산 (최대 투자금액 ÷ 현재가)
            quantity = self._calculate_quantity(current_price)
            if quantity <= 0:
                raise ValueError(
                    f"Cannot calculate valid quantity for {request.ticker}"
                    f" at ₩{current_price:,.0f} with max ₩{self._max_position_krw:,.0f}"
                )

            # 리스크 가드 검증 — 실패 시 예외 발생, 주문 불가
            await self._risk_guard.validate(request.ticker, request.signal, quantity, current_price)

            # BUY/SELL → OrderSide 변환
            order_side = (
                OrderSide.BUY
                if request.signal.signal_type == SignalType.BUY
                else OrderSide.SELL
            )

            # 주문 실행
            kiwoom_order_id = await self._broker.place_order(
                ticker=request.ticker,
                side=order_side,
                order_type=OrderType.LIMIT,
                quantity=quantity,
                price=current_price,
            )

            # Trade 도메인 객체 생성 + 저장
            trade = Trade(
                ticker=request.ticker,
                order_side=order_side,
                order_type=OrderType.LIMIT,
                quantity=quantity,
                price=current_price,
                signal_id=request.signal.id,
                kiwoom_order_id=kiwoom_order_id,
            )
            await self._trade_repo.save(trade)

            # 감사 로그 (append-only)
            await self._audit.log(
                event_type="ORDER_PLACED",
                entity_type="trade",
                entity_id=trade.id,
                payload={
                    "ticker": trade.ticker,
                    "side": trade.order_side.value,
                    "quantity": trade.quantity,
                    "price": trade.price,
                    "signal_id": str(trade.signal_id),
                    "kiwoom_order_id": kiwoom_order_id,
                },
            )

            await self._notifier.send(
                title=f"주문 실행: {request.ticker}",
                message=(
                    f"{order_side.value} {quantity}주 @ ₩{current_price:,.0f}\n"
                    f"신호: {request.signal.signal_type.value} "
                    f"({request.signal.confidence.value})"
                ),
                color=0x2ECC71 if order_side == OrderSide.BUY else 0xE74C3C,
            )

            logger.info(
                "Order placed: %s %s qty=%d price=%.0f order_id=%s",
                request.ticker, order_side.value, quantity, current_price, kiwoom_order_id,
            )

            return trade

    def _calculate_quantity(self, price: float) -> int:
        """최대 투자금액 기준 정수 주문 수량. 1주 미만이면 0."""
        if price <= 0:
            return 0
        return int(self._max_position_krw / price)
