from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from uuid import UUID, uuid4


@dataclass
class RiskSnapshot:
    snapshot_date: date
    daily_pnl: float = 0.0
    daily_loss: float = 0.0      # 누적 손실 (항상 >= 0)
    trading_halted: bool = False
    halt_reason: str | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def halt(self, reason: str) -> None:
        self.trading_halted = True
        self.halt_reason = reason
        self.updated_at = datetime.utcnow()

    def resume(self) -> None:
        self.trading_halted = False
        self.halt_reason = None
        self.updated_at = datetime.utcnow()

    def add_pnl(self, pnl: float) -> None:
        self.daily_pnl += pnl
        if pnl < 0:
            self.daily_loss += abs(pnl)
        self.updated_at = datetime.utcnow()
