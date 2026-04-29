"""Pydantic schemas for signal endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from src.domain.entities.signal import ConfidenceLevel, SignalType


class AnalyzeRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=30, description="Ticker or company name")
    force_quant: bool = Field(default=False, description="Run quant-research/backtest context")
    include_charts: bool = Field(
        default=False,
        description="Activate +charts financial-report packaging",
    )


class SignalResponse(BaseModel):
    id: uuid.UUID
    ticker: str
    signal_type: SignalType
    confidence: ConfidenceLevel
    target_price: float | None
    current_price: float | None
    report_summary: str
    created_at: datetime
