from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass
class WatchlistItem:
    ticker: str                   # 6-digit KRX code
    name: str | None = None       # 종목명 (선택)
    market: str = "KRX"
    is_active: bool = True
    id: UUID = field(default_factory=uuid4)
    added_at: datetime = field(default_factory=datetime.utcnow)

    def deactivate(self) -> None:
        self.is_active = False
