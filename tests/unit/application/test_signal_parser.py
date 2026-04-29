"""Unit tests for SignalParserService."""
from __future__ import annotations

import pytest

from src.application.services.signal_parser import SignalParserService
from src.domain.entities.signal import ConfidenceLevel, SignalType
from src.domain.exceptions import SignalParseError

FULL_REPORT = """\
# Samsung Electronics (005930) — Broker Report

## Summary
Investment Opinion: BUY
Confidence: MEDIUM-HIGH
12-Month Target Price: ₩90,000
Current Price: ₩75,000

### Rationale
Strong fundamentals with semiconductor cycle recovery.
"""

SELL_REPORT = """\
Investment Opinion: SELL
Confidence: HIGH
12-Month Target Price: $120
Current Price: $150
"""

HOLD_NO_PRICE_REPORT = """\
Investment Opinion: HOLD
Confidence: LOW
"""

MISSING_OPINION_REPORT = """\
# Report without opinion field
Confidence: HIGH
12-Month Target Price: ₩90,000
Current Price: ₩75,000
"""

JSON_REPORT = """\
{
  "ticker": "005930",
  "investment_opinion": "BUY",
  "confidence": "MEDIUM-HIGH",
  "target_price": 90000,
  "current_price": "₩75,000",
  "investment_thesis": [{"title": "Memory cycle recovery", "evidence": "DRAM pricing improves."}],
  "risks": ["Memory cycle reversal"],
  "catalysts": ["HBM order growth"],
  "markdown_report": "# Samsung report"
}
"""


@pytest.fixture
def parser() -> SignalParserService:
    return SignalParserService()


class TestSignalParserService:
    def test_parse_buy_signal(self, parser: SignalParserService):
        sig = parser.parse("005930", FULL_REPORT)
        assert sig.signal_type == SignalType.BUY
        assert sig.confidence == ConfidenceLevel.MEDIUM_HIGH
        assert sig.target_price == 90_000.0
        assert sig.current_price == 75_000.0
        assert sig.upside_pct == pytest.approx(20.0)
        assert sig.ticker == "005930"

    def test_parse_sell_signal(self, parser: SignalParserService):
        sig = parser.parse("AAPL", SELL_REPORT)
        assert sig.signal_type == SignalType.SELL
        assert sig.confidence == ConfidenceLevel.HIGH
        assert sig.target_price == 120.0
        assert sig.current_price == 150.0
        assert sig.upside_pct == pytest.approx(-20.0)

    def test_parse_hold_without_prices(self, parser: SignalParserService):
        sig = parser.parse("005930", HOLD_NO_PRICE_REPORT)
        assert sig.signal_type == SignalType.HOLD
        assert sig.confidence == ConfidenceLevel.LOW
        assert sig.target_price is None
        assert sig.current_price is None
        assert sig.upside_pct is None

    def test_missing_opinion_raises(self, parser: SignalParserService):
        with pytest.raises(SignalParseError):
            parser.parse("005930", MISSING_OPINION_REPORT)

    def test_missing_confidence_defaults_medium(self, parser: SignalParserService):
        report = "Investment Opinion: BUY\n12-Month Target Price: ₩80,000\nCurrent Price: ₩75,000"
        sig = parser.parse("005930", report)
        assert sig.confidence == ConfidenceLevel.MEDIUM

    def test_report_stored_verbatim(self, parser: SignalParserService):
        sig = parser.parse("005930", FULL_REPORT)
        assert sig.analyst_report == FULL_REPORT

    def test_case_insensitive_parsing(self, parser: SignalParserService):
        report = (
            "investment opinion: buy\n"
            "confidence: high\n"
            "12-Month Target Price: ₩90,000\n"
            "Current Price: ₩75,000"
        )
        sig = parser.parse("005930", report)
        assert sig.signal_type == SignalType.BUY

    def test_parse_structured_json_report(self, parser: SignalParserService):
        sig = parser.parse("005930", JSON_REPORT)
        assert sig.signal_type == SignalType.BUY
        assert sig.confidence == ConfidenceLevel.MEDIUM_HIGH
        assert sig.target_price == 90_000.0
        assert sig.current_price == 75_000.0
        assert sig.upside_pct == pytest.approx(20.0)
        assert sig.analyst_report == JSON_REPORT
