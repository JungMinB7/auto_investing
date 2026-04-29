"""Alpaca Markets REST API adapter — BrokerPort implementation for US stocks/ETFs.

Paper trading: https://paper-api.alpaca.markets  (default)
Live trading:  https://api.alpaca.markets

Requires:
    ALPACA_API_KEY / ALPACA_SECRET_KEY in .env
    ALPACA_IS_PAPER=true for simulation (default)

Price data fetched from Alpaca's market data endpoint.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx

from src.application.ports.broker_port import BrokerPort
from src.domain.entities.trade import OrderSide, OrderType
from src.domain.exceptions import BrokerError

logger = logging.getLogger(__name__)

_PAPER_TRADING_URL = "https://paper-api.alpaca.markets"
_LIVE_TRADING_URL = "https://api.alpaca.markets"
_DATA_URL = "https://data.alpaca.markets"


class AlpacaBrokerAdapter(BrokerPort):
    """Alpaca Markets REST 어댑터 — 미국 주식·ETF 거래 지원.

    Paper mode: 네트워크 호출 없이 주문 시뮬레이션.
    """

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        is_paper: bool = True,
    ) -> None:
        self._api_key = api_key
        self._secret_key = secret_key
        self._is_paper = is_paper
        base_url = _PAPER_TRADING_URL if is_paper else _LIVE_TRADING_URL
        self._client = httpx.AsyncClient(base_url=base_url, timeout=10.0)
        self._data_client = httpx.AsyncClient(base_url=_DATA_URL, timeout=10.0)

    def _auth_headers(self) -> dict[str, str]:
        return {
            "APCA-API-KEY-ID": self._api_key,
            "APCA-API-SECRET-KEY": self._secret_key,
            "Content-Type": "application/json",
        }

    # ── BrokerPort 구현 ─────────────────────────────────────

    async def place_order(
        self,
        ticker: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: int,
        price: float | None,
    ) -> str:
        if self._is_paper:
            paper_id = f"ALPACA-PAPER-{ticker}-{datetime.utcnow().strftime('%H%M%S%f')[:14]}"
            logger.info(
                "[ALPACA-PAPER] %s %s qty=%d price=%s → %s",
                side.value, ticker, quantity, price, paper_id,
            )
            return paper_id

        payload: dict[str, Any] = {
            "symbol": ticker,
            "qty": str(quantity),
            "side": side.value.lower(),
            "type": "limit" if order_type == OrderType.LIMIT else "market",
            "time_in_force": "day",
        }
        if order_type == OrderType.LIMIT and price is not None:
            payload["limit_price"] = f"{price:.4f}"

        try:
            resp = await self._client.post(
                "/v2/orders", headers=self._auth_headers(), json=payload
            )
        except httpx.TimeoutException as exc:
            raise BrokerError(f"Alpaca order timed out for {ticker}") from exc

        if resp.status_code == 429:
            raise BrokerError("Alpaca API rate limit exceeded")
        if resp.status_code not in (200, 201):
            raise BrokerError(
                f"Alpaca order failed for {ticker}: HTTP {resp.status_code} — {resp.text[:200]}"
            )

        data = resp.json()
        order_id: str = data["id"]
        logger.info("Alpaca order placed: %s %s qty=%d → %s", ticker, side.value, quantity, order_id)
        return order_id

    async def get_current_price(self, ticker: str) -> float:
        """최신 거래 가격 조회 (USD). 마켓 데이터 API 사용."""
        if self._is_paper:
            logger.debug("[ALPACA-PAPER] get_current_price(%s) → 100.0", ticker)
            return 100.0

        try:
            resp = await self._data_client.get(
                f"/v2/stocks/{ticker}/trades/latest",
                headers=self._auth_headers(),
                params={"feed": "iex"},
            )
        except httpx.TimeoutException as exc:
            raise BrokerError(f"Alpaca price query timed out for {ticker}") from exc

        if resp.status_code == 200:
            data = resp.json()
            trade = data.get("trade") or {}
            if "p" in trade:
                return float(trade["p"])

        # 폴백: 최신 스냅샷 사용
        try:
            snap_resp = await self._data_client.get(
                f"/v2/stocks/{ticker}/snapshot",
                headers=self._auth_headers(),
                params={"feed": "iex"},
            )
            if snap_resp.status_code == 200:
                snap = snap_resp.json()
                lp = snap.get("latestTrade", {}).get("p")
                if lp:
                    return float(lp)
        except Exception:
            pass

        raise BrokerError(f"Cannot get price for {ticker} from Alpaca")

    async def get_positions(self) -> list[dict[str, Any]]:
        if self._is_paper:
            return []
        try:
            resp = await self._client.get("/v2/positions", headers=self._auth_headers())
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            logger.warning("Failed to fetch Alpaca positions", exc_info=True)
        return []

    async def get_balance(self) -> float:
        """주문 가능 금액 (USD)."""
        if self._is_paper:
            return 10_000.0

        try:
            resp = await self._client.get("/v2/account", headers=self._auth_headers())
            if resp.status_code == 200:
                return float(resp.json().get("buying_power", 0.0))
        except Exception:
            logger.warning("Failed to fetch Alpaca balance", exc_info=True)
        return 0.0

    async def close(self) -> None:
        await self._client.aclose()
        await self._data_client.aclose()
