"""Unit tests for AnalyzeStockUseCase."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.application.ports.analyst_port import AnalystRequest
from src.application.services.signal_parser import SignalParserService
from src.application.use_cases.analyze_stock import AnalyzeStockRequest, AnalyzeStockUseCase
from src.domain.entities.signal import ConfidenceLevel, SignalType

_REPORT = """\
Investment Opinion: BUY
Confidence: HIGH
12-Month Target Price: ₩90,000
Current Price: ₩75,000
"""


@pytest.fixture
def analyst_port():
    mock = AsyncMock()
    mock.analyze.return_value = _REPORT
    return mock


@pytest.fixture
def signal_repo():
    mock = AsyncMock()
    mock.save = AsyncMock()
    return mock


@pytest.fixture
def quant_research():
    mock = AsyncMock()
    mock.build_context.return_value = "Quant precheck status: RUN"
    return mock


@pytest.fixture
def use_case(analyst_port, signal_repo):
    parser = SignalParserService()
    return AnalyzeStockUseCase(analyst=analyst_port, signal_parser=parser, signal_repo=signal_repo)


class TestAnalyzeStockUseCase:
    @pytest.mark.asyncio
    async def test_returns_parsed_signal(self, use_case, analyst_port, signal_repo):
        result = await use_case.execute(AnalyzeStockRequest(ticker="005930"))
        assert result.signal.signal_type == SignalType.BUY
        assert result.signal.confidence == ConfidenceLevel.HIGH
        assert result.signal.ticker == "005930"
        assert result.raw_report == _REPORT

    @pytest.mark.asyncio
    async def test_saves_signal_to_repo(self, use_case, signal_repo):
        await use_case.execute(AnalyzeStockRequest(ticker="005930"))
        signal_repo.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_calls_analyst_with_ticker(self, use_case, analyst_port):
        await use_case.execute(AnalyzeStockRequest(ticker="005930"))
        analyst_port.analyze.assert_called_once_with(
            AnalystRequest(
                ticker="005930",
                force_quant=False,
                include_charts=False,
                quant_context=None,
            )
        )

    @pytest.mark.asyncio
    async def test_injects_quant_context_when_requested(
        self,
        analyst_port,
        signal_repo,
        quant_research,
    ):
        parser = SignalParserService()
        use_case = AnalyzeStockUseCase(
            analyst=analyst_port,
            signal_parser=parser,
            signal_repo=signal_repo,
            quant_research=quant_research,
        )

        await use_case.execute(
            AnalyzeStockRequest(ticker="005930", force_quant=True, include_charts=True)
        )

        quant_research.build_context.assert_called_once_with("005930")
        analyst_port.analyze.assert_called_once_with(
            AnalystRequest(
                ticker="005930",
                force_quant=True,
                include_charts=True,
                quant_context="Quant precheck status: RUN",
            )
        )

    @pytest.mark.asyncio
    async def test_enable_quant_context_does_not_force_quant_mode(
        self,
        analyst_port,
        signal_repo,
        quant_research,
    ):
        parser = SignalParserService()
        use_case = AnalyzeStockUseCase(
            analyst=analyst_port,
            signal_parser=parser,
            signal_repo=signal_repo,
            quant_research=quant_research,
            enable_quant_context=True,
        )

        await use_case.execute(AnalyzeStockRequest(ticker="005930"))

        analyst_port.analyze.assert_called_once_with(
            AnalystRequest(
                ticker="005930",
                force_quant=False,
                include_charts=False,
                quant_context="Quant precheck status: RUN",
            )
        )
