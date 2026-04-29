"""Pydantic schemas for position endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class PositionResponse(BaseModel):
    id: uuid.UUID
    ticker: str
    quantity: int
    avg_cost: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    opened_at: datetime
