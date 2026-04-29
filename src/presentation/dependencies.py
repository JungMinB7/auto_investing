"""dependency-injector DI container for the trading engine.

Design Ref: §5.4 TradingContainer

FastAPI routers import Provide[TradingContainer.xyz] and use @inject decorator.
Call container.wire(modules=[...]) in main.py lifespan to activate wiring.
Call container.init_resources() / container.shutdown_resources() for lifecycle.
"""
from __future__ import annotations

import redis.asyncio as aioredis
from dependency_injector import containers, providers

from src.application.services.risk_guard import RiskGuardService
from src.application.services.signal_parser import SignalParserService
from src.application.services.trading_pipeline import TradingPipelineService
from src.application.use_cases.analyze_stock import AnalyzeStockUseCase
from src.application.use_cases.execute_trade import ExecuteTradeUseCase
from src.application.use_cases.monitor_position import MonitorPositionUseCase
from src.core.settings import Settings
from src.domain.entities.risk_rule import RiskRule
from src.domain.entities.signal import ConfidenceLevel
from src.infrastructure.claude.claude_analyst import ClaudeAnalystAdapter
from src.infrastructure.db.audit_logger import PostgresAuditLogger
from src.infrastructure.db.repositories.postgres_position_repo import PostgresPositionRepository
from src.infrastructure.db.repositories.postgres_risk_snapshot_repo import PostgresRiskSnapshotRepository
from src.infrastructure.db.repositories.postgres_signal_repo import PostgresSignalRepository
from src.infrastructure.db.repositories.postgres_trade_repo import PostgresTradeRepository
from src.infrastructure.db.repositories.postgres_watchlist_repo import PostgresWatchlistRepository
from src.infrastructure.db.session import create_async_session_factory
from src.infrastructure.discord.discord_notifier import DiscordNotifierAdapter
from src.infrastructure.kiwoom.kiwoom_adapter import KiwoomRestAdapter
from src.infrastructure.redis.distributed_lock import RedisDistributedLock
from src.infrastructure.redis.price_cache import RedisPriceCacheAdapter
from src.infrastructure.scheduler.trading_scheduler import TradingScheduler


def _make_risk_rule(settings: Settings) -> RiskRule:
    balance = 10_000_000.0  # 1천만원 기준 잔고 (paper mode)
    return RiskRule(
        max_daily_loss_krw=settings.max_daily_loss_pct / 100.0 * balance,
        max_position_count=settings.max_position_count,
        max_position_krw=settings.max_position_size_pct / 100.0 * balance,
        max_position_pct=settings.max_position_size_pct,
        min_signal_confidence=ConfidenceLevel(settings.min_confidence),
    )


def _max_position_krw(settings: Settings) -> float:
    return settings.max_position_size_pct / 100.0 * 10_000_000.0


class TradingContainer(containers.DeclarativeContainer):
    """DI container — wire once in lifespan, resolve per-request via Provide[...]."""

    wiring_config = containers.WiringConfiguration(
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

    # ── Configuration ────────────────────────────────────────
    config = providers.Singleton(Settings)

    # ── Infrastructure: Kiwoom ───────────────────────────────
    kiwoom = providers.Singleton(
        KiwoomRestAdapter,
        app_key=config.provided.kiwoom_app_key,
        secret_key=config.provided.kiwoom_secret_key,
        account_no=config.provided.kiwoom_account_no,
        is_paper=config.provided.kiwoom_is_paper,
    )

    # ── Infrastructure: Claude ───────────────────────────────
    claude = providers.Singleton(
        ClaudeAnalystAdapter,
        api_key=config.provided.anthropic_api_key,
    )

    # ── Infrastructure: DB session factory (Resource) ────────
    db_session_factory = providers.Resource(
        create_async_session_factory,
        db_url=config.provided.database_url,
    )

    # ── Infrastructure: Redis ────────────────────────────────
    redis_client = providers.Singleton(
        aioredis.from_url,
        config.provided.redis_url,
        encoding="utf-8",
        decode_responses=False,
    )

    price_cache = providers.Singleton(
        RedisPriceCacheAdapter,
        client=redis_client,
    )

    distributed_lock = providers.Singleton(
        RedisDistributedLock,
        client=redis_client,
    )

    # ── Infrastructure: Discord ──────────────────────────────
    discord = providers.Singleton(
        DiscordNotifierAdapter,
        webhook_url=config.provided.discord_webhook_url,
    )

    # ── Domain: RiskRule ─────────────────────────────────────
    risk_rule = providers.Singleton(_make_risk_rule, config)

    # ── Repositories (Factory — new session per call) ────────
    trade_repo = providers.Factory(
        PostgresTradeRepository,
        session_factory=db_session_factory,
    )

    signal_repo = providers.Factory(
        PostgresSignalRepository,
        session_factory=db_session_factory,
    )

    position_repo = providers.Factory(
        PostgresPositionRepository,
        session_factory=db_session_factory,
    )

    risk_snapshot_repo = providers.Factory(
        PostgresRiskSnapshotRepository,
        session_factory=db_session_factory,
    )

    watchlist_repo = providers.Factory(
        PostgresWatchlistRepository,
        session_factory=db_session_factory,
    )

    audit_logger = providers.Factory(
        PostgresAuditLogger,
        session_factory=db_session_factory,
    )

    # ── Application Services ─────────────────────────────────
    signal_parser = providers.Singleton(SignalParserService)

    risk_guard = providers.Singleton(
        RiskGuardService,
        rule=risk_rule,
        position_repo=position_repo,
        snapshot_repo=risk_snapshot_repo,
    )

    max_position_krw = providers.Callable(_max_position_krw, config)

    # ── Use Cases ────────────────────────────────────────────
    analyze_stock_uc = providers.Factory(
        AnalyzeStockUseCase,
        analyst=claude,
        signal_parser=signal_parser,
        signal_repo=signal_repo,
    )

    execute_trade_uc = providers.Factory(
        ExecuteTradeUseCase,
        broker=kiwoom,
        risk_guard=risk_guard,
        trade_repo=trade_repo,
        lock=distributed_lock,
        audit=audit_logger,
        notifier=discord,
        max_position_krw=max_position_krw,
    )

    monitor_position_uc = providers.Factory(
        MonitorPositionUseCase,
        position_repo=position_repo,
        broker=kiwoom,
        risk_guard=risk_guard,
        notifier=discord,
    )

    # ── Pipeline & Scheduler ─────────────────────────────────
    trading_pipeline = providers.Singleton(
        TradingPipelineService,
        analyze_uc=analyze_stock_uc,
        execute_uc=execute_trade_uc,
        monitor_uc=monitor_position_uc,
        watchlist_repo=watchlist_repo,
        notifier=discord,
    )

    scheduler = providers.Singleton(
        TradingScheduler,
        pipeline=trading_pipeline,
    )
