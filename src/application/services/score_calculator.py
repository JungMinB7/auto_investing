from __future__ import annotations

import logging
from typing import Any

from src.domain.entities.score import SignalScore

logger = logging.getLogger(__name__)

_VETO_PERSONAS = {
    "livermore":     {"penalty": -50.0, "trigger_stances": {"SELL", "AVOID", "SHORT"}},
    "burry":         {"penalty": -30.0, "trigger_stances": {"SELL", "AVOID"}},
    "taleb":         {"penalty": -25.0, "trigger_stances": {"SELL", "AVOID"}},
    "druckenmiller": {"penalty": -20.0, "trigger_stances": {"SELL", "AVOID"}},
    "damodaran":     {"penalty": -10.0, "trigger_stances": {"SELL", "AVOID"}},
}

_DEFAULT = SignalScore(
    fundamental=15.0, regime=12.0, momentum=12.0, persona_consensus=10.0, risk_penalty=0.0
)


class ScoreCalculatorService:
    """Claude JSON 리포트 → SignalScore 변환.

    JSON 구조가 없거나 파싱 실패 시 중립적인 기본값(trade_score ≈ 49)을 반환해
    분석 파이프라인을 멈추지 않는다.
    """

    def calculate(self, payload: dict[str, Any] | None) -> SignalScore:
        if not payload:
            return _DEFAULT
        try:
            return SignalScore(
                fundamental=self._fundamental(payload),
                regime=self._regime(payload),
                momentum=self._momentum(payload),
                persona_consensus=self._persona_consensus(payload),
                risk_penalty=self._risk_penalty(payload),
            )
        except Exception:
            logger.warning("ScoreCalculator failed; returning default", exc_info=True)
            return _DEFAULT

    # ── 구성 요소별 계산 ──────────────────────────────────────

    def _fundamental(self, payload: dict) -> float:
        opinion = str(payload.get("investment_opinion", "HOLD")).upper()
        confidence = str(payload.get("confidence", "MEDIUM")).upper()

        base = {"BUY": 30.0, "HOLD": 10.0, "SELL": 0.0}.get(opinion, 10.0)
        conf_factor = {
            "HIGH": 1.0,
            "MEDIUM-HIGH": 0.80,
            "MEDIUM": 0.60,
            "LOW": 0.30,
        }.get(confidence, 0.60)

        upside = payload.get("upside_pct") or 0.0
        try:
            upside_bonus = min(5.0, max(0.0, float(upside) / 10.0))
        except (TypeError, ValueError):
            upside_bonus = 0.0

        return base * conf_factor + upside_bonus

    def _regime(self, payload: dict) -> float:
        ctx = payload.get("market_context") or {}
        verdict = str(ctx.get("backdrop_verdict", "중립"))
        return {"강화": 25.0, "중립": 15.0, "약화": 5.0, "무효화": 0.0}.get(verdict, 12.0)

    def _momentum(self, payload: dict) -> float:
        quant = payload.get("quant_signals") or {}
        status = str(quant.get("status", "N/A")).upper()
        if status in ("N/A", "UNAVAILABLE"):
            return 12.0  # 데이터 없음 → 중립
        momentum = str(quant.get("momentum_signal", "NEUTRAL")).upper()
        return {"POSITIVE": 25.0, "NEUTRAL": 12.0, "NEGATIVE": 0.0}.get(momentum, 12.0)

    def _persona_consensus(self, payload: dict) -> float:
        panel = payload.get("persona_panel") or {}
        consensus = str(panel.get("consensus", "HOLD")).upper()
        return {"BUY": 20.0, "HOLD": 10.0, "SELL": 0.0}.get(consensus, 10.0)

    def _risk_penalty(self, payload: dict) -> float:
        panel = payload.get("persona_panel") or {}
        selected = panel.get("selected") or []

        total_penalty = 0.0
        for persona in selected:
            if not isinstance(persona, dict):
                continue
            name = str(persona.get("name", "")).lower()
            stance = str(persona.get("stance", "")).upper()

            for key, cfg in _VETO_PERSONAS.items():
                if key in name and stance in cfg["trigger_stances"]:
                    total_penalty += cfg["penalty"]
                    logger.debug("Veto applied: %s stance=%s penalty=%.0f", name, stance, cfg["penalty"])
                    break

        return max(-50.0, total_penalty)
