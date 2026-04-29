"""FastAPI application entry point.

Lifespan:
  startup  → TradingContainer.init_resources() → container.wire() → scheduler.start()
  shutdown → scheduler.shutdown() → container.shutdown_resources()
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.presentation.api.v1 import health, orders, positions, risk, scheduler, signals, watchlist
from src.presentation.dependencies import TradingContainer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

container = TradingContainer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting auto-trading-engine …")
    await container.init_resources()
    container.wire(
        modules=[
            "src.presentation.api.v1.health",
            "src.presentation.api.v1.positions",
            "src.presentation.api.v1.orders",
            "src.presentation.api.v1.signals",
            "src.presentation.api.v1.watchlist",
            "src.presentation.api.v1.risk",
            "src.presentation.api.v1.scheduler",
        ]
    )

    sched = await container.scheduler.async_()
    sched.start()
    logger.info("TradingScheduler started")

    yield

    logger.info("Shutting down …")
    sched.shutdown(wait=False)
    await container.shutdown_resources()
    logger.info("Shutdown complete")


app = FastAPI(
    title="auto-trading-engine",
    description="Fully automated KRX stock trading engine",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(positions.router)
app.include_router(orders.router)
app.include_router(signals.router)
app.include_router(watchlist.router)
app.include_router(risk.router)
app.include_router(scheduler.router)
