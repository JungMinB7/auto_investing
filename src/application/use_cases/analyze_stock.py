from __future__ import annotations

from dataclasses import dataclass

from src.application.ports.analyst_port import AnalystPort
from src.application.services.signal_parser import SignalParserService
from src.domain.entities.signal import TradingSignal
from src.domain.repositories.signal_repository import SignalRepository


@dataclass
class AnalyzeStockRequest:
    ticker: str


@dataclass
class AnalyzeStockResponse:
    signal: TradingSignal
    raw_report: str


class AnalyzeStockUseCase:
    """ticker → ClaudeAnalystAdapter → SignalParser → TradingSignal 저장."""

    def __init__(
        self,
        analyst: AnalystPort,
        signal_parser: SignalParserService,
        signal_repo: SignalRepository,
    ) -> None:
        self._analyst = analyst
        self._parser = signal_parser
        self._signal_repo = signal_repo

    async def execute(self, request: AnalyzeStockRequest) -> AnalyzeStockResponse:
        raw_report = await self._analyst.analyze(request.ticker)
        signal = self._parser.parse(request.ticker, raw_report)
        await self._signal_repo.save(signal)
        return AnalyzeStockResponse(signal=signal, raw_report=raw_report)
