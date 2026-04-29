from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.entities.trade import OrderSide, OrderType


class BrokerPort(ABC):
    @abstractmethod
    async def place_order(
        self,
        ticker: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: int,
        price: float | None,
    ) -> str: ...  # 반환값: kiwoom_order_id

    @abstractmethod
    async def get_positions(self) -> list[dict]: ...

    @abstractmethod
    async def get_balance(self) -> float: ...  # 주문 가능 금액 (KRW)

    @abstractmethod
    async def get_current_price(self, ticker: str) -> float: ...
