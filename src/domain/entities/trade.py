from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


@dataclass
class Trade:
    ticker: str
    order_side: OrderSide
    order_type: OrderType
    quantity: int
    price: float | None          # None = 시장가
    status: OrderStatus = OrderStatus.PENDING
    id: UUID = field(default_factory=uuid4)
    signal_id: UUID | None = None
    kiwoom_order_id: str | None = None
    filled_price: float | None = None
    filled_quantity: int | None = None
    error_message: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    filled_at: datetime | None = None

    def mark_filled(self, filled_price: float, filled_qty: int) -> None:
        self.status = OrderStatus.FILLED
        self.filled_price = filled_price
        self.filled_quantity = filled_qty
        self.filled_at = datetime.utcnow()

    def mark_failed(self, reason: str) -> None:
        self.status = OrderStatus.FAILED
        self.error_message = reason

    def mark_cancelled(self) -> None:
        self.status = OrderStatus.CANCELLED

    @property
    def is_terminal(self) -> bool:
        return self.status in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.FAILED)

    @property
    def investment_krw(self) -> float | None:
        """Estimated investment at order price (None for market orders without price)."""
        if self.price is None:
            return None
        return self.price * self.quantity
