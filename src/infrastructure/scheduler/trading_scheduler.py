"""APScheduler-based trading scheduler.

4 cron jobs in KST timezone:
  08:50 — prepare_market_open  (pre-market setup)
  09:00 — run_morning_cycle    (analysis + orders)
  every 30 min — run_position_monitor (stop-loss / take-profit)
  15:20 — run_closing_routine  (EOD cleanup)
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.application.services.trading_pipeline import TradingPipelineService

logger = logging.getLogger(__name__)

_KST = "Asia/Seoul"


class TradingScheduler:
    """APScheduler wrapper for the 5-job KRX+US trading schedule."""

    def __init__(self, pipeline: TradingPipelineService) -> None:
        self._pipeline = pipeline
        self._scheduler = AsyncIOScheduler(timezone=_KST)
        self._register_jobs()

    def _register_jobs(self) -> None:
        self._scheduler.add_job(
            self._pipeline.check_market_regime,
            CronTrigger(hour=8, minute=45, timezone=_KST),
            id="check_market_regime",
            name="Market regime check (Kill Switch)",
            misfire_grace_time=60,
        )
        self._scheduler.add_job(
            self._pipeline.prepare_market_open,
            CronTrigger(hour=8, minute=50, timezone=_KST),
            id="prepare_market_open",
            name="Pre-market setup",
            misfire_grace_time=60,
        )
        self._scheduler.add_job(
            self._pipeline.run_morning_cycle,
            CronTrigger(hour=9, minute=0, timezone=_KST),
            id="run_morning_cycle",
            name="Morning analysis + orders",
            misfire_grace_time=120,
        )
        self._scheduler.add_job(
            self._pipeline.run_position_monitor,
            IntervalTrigger(minutes=30),
            id="run_position_monitor",
            name="Position monitor (stop-loss/take-profit)",
        )
        self._scheduler.add_job(
            self._pipeline.run_closing_routine,
            CronTrigger(hour=15, minute=20, timezone=_KST),
            id="run_closing_routine",
            name="EOD closing routine",
            misfire_grace_time=60,
        )
        logger.info("TradingScheduler: 5 jobs registered")

    def start(self) -> None:
        self._scheduler.start()
        logger.info("TradingScheduler started")

    def shutdown(self, wait: bool = False) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=wait)
            logger.info("TradingScheduler stopped")

    @property
    def running(self) -> bool:
        return self._scheduler.running
