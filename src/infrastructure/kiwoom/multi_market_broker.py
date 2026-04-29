"""MultiMarketBrokerAdapter — KRX와 US 시장을 ticker 형식으로 자동 라우팅."""
from __future__ import annotations

import re
from typing import Any

from src.application.ports.broker_port import BrokerPort
from src.domain.entities.trade import OrderSide, OrderType
from src.domain.exceptions import BrokerError


def _is_krx(ticker: str) -> bool:
    """KRX 종목 코드 = 6자리 숫자 (예: 005930, 042700)."""
    return bool(re.fullmatch(r"\d{6}", ticker.split()[0].strip()))


class MultiMarketBrokerAdapter(BrokerPort):
    """KRX → Kiwoom, US → Alpaca 자동 라우팅 어댑터.

    us_broker가 None이면 US 티커 주문 시 BrokerError를 발생시킨다.
    """

    def __init__(
        self,
        krx_broker: BrokerPort,
        us_broker: BrokerPort | None = None,
    ) -> None:
        self._krx = krx_broker
        self._us = us_broker

    def _route(self, ticker: str) -> BrokerPort:
        if _is_krx(ticker):
            return self._krx
        if self._us is None:
            raise BrokerError(
                f"US broker not configured — cannot trade {ticker}. "
                "Set ALPACA_API_KEY in .env."
            )
        return self._us

    async def place_order(
        self,
        ticker: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: int,
        price: float | None,
    ) -> str:
        return await self._route(ticker).place_order(ticker, side, order_type, quantity, price)

    async def get_current_price(self, ticker: str) -> float:
        return await self._route(ticker).get_current_price(ticker)

    async def get_positions(self) -> list[dict[str, Any]]:
        positions = list(await self._krx.get_positions())
        if self._us is not None:
            try:
                us_pos = await self._us.get_positions()
                positions.extend(us_pos)
            except Exception:
                pass
        return positions

    async def get_balance(self) -> float:
        return await self._krx.get_balance()
