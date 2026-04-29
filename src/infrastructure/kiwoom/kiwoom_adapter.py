"""Kiwoom REST API adapter — BrokerPort implementation.

Design Ref: §5.1 KiwoomRestAdapter

Endpoint paths follow the KIS Developers API specification.
Verify actual paths against official documentation before production use.
Paper trading mode (is_paper=True) simulates all order calls without network I/O.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx

from src.application.ports.broker_port import BrokerPort
from src.domain.entities.trade import OrderSide, OrderType
from src.domain.exceptions import KiwoomAuthError, KiwoomOrderError, KiwoomRateLimitError
from src.infrastructure.kiwoom.kiwoom_auth import KiwoomTokenManager

logger = logging.getLogger(__name__)

_BASE_URL = "https://openapi.koreainvestment.com:9443"

# TR IDs for real trading (모의: VTTC*, 실전: TTTC*)
_TR_BUY = "TTTC0802U"
_TR_SELL = "TTTC0801U"
_TR_PRICE = "FHKST01010100"
_TR_BALANCE = "TTTC8434R"
_TR_ORDER_CAPACITY = "TTTC8908R"


class KiwoomRestAdapter(BrokerPort):
    """키움증권 REST API 어댑터.

    Paper mode: 네트워크 호출 없이 주문 시뮬레이션. 실거래 전 반드시 검증.
    """

    def __init__(
        self,
        app_key: str,
        secret_key: str,
        account_no: str,
        is_paper: bool = True,
    ) -> None:
        self._app_key = app_key
        self._secret_key = secret_key
        self._account_no = account_no
        self._is_paper = is_paper
        self._client = httpx.AsyncClient(base_url=_BASE_URL, timeout=10.0)
        self._auth = KiwoomTokenManager(app_key, secret_key, self._client)

    # ── 내부 헬퍼 ───────────────────────────────────────────

    async def _headers(self, tr_id: str) -> dict[str, str]:
        token = await self._auth.get()
        return {
            "Authorization": f"Bearer {token}",
            "appkey": self._app_key,
            "appsecret": self._secret_key,
            "tr_id": tr_id,
            "Content-Type": "application/json",
        }

    def _acnt_parts(self) -> tuple[str, str]:
        """계좌번호를 (CANO 8자리, ACNT_PRDT_CD 2자리)로 분리."""
        cano = self._account_no[:8]
        prdt = self._account_no[8:10] if len(self._account_no) >= 10 else "01"
        return cano, prdt

    @staticmethod
    def _check_rt(data: dict, context: str) -> None:
        if data.get("rt_cd") != "0":
            raise KiwoomOrderError(
                f"{context}: rt_cd={data.get('rt_cd')} msg={data.get('msg1', '')}"
            )

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
            paper_id = f"PAPER-{ticker}-{datetime.utcnow().strftime('%H%M%S%f')[:14]}"
            logger.info(
                "[PAPER] Order: %s %s qty=%d price=%s → %s",
                ticker, side.value, quantity, price, paper_id,
            )
            return paper_id

        cano, prdt = self._acnt_parts()
        tr_id = _TR_BUY if side == OrderSide.BUY else _TR_SELL
        ord_dvsn = "00" if order_type == OrderType.LIMIT else "01"

        try:
            headers = await self._headers(tr_id)
            resp = await self._client.post(
                "/uapi/domestic-stock/v1/trading/order-cash",
                headers=headers,
                json={
                    "CANO": cano,
                    "ACNT_PRDT_CD": prdt,
                    "PDNO": ticker,
                    "ORD_DVSN": ord_dvsn,
                    "ORD_QTY": str(quantity),
                    "ORD_UNPR": str(int(price)) if price else "0",
                },
            )
        except httpx.TimeoutException as exc:
            raise KiwoomOrderError(f"Order timed out for {ticker}") from exc

        if resp.status_code == 429:
            raise KiwoomRateLimitError("Kiwoom API rate limit exceeded")
        if resp.status_code != 200:
            raise KiwoomOrderError(f"Order failed for {ticker}: HTTP {resp.status_code}")

        data = resp.json()
        self._check_rt(data, f"place_order({ticker})")
        kiwoom_order_id: str = data["output"]["ODNO"]
        logger.info("Order placed: %s %s qty=%d → order_id=%s", ticker, side.value, quantity, kiwoom_order_id)
        return kiwoom_order_id

    async def get_current_price(self, ticker: str) -> float:
        if self._is_paper:
            logger.debug("[PAPER] get_current_price(%s) → 100000.0", ticker)
            return 100_000.0

        try:
            headers = await self._headers(_TR_PRICE)
            resp = await self._client.get(
                "/uapi/domestic-stock/v1/quotations/inquire-price",
                headers=headers,
                params={"fid_cond_mrkt_div_code": "J", "fid_input_iscd": ticker},
            )
        except httpx.TimeoutException as exc:
            raise KiwoomOrderError(f"Price query timed out for {ticker}") from exc

        if resp.status_code != 200:
            raise KiwoomOrderError(f"Price query failed for {ticker}: HTTP {resp.status_code}")

        data = resp.json()
        self._check_rt(data, f"get_current_price({ticker})")
        return float(data["output"]["stck_prpr"])

    async def get_positions(self) -> list[dict[str, Any]]:
        if self._is_paper:
            return []

        cano, prdt = self._acnt_parts()
        headers = await self._headers(_TR_BALANCE)
        resp = await self._client.get(
            "/uapi/domestic-stock/v1/trading/inquire-balance",
            headers=headers,
            params={
                "CANO": cano,
                "ACNT_PRDT_CD": prdt,
                "AFHR_FLPR_YN": "N",
                "OFL_YN": "N",
                "INQR_DVSN": "02",
                "UNPR_DVSN": "01",
                "FUND_STTL_ICLD_YN": "N",
                "FNCG_AMT_AUTO_RDPT_YN": "N",
                "PRCS_DVSN": "01",
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": "",
            },
        )
        if resp.status_code != 200:
            raise KiwoomOrderError(f"Position query failed: HTTP {resp.status_code}")
        return resp.json().get("output1", [])

    async def get_balance(self) -> float:
        if self._is_paper:
            return 10_000_000.0  # 1천만원 mock

        cano, prdt = self._acnt_parts()
        headers = await self._headers(_TR_ORDER_CAPACITY)
        resp = await self._client.get(
            "/uapi/domestic-stock/v1/trading/inquire-psbl-order",
            headers=headers,
            params={
                "CANO": cano,
                "ACNT_PRDT_CD": prdt,
                "PDNO": "",
                "ORD_UNPR": "0",
                "ORD_DVSN": "01",
                "CMA_EVLU_AMT_ICLD_YN": "Y",
                "OVRS_ICLD_YN": "N",
            },
        )
        if resp.status_code != 200:
            raise KiwoomOrderError(f"Balance query failed: HTTP {resp.status_code}")
        data = resp.json()
        if data.get("rt_cd") != "0":
            return 0.0
        return float(data["output"]["ord_psbl_cash"])

    async def close(self) -> None:
        await self._client.aclose()
