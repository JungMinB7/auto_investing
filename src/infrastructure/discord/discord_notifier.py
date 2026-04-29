"""Discord Webhook notifier — NotifierPort implementation.

Sends structured Discord embed messages in Korean for:
- 분석 리포트 (send_report): full broker report summary with fields
- 포트폴리오 현황 (send_portfolio): position P&L summary
- 일반 알림 (send): trade events, risk alerts, errors
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import TYPE_CHECKING

import httpx

from src.application.ports.notifier_port import NotifierPort

if TYPE_CHECKING:
    from src.domain.entities.position import Position
    from src.domain.entities.signal import TradingSignal

logger = logging.getLogger(__name__)

# ── 한국어 매핑 ──────────────────────────────────────────────────────────────
_SIGNAL_KO = {"BUY": "매수", "HOLD": "보유", "SELL": "매도"}
_CONFIDENCE_KO = {
    "HIGH": "매우 높음",
    "MEDIUM-HIGH": "높음",
    "MEDIUM": "보통",
    "LOW": "낮음",
}
_SIGNAL_COLOR = {"BUY": 0x2ECC71, "SELL": 0xE74C3C, "HOLD": 0xF39C12}


def _extract_section(report: str, *headers: str, max_lines: int = 5) -> str:
    """영문 브로커 리포트에서 특정 섹션의 내용을 추출."""
    for header in headers:
        pattern = rf"## {re.escape(header)}\s*\n([\s\S]+?)(?=\n## |\Z)"
        m = re.search(pattern, report, re.IGNORECASE)
        if m:
            lines = [l for l in m.group(1).strip().splitlines() if l.strip()][:max_lines]
            return "\n".join(lines)
    return ""


def _format_thesis(report: str) -> str:
    """Investment Thesis 섹션에서 번호 인수 3개 추출."""
    raw = _extract_section(report, "Investment Thesis", "Core Investment Thesis", max_lines=12)
    if not raw:
        return "리포트에서 투자 근거를 추출할 수 없습니다."

    points: list[str] = []
    for m in re.finditer(r"^\d+\.\s+(.+)", raw, re.MULTILINE):
        points.append(f"• {m.group(1).strip()}")
        if len(points) >= 3:
            break
    return "\n".join(points) if points else raw[:300]


def _format_risks(report: str) -> str:
    """Risks 섹션에서 상위 3개 리스크 추출."""
    raw = _extract_section(report, "Risks", "Key Risks", "Risk Factors", max_lines=12)
    if not raw:
        return "리스크 정보 없음"

    items: list[str] = []
    for m in re.finditer(r"[-*•]\s+(.+)|^\d+\.\s+(.+)", raw, re.MULTILINE):
        text = (m.group(1) or m.group(2) or "").strip()
        if text:
            items.append(f"• {text[:120]}")
        if len(items) >= 3:
            break
    return "\n".join(items) if items else raw[:300]


def _format_catalysts(report: str) -> str:
    """Catalysts 섹션에서 상위 2개 추출."""
    raw = _extract_section(report, "Catalysts", "Key Catalysts", max_lines=8)
    if not raw:
        return ""
    items: list[str] = []
    for m in re.finditer(r"[-*•]\s+(.+)|^\d+\.\s+(.+)", raw, re.MULTILINE):
        text = (m.group(1) or m.group(2) or "").strip()
        if text:
            items.append(f"• {text[:100]}")
        if len(items) >= 2:
            break
    return "\n".join(items)


class DiscordNotifierAdapter(NotifierPort):
    """Discord Webhook → NotifierPort 구현체.

    알림 실패 시 예외를 발생시키지 않음 — 주문 파이프라인 중단 방지.
    """

    def __init__(self, webhook_url: str) -> None:
        self._webhook_url = webhook_url
        self._client = httpx.AsyncClient(timeout=10.0)

    async def _post(self, payload: dict) -> None:
        try:
            resp = await self._client.post(self._webhook_url, json=payload)
            if resp.status_code == 429:
                logger.warning("Discord rate limit — notification dropped")
                return
            resp.raise_for_status()
        except httpx.TimeoutException:
            logger.warning("Discord notification timed out")
        except Exception as exc:
            logger.error("Discord notification failed: %s", exc)

    async def send(self, title: str, message: str, color: int = 0x00FF00) -> None:
        payload = {
            "embeds": [
                {
                    "title": title,
                    "description": message,
                    "color": color,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "footer": {"text": "auto-trading-engine"},
                }
            ]
        }
        await self._post(payload)

    async def send_report(self, ticker: str, signal: "TradingSignal", raw_report: str) -> None:
        """분석 리포트 한국어 임베드 전송."""
        sig_val = signal.signal_type.value
        conf_val = signal.confidence.value
        color = _SIGNAL_COLOR.get(sig_val, 0x95A5A6)

        # 수치 포맷
        tp_str = f"₩{signal.target_price:,.0f}" if signal.target_price else "N/A"
        cp_str = f"₩{signal.current_price:,.0f}" if signal.current_price else "N/A"
        up_str = f"{signal.upside_pct:+.1f}%" if signal.upside_pct is not None else "N/A"

        # 리포트 섹션 추출
        thesis = _format_thesis(raw_report)
        risks = _format_risks(raw_report)
        catalysts = _format_catalysts(raw_report)

        fields = [
            {"name": "매매 의견", "value": f"**{_SIGNAL_KO.get(sig_val, sig_val)} ({sig_val})**", "inline": True},
            {"name": "신뢰도", "value": _CONFIDENCE_KO.get(conf_val, conf_val), "inline": True},
            {"name": "현재가", "value": cp_str, "inline": True},
            {"name": "목표가 (12개월)", "value": tp_str, "inline": True},
            {"name": "상승여력", "value": up_str, "inline": True},
            {"name": "​", "value": "​", "inline": True},  # spacer
            {"name": "📋 핵심 투자 근거", "value": thesis or "정보 없음", "inline": False},
            {"name": "⚠️ 주요 리스크", "value": risks or "정보 없음", "inline": False},
        ]
        if catalysts:
            fields.append({"name": "🚀 주요 촉매", "value": catalysts, "inline": False})

        payload = {
            "embeds": [
                {
                    "title": f"📊 {ticker} 종목 분석 리포트",
                    "color": color,
                    "fields": fields,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "footer": {"text": "pro-securities-analyst • auto-trading-engine"},
                }
            ]
        }
        await self._post(payload)

    async def send_portfolio(self, positions: list["Position"], prices: dict[str, float]) -> None:
        """포트폴리오 현황 한국어 임베드 전송."""
        if not positions:
            await self.send("📈 포트폴리오 현황", "보유 포지션 없음", 0x95A5A6)
            return

        total_pnl = 0.0
        total_cost = 0.0
        fields = []

        for pos in positions:
            price = prices.get(pos.ticker, pos.avg_cost)
            pnl = pos.unrealized_pnl(price)
            pnl_pct = pos.unrealized_pnl_pct(price)
            mv = pos.market_value(price)
            total_pnl += pnl
            total_cost += pos.total_cost()

            sign = "+" if pnl >= 0 else ""
            color_emoji = "🟢" if pnl >= 0 else "🔴"
            fields.append({
                "name": f"{color_emoji} {pos.ticker}",
                "value": (
                    f"보유: {pos.quantity:,}주 | 평균단가: ₩{pos.avg_cost:,.0f}\n"
                    f"현재가: ₩{price:,.0f} | 평가손익: {sign}₩{pnl:,.0f} ({sign}{pnl_pct:.1f}%)"
                ),
                "inline": False,
            })

        total_pnl_pct = (total_pnl / total_cost * 100) if total_cost else 0.0
        sign = "+" if total_pnl >= 0 else ""
        summary = f"{sign}₩{total_pnl:,.0f} ({sign}{total_pnl_pct:.1f}%)"
        color = 0x2ECC71 if total_pnl >= 0 else 0xE74C3C

        payload = {
            "embeds": [
                {
                    "title": "📈 포트폴리오 현황",
                    "description": f"총 평가손익: **{summary}** | 보유 {len(positions)}종목",
                    "color": color,
                    "fields": fields,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "footer": {"text": "auto-trading-engine"},
                }
            ]
        }
        await self._post(payload)

    async def close(self) -> None:
        await self._client.aclose()
