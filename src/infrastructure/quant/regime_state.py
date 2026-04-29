from __future__ import annotations

import logging
import threading

from src.application.ports.quant_research_port import QuantResearchPort
from src.application.ports.regime_port import MarketRegime, MarketRegimePort

logger = logging.getLogger(__name__)


class InMemoryRegimeStateAdapter(MarketRegimePort):
    """프로세스 내 메모리 기반 시장 상태 저장소.

    APScheduler가 매일 08:45에 set_regime()을 호출해 갱신한다.
    재시작 시 NEUTRAL로 초기화되므로 첫 번째 장전 체크 전까지는 보수적으로 중립 유지.
    """

    def __init__(self) -> None:
        self._regime = MarketRegime.NEUTRAL
        self._lock = threading.Lock()

    def get_regime(self) -> MarketRegime:
        with self._lock:
            return self._regime

    def set_regime(self, regime: MarketRegime) -> None:
        with self._lock:
            prev = self._regime
            self._regime = regime
        if prev != regime:
            logger.info("Market regime changed: %s → %s", prev.value, regime.value)


class RegimeCheckerService:
    """KOSPI 지수의 퀀트 컨텍스트를 해석해 MarketRegime를 결정한다.

    vectorbt / OpenBB가 없으면 UNAVAILABLE 컨텍스트를 받아 NEUTRAL로 폴백.
    """

    _KOSPI_TICKER = "^KS11"
    _KOSDAQ_TICKER = "^KQ11"

    def __init__(self, quant: QuantResearchPort, state: MarketRegimePort) -> None:
        self._quant = quant
        self._state = state

    async def run(self) -> MarketRegime:
        try:
            kospi_ctx = await self._quant.build_context(self._KOSPI_TICKER)
            regime = self._infer(kospi_ctx)
        except Exception:
            logger.warning("Regime check failed; defaulting to NEUTRAL", exc_info=True)
            regime = MarketRegime.NEUTRAL

        self._state.set_regime(regime)
        return regime

    @staticmethod
    def _infer(context: str) -> MarketRegime:
        if "UNAVAILABLE" in context:
            return MarketRegime.NEUTRAL
        upper = context.upper()
        if "MOMENTUM SIGNAL: NEGATIVE" in upper:
            return MarketRegime.BEAR
        if "MOMENTUM SIGNAL: POSITIVE" in upper:
            return MarketRegime.BULL
        return MarketRegime.NEUTRAL
