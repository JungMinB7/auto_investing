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
from typing import Any, TYPE_CHECKING

import httpx

from src.application.ports.notifier_port import NotifierPort
from src.application.services.report_payload import extract_json_payload, normalize_report_markdown

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


def _clip(text: str, limit: int = 1000) -> str:
    """Discord embed field 제한에 맞춰 문자열을 자른다."""
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _extract_section(report: str, *headers: str, max_lines: int = 5) -> str:
    """영문 브로커 리포트에서 특정 섹션의 내용을 추출."""
    for header in headers:
        pattern = rf"## {re.escape(header)}\s*\n([\s\S]+?)(?=\n## |\Z)"
        m = re.search(pattern, report, re.IGNORECASE)
        if m:
            lines = [l for l in m.group(1).strip().splitlines() if l.strip()][:max_lines]
            return "\n".join(lines)
    return ""


def _format_thesis(report: str, payload: dict[str, Any] | None = None) -> str:
    """Investment Thesis 섹션에서 번호 인수 3개 추출."""
    if payload:
        thesis = payload.get("investment_thesis")
        if isinstance(thesis, list) and thesis:
            points: list[str] = []
            for item in thesis[:3]:
                if isinstance(item, dict):
                    title = item.get("title", "근거")
                    evidence = item.get("evidence", "")
                    points.append(f"• {title}: {evidence}")
                else:
                    points.append(f"• {item}")
            return _clip("\n".join(points))

    raw = _extract_section(report, "Investment Thesis", "Core Investment Thesis", max_lines=12)
    if not raw:
        return "리포트에서 투자 근거를 추출할 수 없습니다."

    points: list[str] = []
    for m in re.finditer(r"^\d+\.\s+(.+)", raw, re.MULTILINE):
        points.append(f"• {m.group(1).strip()}")
        if len(points) >= 3:
            break
    return _clip("\n".join(points) if points else raw[:300])


def _format_risks(report: str, payload: dict[str, Any] | None = None) -> str:
    """Risks 섹션에서 상위 3개 리스크 추출."""
    if payload:
        risks = payload.get("risks")
        if isinstance(risks, list) and risks:
            return _clip("\n".join(f"• {risk}" for risk in risks[:3]))

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
    return _clip("\n".join(items) if items else raw[:300])


def _format_catalysts(report: str, payload: dict[str, Any] | None = None) -> str:
    """Catalysts 섹션에서 상위 2개 추출."""
    if payload:
        catalysts = payload.get("catalysts")
        if isinstance(catalysts, list) and catalysts:
            return _clip("\n".join(f"• {catalyst}" for catalyst in catalysts[:3]))

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


def _format_quant(payload: dict[str, Any] | None) -> str:
    if not payload:
        return ""
    quant = payload.get("quant_signals")
    if not isinstance(quant, dict):
        return ""
    status = quant.get("status", "N/A")
    momentum = quant.get("momentum_signal", "N/A")
    timing = quant.get("timing_note", "")
    backtest = quant.get("backtest_summary", "")
    return _clip(
        "\n".join(
            line
            for line in [
                f"상태: {status} | 모멘텀: {momentum}",
                f"타이밍: {timing}" if timing else "",
                f"백테스트: {backtest}" if backtest else "",
            ]
            if line
        )
    )


def _format_persona(payload: dict[str, Any] | None) -> str:
    if not payload:
        return ""
    panel = payload.get("persona_panel")
    if not isinstance(panel, dict):
        return ""
    selected = panel.get("selected")
    names: list[str] = []
    if isinstance(selected, list):
        for item in selected[:3]:
            if isinstance(item, dict):
                names.append(str(item.get("name", "")))
    rationale = panel.get("selection_rationale") or ""
    stock_type = panel.get("stock_type") or "N/A"
    return _clip(f"{stock_type} | {' + '.join(n for n in names if n)}\n{rationale}".strip())


class DiscordNotifierAdapter(NotifierPort):
    """Discord Webhook → NotifierPort 구현체.

    알림 실패 시 예외를 발생시키지 않음 — 주문 파이프라인 중단 방지.
    """

    def __init__(self, webhook_url: str) -> None:
        self._webhook_url = webhook_url
        self._client = httpx.AsyncClient(timeout=10.0)

    async def _post(self, payload: dict) -> None:
        if not self._webhook_url:
            logger.debug("Discord webhook URL is empty — notification skipped")
            return
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
        """분석 리포트 한국어 임베드와 전체 리포트 청크를 전송."""
        sig_val = signal.signal_type.value
        conf_val = signal.confidence.value
        color = _SIGNAL_COLOR.get(sig_val, 0x95A5A6)
        payload_json = extract_json_payload(raw_report)
        report_text = (
            normalize_report_markdown(payload_json, raw_report) if payload_json else raw_report
        )

        # 수치 포맷
        tp_str = f"₩{signal.target_price:,.0f}" if signal.target_price else "N/A"
        cp_str = f"₩{signal.current_price:,.0f}" if signal.current_price else "N/A"
        up_str = f"{signal.upside_pct:+.1f}%" if signal.upside_pct is not None else "N/A"

        # 리포트 섹션 추출
        thesis = _format_thesis(report_text, payload_json)
        risks = _format_risks(report_text, payload_json)
        catalysts = _format_catalysts(report_text, payload_json)
        quant = _format_quant(payload_json)
        persona = _format_persona(payload_json)

        fields = [
            {
                "name": "매매 의견",
                "value": f"**{_SIGNAL_KO.get(sig_val, sig_val)} ({sig_val})**",
                "inline": True,
            },
            {"name": "신뢰도", "value": _CONFIDENCE_KO.get(conf_val, conf_val), "inline": True},
            {"name": "현재가", "value": cp_str, "inline": True},
            {"name": "목표가 (12개월)", "value": tp_str, "inline": True},
            {"name": "상승여력", "value": up_str, "inline": True},
            {"name": "​", "value": "​", "inline": True},  # spacer
            {"name": "📋 핵심 투자 근거", "value": thesis or "정보 없음", "inline": False},
            {"name": "⚠️ 주요 리스크", "value": risks or "정보 없음", "inline": False},
        ]
        if persona:
            fields.insert(6, {"name": "🧠 선택 페르소나", "value": persona, "inline": False})
        if quant:
            fields.append({"name": "📈 퀀트/백테스트", "value": quant, "inline": False})
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
        await self._send_full_report(ticker, report_text, color)

    async def _send_full_report(self, ticker: str, report_text: str, color: int) -> None:
        """Discord 본문 제한을 피하기 위해 전체 스킬 리포트를 여러 임베드로 나눠 보낸다."""
        clean = report_text.strip()
        if not clean:
            return

        chunks = [clean[i : i + 3400] for i in range(0, min(len(clean), 10_200), 3400)]
        for idx, chunk in enumerate(chunks, start=1):
            await self._post(
                {
                    "embeds": [
                        {
                            "title": f"📄 {ticker} 상세 리포트 ({idx}/{len(chunks)})",
                            "description": chunk,
                            "color": color,
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "footer": {"text": "skills report • pro-securities-analyst"},
                        }
                    ]
                }
            )

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
