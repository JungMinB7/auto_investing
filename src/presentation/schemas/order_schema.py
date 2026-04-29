"""Pydantic schemas for order / trade endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from src.domain.entities.trade import OrderSide, OrderStatus, OrderType


class ManualOrderRequest(BaseModel):
    ticker: str = Field(..., pattern=r"^\d{6}$", description="6-digit KRX ticker")
    side: OrderSide
    order_type: OrderType = OrderType.MARKET
    quantity: int = Field(..., gt=0)
    price: float | None = Field(default=None, gt=0)


class TradeResponse(BaseModel):
    id: uuid.UUID
    ticker: str
    side: OrderSide
    order_type: OrderType
    quantity: int
    price: float | None
    status: OrderStatus
    order_id: str | None
    created_at: datetime
