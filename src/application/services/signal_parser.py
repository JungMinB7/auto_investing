from __future__ import annotations

import re
from typing import Any

from src.application.services.report_payload import extract_json_payload, get_nested, parse_price
from src.domain.entities.signal import ConfidenceLevel, SignalType, TradingSignal
from src.domain.exceptions import SignalParseError


class SignalParserService:
    """pro-securities-analyst 리포트에서 TradingSignal을 추출.

    운영 경로는 Claude JSON을 우선 파싱하고, 과거 리포트/테스트 호환을 위해 Markdown
    정규식 파서를 보조 경로로 유지한다.
    """

    _SIGNAL_RE = re.compile(r"Investment Opinion:\s*(BUY|HOLD|SELL)", re.IGNORECASE)
    _CONFIDENCE_RE = re.compile(r"Confidence:\s*(HIGH|MEDIUM-HIGH|MEDIUM|LOW)", re.IGNORECASE)
    _TP_RE = re.compile(r"12-Month Target Price:.*?([\d,]+)", re.IGNORECASE)
    _CURRENT_RE = re.compile(r"Current Price:.*?([\d,]+)", re.IGNORECASE)

    def parse(self, ticker: str, report: str) -> TradingSignal:
        payload = extract_json_payload(report)
        if payload is not None:
            return self._parse_json(ticker, report, payload)

        return self._parse_markdown(ticker, report)

    def _parse_json(self, ticker: str, report: str, payload: dict[str, Any]) -> TradingSignal:
        opinion_raw = get_nested(payload, "investment_opinion", "signal_type", "opinion")
        if not isinstance(opinion_raw, str):
            raise SignalParseError(
                f"Cannot find 'investment_opinion: BUY/HOLD/SELL' in analyst JSON for {ticker}"
            )

        opinion = opinion_raw.upper().strip()
        if opinion not in {"BUY", "HOLD", "SELL"}:
            raise SignalParseError(f"Unsupported investment opinion {opinion_raw!r} for {ticker}")

        confidence_raw = get_nested(payload, "confidence", "rating.confidence") or "MEDIUM"
        confidence = str(confidence_raw).upper().strip()

        target_price = parse_price(
            get_nested(payload, "target_price", "prices.target_price", "valuation.target_price")
        )
        current_price = parse_price(get_nested(payload, "current_price", "prices.current_price"))
        upside_pct = parse_price(get_nested(payload, "upside_pct", "prices.upside_pct"))
        if upside_pct is None and target_price is not None and current_price:
            upside_pct = (target_price - current_price) / current_price * 100

        return TradingSignal(
            ticker=str(get_nested(payload, "ticker", "symbol") or ticker),
            signal_type=SignalType(opinion),
            confidence=ConfidenceLevel.from_string(confidence),
            target_price=target_price,
            current_price=current_price,
            upside_pct=upside_pct,
            analyst_report=report,
        )

    def _parse_markdown(self, ticker: str, report: str) -> TradingSignal:
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
