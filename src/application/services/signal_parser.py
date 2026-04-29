from __future__ import annotations

import re

from src.domain.entities.signal import ConfidenceLevel, SignalType, TradingSignal
from src.domain.exceptions import SignalParseError


class SignalParserService:
    """pro-securities-analyst Markdown 리포트에서 TradingSignal을 추출."""

    _SIGNAL_RE = re.compile(r"Investment Opinion:\s*(BUY|HOLD|SELL)", re.IGNORECASE)
    _CONFIDENCE_RE = re.compile(r"Confidence:\s*(HIGH|MEDIUM-HIGH|MEDIUM|LOW)", re.IGNORECASE)
    _TP_RE = re.compile(r"12-Month Target Price:.*?([\d,]+)", re.IGNORECASE)
    _CURRENT_RE = re.compile(r"Current Price:.*?([\d,]+)", re.IGNORECASE)

    def parse(self, ticker: str, report: str) -> TradingSignal:
        signal_match = self._SIGNAL_RE.search(report)
        if not signal_match:
            raise SignalParseError(
                f"Cannot find 'Investment Opinion: BUY/HOLD/SELL' in analyst report for {ticker}"
            )

        confidence_match = self._CONFIDENCE_RE.search(report)
        tp_match = self._TP_RE.search(report)
        current_match = self._CURRENT_RE.search(report)

        tp = float(tp_match.group(1).replace(",", "")) if tp_match else None
        current = float(current_match.group(1).replace(",", "")) if current_match else None
        upside = ((tp - current) / current * 100) if tp and current else None

        confidence_str = confidence_match.group(1).upper() if confidence_match else "MEDIUM"

        return TradingSignal(
            ticker=ticker,
            signal_type=SignalType(signal_match.group(1).upper()),
            confidence=ConfidenceLevel.from_string(confidence_str),
            target_price=tp,
            current_price=current,
            upside_pct=upside,
            analyst_report=report,
        )
