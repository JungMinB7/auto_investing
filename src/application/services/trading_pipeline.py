from __future__ import annotations

import logging

from src.application.ports.notifier_port import NotifierPort
from src.application.ports.regime_port import MarketRegime, MarketRegimePort
from src.application.use_cases.analyze_stock import AnalyzeStockRequest, AnalyzeStockUseCase
from src.application.use_cases.execute_trade import ExecuteTradeRequest, ExecuteTradeUseCase
from src.application.use_cases.monitor_position import MonitorPositionUseCase
from src.domain.entities.score import SignalScore
from src.domain.exceptions import TradingError, TradingHaltedError
from src.domain.repositories.watchlist_repository import WatchlistRepository
from src.infrastructure.quant.regime_state import RegimeCheckerService

logger = logging.getLogger(__name__)

_DEFAULT_ORDER_THRESHOLD = 80.0
_DEFAULT_NOTIFY_THRESHOLD = 60.0


class TradingPipelineService:
    """APScheduler가 호출하는 거래 파이프라인 오케스트레이터."""

    def __init__(
        self,
        analyze_uc: AnalyzeStockUseCase,
        execute_uc: ExecuteTradeUseCase,
        monitor_uc: MonitorPositionUseCase,
        watchlist_repo: WatchlistRepository,
        notifier: NotifierPort,
        regime_checker: RegimeCheckerService | None = None,
        regime_state: MarketRegimePort | None = None,
        order_threshold: float = _DEFAULT_ORDER_THRESHOLD,
        notify_threshold: float = _DEFAULT_NOTIFY_THRESHOLD,
    ) -> None:
        self._analyze_uc = analyze_uc
        self._execute_uc = execute_uc
        self._monitor_uc = monitor_uc
        self._watchlist_repo = watchlist_repo
        self._notifier = notifier
        self._regime_checker = regime_checker
        self._regime_state = regime_state
        self._order_threshold = order_threshold
        self._notify_threshold = notify_threshold

    async def check_market_regime(self) -> None:
        """08:45 KST — 시장 국면 사전 점검 (Kill Switch 갱신)."""
        if self._regime_checker is None:
            logger.debug("Regime checker not configured — skipping")
            return

        logger.info("Running market regime check")
        try:
            regime = await self._regime_checker.run()
            logger.info("Market regime: %s", regime.value)
            color = {
                MarketRegime.BULL: 0x2ECC71,
                MarketRegime.NEUTRAL: 0x3498DB,
                MarketRegime.BEAR: 0xE74C3C,
            }.get(regime, 0x95A5A6)
            label = {"BULL": "상승장", "NEUTRAL": "중립장", "BEAR": "하락장"}.get(regime.value, regime.value)
            msg = (
                "포지션 크기 50% 축소 적용 중" if regime == MarketRegime.BEAR
                else "정상 포지션 크기 적용"
            )
            await self._notifier.send(
                title=f"📡 시장 국면 점검: {label}",
                message=msg,
                color=color,
            )
        except Exception:
            logger.error("Regime check failed", exc_info=True)

    async def prepare_market_open(self) -> None:
        """08:50 KST — 장 시작 10분 전 준비."""
        logger.info("Preparing for market open")
        regime_str = ""
        if self._regime_state:
            regime_str = f" | 시장 국면: {self._regime_state.get_regime().value}"
        await self._notifier.send(
            "장 시작 준비",
            f"09:00 매매 사이클 시작 예정{regime_str}",
            0x3498DB,
        )

    async def run_morning_cycle(self) -> None:
        """09:00 KST — 감시 종목 전체 분석 → 점수 필터 → 리스크 검증 → 주문."""
        logger.info("Starting morning trading cycle")
        tickers = await self._watchlist_repo.find_active_tickers()
        logger.info("Processing %d tickers from watchlist", len(tickers))

        for ticker in tickers:
            try:
                resp = await self._analyze_uc.execute(AnalyzeStockRequest(ticker=ticker))
                signal = resp.signal
                score: SignalScore | None = resp.score
                trade_score = score.trade_score if score else 50.0

                await self._notifier.send_report(ticker, signal, resp.raw_report)

                action = score.action if score else ("ORDER" if signal.is_actionable else "IGNORE")

                if action == "IGNORE":
                    logger.info(
                        "IGNORE %s — score=%.1f (< %.0f)",
                        ticker, trade_score, self._notify_threshold,
                    )
                    continue

                if action == "NOTIFY":
                    logger.info(
                        "NOTIFY-ONLY %s — score=%.1f (%.0f ~ %.0f)",
                        ticker, trade_score, self._notify_threshold, self._order_threshold,
                    )
                    await self._notifier.send(
                        title=f"📌 관심 알림: {ticker}",
                        message=(
                            f"점수 {trade_score:.0f}점 — 매수 기준 {self._order_threshold:.0f}점 미달\n"
                            f"신호: {signal.signal_type.value} ({signal.confidence.value})"
                        ),
                        color=0xF39C12,
                    )
                    continue

                # action == "ORDER"
                if not signal.is_actionable:
                    logger.info("HOLD signal for %s — skipping order", ticker)
                    continue

                await self._execute_uc.execute(
                    ExecuteTradeRequest(ticker=ticker, signal=signal, trade_score=trade_score)
                )

            except TradingHaltedError:
                logger.warning("Trading halted — stopping morning cycle early")
                await self._notifier.send("거래 중단", "일일 손실 한도 초과로 거래 중단", 0xE74C3C)
                break
            except TradingError as e:
                logger.warning("Trading error for %s: %s", ticker, e)
                await self._notifier.send(f"{ticker} 거래 오류", str(e), 0xFF9900)
            except Exception as e:
                logger.error("Unexpected error for %s", ticker, exc_info=True)
                await self._notifier.send(f"{ticker} 예상치 못한 오류", str(e), 0xE74C3C)

    async def run_position_monitor(self) -> None:
        """30분 간격 — 포지션 모니터링 (손절/익절 경보)."""
        logger.info("Running position monitor")
        try:
            await self._monitor_uc.execute()
        except Exception:
            logger.error("Position monitor failed", exc_info=True)

    async def analyze_and_trade_single(self, ticker: str) -> None:
        """워치리스트 즉시 추가 시 단일 종목 분석 → 점수 필터 → 매수 주문."""
        logger.info("On-demand analysis triggered for %s", ticker)
        try:
            resp = await self._analyze_uc.execute(AnalyzeStockRequest(ticker=ticker))
            signal = resp.signal
            score = resp.score
            trade_score = score.trade_score if score else 50.0

            await self._notifier.send_report(ticker, signal, resp.raw_report)

            action = score.action if score else ("ORDER" if signal.is_actionable else "IGNORE")

            if action == "IGNORE":
                logger.info("IGNORE %s — score=%.1f", ticker, trade_score)
                await self._notifier.send(
                    title=f"📉 분석 완료: {ticker}",
                    message=f"점수 {trade_score:.0f}점 — 매수 기준 미달 (무시)",
                    color=0x95A5A6,
                )
                return

            if action == "NOTIFY":
                await self._notifier.send(
                    title=f"📌 관심 알림: {ticker}",
                    message=f"점수 {trade_score:.0f}점 — 매수 기준 미달 (알림만)",
                    color=0xF39C12,
                )
                return

            if not signal.is_actionable:
                logger.info("HOLD signal for %s — no order placed", ticker)
                return

            await self._execute_uc.execute(
                ExecuteTradeRequest(ticker=ticker, signal=signal, trade_score=trade_score)
            )

        except TradingHaltedError:
            logger.warning("Trading halted — skipping on-demand trade for %s", ticker)
            await self._notifier.send("거래 중단", "일일 손실 한도 초과로 거래 중단", 0xE74C3C)
        except TradingError as e:
            logger.warning("Trading error for %s: %s", ticker, e)
            await self._notifier.send(f"{ticker} 거래 오류", str(e), 0xFF9900)
        except Exception as e:
            logger.error("Unexpected error for %s", ticker, exc_info=True)
            await self._notifier.send(f"{ticker} 예상치 못한 오류", str(e), 0xE74C3C)

    async def run_closing_routine(self) -> None:
        """15:20 KST — 장 마감 10분 전 정리."""
        logger.info("Running closing routine")
        await self._notifier.send("장 마감 준비", "미체결 주문 정리 중 (15:30 장 종료)", 0x95A5A6)
