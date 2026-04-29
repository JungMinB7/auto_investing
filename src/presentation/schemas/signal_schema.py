"""Pydantic schemas for signal endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from src.domain.entities.signal import ConfidenceLevel, SignalType


class AnalyzeRequest(BaseModel):
    ticker: str = Field(..., pattern=r"^\d{6}$", description="6-digit KRX ticker")


class SignalResponse(BaseModel):
    id: uuid.UUID
    ticker: str
    signal_type: SignalType
    confidence: ConfidenceLevel
    target_price: float | None
    current_price: float | None
    report_summary: str
    created_at: datetime
