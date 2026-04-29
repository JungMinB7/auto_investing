from __future__ import annotations

import logging

from src.application.ports.notifier_port import NotifierPort
from src.application.use_cases.analyze_stock import AnalyzeStockRequest, AnalyzeStockUseCase
from src.application.use_cases.execute_trade import ExecuteTradeRequest, ExecuteTradeUseCase
from src.application.use_cases.monitor_position import MonitorPositionUseCase
from src.domain.exceptions import TradingError, TradingHaltedError
from src.domain.repositories.watchlist_repository import WatchlistRepository

logger = logging.getLogger(__name__)


class TradingPipelineService:
    """APScheduler가 호출하는 거래 파이프라인 오케스트레이터."""

    def __init__(
        self,
        analyze_uc: AnalyzeStockUseCase,
        execute_uc: ExecuteTradeUseCase,
        monitor_uc: MonitorPositionUseCase,
        watchlist_repo: WatchlistRepository,
        notifier: NotifierPort,
    ) -> None:
        self._analyze_uc = analyze_uc
        self._execute_uc = execute_uc
        self._monitor_uc = monitor_uc
        self._watchlist_repo = watchlist_repo
        self._notifier = notifier

    async def prepare_market_open(self) -> None:
        """08:50 KST — 장 시작 10분 전 준비."""
        logger.info("Preparing for market open")
        await self._notifier.send("장 시작 준비", "09:00 매매 사이클 시작 예정", 0x3498DB)

    async def run_morning_cycle(self) -> None:
        """09:00 KST — 감시 종목 전체 분석 → 리스크 검증 → 주문 실행."""
        logger.info("Starting morning trading cycle")
        tickers = await self._watchlist_repo.find_active_tickers()
        logger.info("Processing %d tickers from watchlist", len(tickers))

        for ticker in tickers:
            try:
                analyze_resp = await self._analyze_uc.execute(AnalyzeStockRequest(ticker=ticker))
                signal = analyze_resp.signal

                await self._notifier.send_report(ticker, signal, analyze_resp.raw_report)

                if not signal.is_actionable:
                    logger.info("HOLD signal for %s — skipping", ticker)
                    continue

                await self._execute_uc.execute(ExecuteTradeRequest(ticker=ticker, signal=signal))

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
        """워치리스트 즉시 추가 시 단일 종목 분석 → 매수 주문."""
        logger.info("On-demand analysis triggered for %s", ticker)
        try:
            analyze_resp = await self._analyze_uc.execute(AnalyzeStockRequest(ticker=ticker))
            signal = analyze_resp.signal

            await self._notifier.send_report(ticker, signal, analyze_resp.raw_report)

            if not signal.is_actionable:
                logger.info("HOLD signal for %s — no order placed", ticker)
                return

            await self._execute_uc.execute(ExecuteTradeRequest(ticker=ticker, signal=signal))

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
