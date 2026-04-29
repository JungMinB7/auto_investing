from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass
class Position:
    ticker: str
    quantity: int
    avg_cost: float               # KRW per share
    id: UUID = field(default_factory=uuid4)
    realized_pnl: float = 0.0
    opened_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def market_value(self, current_price: float) -> float:
        return self.quantity * current_price

    def unrealized_pnl(self, current_price: float) -> float:
        return (current_price - self.avg_cost) * self.quantity

    def unrealized_pnl_pct(self, current_price: float) -> float:
        if self.avg_cost == 0:
            return 0.0
        return (current_price - self.avg_cost) / self.avg_cost * 100

    def total_cost(self) -> float:
        return self.avg_cost * self.quantity

    @property
    def is_active(self) -> bool:
        return self.quantity > 0

    def apply_fill(self, filled_qty: int, filled_price: float, side: str) -> None:
        """Update position after a fill. side: 'BUY' or 'SELL'."""
        if side == "BUY":
            total_cost = self.avg_cost * self.quantity + filled_price * filled_qty
            self.quantity += filled_qty
            self.avg_cost = total_cost / self.quantity if self.quantity else 0.0
        elif side == "SELL":
            pnl = (filled_price - self.avg_cost) * filled_qty
            self.realized_pnl += pnl
            self.quantity -= filled_qty
        self.updated_at = datetime.utcnow()
