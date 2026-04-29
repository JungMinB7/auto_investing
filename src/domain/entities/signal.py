from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4


class SignalType(str, Enum):
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"


class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM_HIGH = "MEDIUM-HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

    @classmethod
    def from_string(cls, value: str) -> "ConfidenceLevel":
        """Parse confidence strings from analyst report (e.g. 'MEDIUM-HIGH')."""
        normalized = value.upper().strip()
        for member in cls:
            if member.value == normalized:
                return member
        raise ValueError(f"Unknown confidence level: {value!r}")

    def rank(self) -> int:
        """Higher is more confident."""
        return {
            ConfidenceLevel.LOW: 1,
            ConfidenceLevel.MEDIUM: 2,
            ConfidenceLevel.MEDIUM_HIGH: 3,
            ConfidenceLevel.HIGH: 4,
        }[self]

    def meets_minimum(self, minimum: "ConfidenceLevel") -> bool:
        return self.rank() >= minimum.rank()


@dataclass
class TradingSignal:
    ticker: str
    signal_type: SignalType
    confidence: ConfidenceLevel
    analyst_report: str           # 원문 JSON / markdown
    target_price: float | None = None
    current_price: float | None = None
    upside_pct: float | None = None
    trade_score: float = 0.0      # SignalScore.trade_score (0-100)
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_actionable(self) -> bool:
        return self.signal_type in (SignalType.BUY, SignalType.SELL)

    @property
    def is_high_confidence(self) -> bool:
        return self.confidence in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM_HIGH)
