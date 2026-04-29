from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from typing import Any

from src.application.ports.quant_research_port import QuantResearchPort

logger = logging.getLogger(__name__)


class VectorbtQuantResearchAdapter(QuantResearchPort):
    """vectorbt 기반 퀀트 사전검증 어댑터.

    이 어댑터는 거래 결정을 직접 내리지 않고, Claude의 quant-research 스킬이 참고할
    재현 가능한 백테스트/팩터 컨텍스트만 만든다. 선택 의존성이 없으면 명시적인
    UNAVAILABLE 컨텍스트를 반환해 분석 파이프라인을 멈추지 않는다.
    """

    def __init__(self, lookback_days: int = 365, provider: str = "yfinance") -> None:
        self._lookback_days = lookback_days
        self._provider = provider

    async def build_context(self, ticker: str) -> str:
        return await asyncio.to_thread(self._build_context_sync, ticker)

    def _build_context_sync(self, ticker: str) -> str:
        missing = self._missing_optional_dependencies()
        if missing:
            return (
                "Quant precheck status: UNAVAILABLE\n"
                f"Reason: missing optional packages: {', '.join(missing)}\n"
                "Install with: pip install 'auto-investing[backtest]' and configure OpenBB.\n"
                "Do not invent backtest metrics; report quant_signals.status='UNAVAILABLE'."
            )

        try:
            close = self._load_close_prices(ticker)
            if close is None or len(close) < 80:
                return (
                    "Quant precheck status: UNAVAILABLE\n"
                    "Reason: insufficient historical close prices for robust MA/RS test.\n"
                    "Do not invent backtest metrics; report quant_signals.status='UNAVAILABLE'."
                )
            return self._run_vectorbt_summary(ticker, close)
        except Exception as exc:
            logger.warning("Quant precheck failed for %s: %s", ticker, exc)
            return (
                "Quant precheck status: UNAVAILABLE\n"
                f"Reason: {type(exc).__name__}: {exc}\n"
                "Do not invent backtest metrics; report quant_signals.status='UNAVAILABLE'."
            )

    @staticmethod
    def _missing_optional_dependencies() -> list[str]:
        missing: list[str] = []
        for module_name in ("pandas", "numpy", "vectorbt", "openbb"):
            try:
                __import__(module_name)
            except Exception:
                missing.append(module_name)
        return missing

    def _load_close_prices(self, ticker: str) -> Any:
        from openbb import obb

        symbol = self._openbb_symbol(ticker)
        start_date = (date.today() - timedelta(days=self._lookback_days)).isoformat()
        result = obb.equity.price.historical(
            symbol=symbol,
            start_date=start_date,
            provider=self._provider,
        )
        df = result.to_dataframe()
        for col in ("close", "Close", "adj_close", "Adj Close"):
            if col in df.columns:
                return df[col].dropna()
        return None

    @staticmethod
    def _openbb_symbol(ticker: str) -> str:
        clean = ticker.split()[0].strip().upper()
        if clean.isdigit() and len(clean) == 6:
            return f"{clean}.KS"
        return clean

    @staticmethod
    def _run_vectorbt_summary(ticker: str, close: Any) -> str:
        import vectorbt as vbt

        fast_ma = vbt.MA.run(close, 20)
        slow_ma = vbt.MA.run(close, 60)
        entries = fast_ma.ma_crossed_above(slow_ma)
        exits = fast_ma.ma_crossed_below(slow_ma)
        portfolio = vbt.Portfolio.from_signals(
            close,
            entries,
            exits,
            init_cash=10_000_000,
            fees=0.001,
        )
        stats = portfolio.stats()

        total_return = _safe_stat(stats, "Total Return [%]")
        max_drawdown = _safe_stat(stats, "Max Drawdown [%]")
        sharpe = _safe_stat(stats, "Sharpe Ratio")
        win_rate = _safe_stat(stats, "Win Rate [%]")
        six_month_return = (close.iloc[-1] / close.iloc[max(0, len(close) - 126)] - 1.0) * 100.0

        if six_month_return > 20:
            momentum = "POSITIVE"
        elif six_month_return < -10:
            momentum = "NEGATIVE"
        else:
            momentum = "NEUTRAL"

        return "\n".join(
            [
                "Quant precheck status: RUN",
                f"Ticker: {ticker}",
                "Strategy: 20D/60D moving-average crossover, long-only, fees=0.10%",
                f"Lookback observations: {len(close)}",
                f"6M price momentum: {six_month_return:.2f}%",
                f"Momentum signal: {momentum}",
                f"Backtest total return: {_fmt(total_return)}%",
                f"Backtest max drawdown: {_fmt(max_drawdown)}%",
                f"Backtest Sharpe ratio: {_fmt(sharpe)}",
                f"Backtest win rate: {_fmt(win_rate)}%",
                "Use these as supporting evidence only; validate data quality before trading.",
            ]
        )


def _safe_stat(stats: Any, key: str) -> float | None:
    try:
        value = stats.get(key)
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _fmt(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.2f}"
