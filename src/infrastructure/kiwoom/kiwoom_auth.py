"""Kiwoom REST API OAuth2 token manager.

Handles token acquisition and auto-refresh with a 5-minute safety margin.
Token lifecycle: issued → valid → near-expiry (refresh) → renewed.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import httpx

from src.domain.exceptions import KiwoomAuthError

_SAFETY_MARGIN = timedelta(minutes=5)
_TOKEN_PATH = "/oauth2/tokenP"


class KiwoomTokenManager:
    """Bearer 토큰 자동 갱신 — 만료 5분 전 재발급."""

    def __init__(self, app_key: str, secret_key: str, client: httpx.AsyncClient) -> None:
        self._app_key = app_key
        self._secret_key = secret_key
        self._client = client
        self._token: str | None = None
        self._expires_at: datetime | None = None

    async def get(self) -> str:
        """유효한 Bearer 토큰 반환. 필요 시 자동 갱신."""
        if not self._is_valid():
            await self._refresh()
        return self._token  # type: ignore[return-value]

    def _is_valid(self) -> bool:
        if self._token is None or self._expires_at is None:
            return False
        return datetime.utcnow() < self._expires_at - _SAFETY_MARGIN

    async def _refresh(self) -> None:
        try:
            resp = await self._client.post(
                _TOKEN_PATH,
                json={
                    "grant_type": "client_credentials",
                    "appkey": self._app_key,
                    "appsecret": self._secret_key,
                },
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
            self._token = data["access_token"]
            expires_in = int(data.get("expires_in", 86400))
            self._expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        except KiwoomAuthError:
            raise
        except Exception as exc:
            raise KiwoomAuthError(f"Token refresh failed: {exc}") from exc
