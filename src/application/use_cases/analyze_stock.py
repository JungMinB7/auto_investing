from __future__ import annotations

from dataclasses import dataclass, field

from src.application.ports.analyst_port import AnalystPort, AnalystRequest
from src.application.ports.quant_research_port import QuantResearchPort
from src.application.services.report_payload import extract_json_payload
from src.application.services.score_calculator import ScoreCalculatorService
from src.application.services.signal_parser import SignalParserService
from src.domain.entities.score import SignalScore
from src.domain.entities.signal import TradingSignal
from src.domain.repositories.signal_repository import SignalRepository


@dataclass
class AnalyzeStockRequest:
    ticker: str
    force_quant: bool = False
    include_charts: bool = False


@dataclass
class AnalyzeStockResponse:
    signal: TradingSignal
    raw_report: str
    score: SignalScore | None = field(default=None)


class AnalyzeStockUseCase:
    """ticker → quant context → Claude → SignalParser → ScoreCalculator → 저장."""

    def __init__(
        self,
        analyst: AnalystPort,
        signal_parser: SignalParserService,
        signal_repo: SignalRepository,
        quant_research: QuantResearchPort | None = None,
        score_calculator: ScoreCalculatorService | None = None,
        enable_quant_context: bool = False,
        include_charts: bool = False,
    ) -> None:
        self._analyst = analyst
        self._parser = signal_parser
        self._signal_repo = signal_repo
        self._quant_research = quant_research
        self._score_calculator = score_calculator
        self._enable_quant_context = enable_quant_context
        self._include_charts = include_charts

    async def execute(self, request: AnalyzeStockRequest) -> AnalyzeStockResponse:
        force_quant = request.force_quant
        include_charts = request.include_charts or self._include_charts
        quant_context = await self._build_quant_context(
            request.ticker,
            request.force_quant or self._enable_quant_context,
        )

        raw_report = await self._analyst.analyze(
            AnalystRequest(
                ticker=request.ticker,
                force_quant=force_quant,
                include_charts=include_charts,
                quant_context=quant_context,
            )
        )
        signal = self._parser.parse(request.ticker, raw_report)

        # 점수 계산 + signal에 반영
        score: SignalScore | None = None
        if self._score_calculator is not None:
            payload = extract_json_payload(raw_report)
            score = self._score_calculator.calculate(payload)
            signal.trade_score = score.trade_score

        await self._signal_repo.save(signal)
        return AnalyzeStockResponse(signal=signal, raw_report=raw_report, score=score)

    async def _build_quant_context(self, ticker: str, enabled: bool) -> str | None:
        if not enabled or self._quant_research is None:
            return None
        return await self._quant_research.build_context(ticker)
