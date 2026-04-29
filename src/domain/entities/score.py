from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SignalScore:
    """pro-securities-analyst JSON 결과를 5개 축으로 점수화한 거래 신뢰도 지표.

    Components (총 100점 만점, risk_penalty로 감산):
        fundamental      (0-30):  company-analysis 품질 × 신뢰도 × 상승여력
        regime           (0-25):  market_context.backdrop_verdict
        momentum         (0-25):  quant_signals.momentum_signal
        persona_consensus (0-20): persona_panel.consensus
        risk_penalty     (≤ 0):   Livermore/Taleb/Burry/Druckenmiller veto
    """

    fundamental: float
    regime: float
    momentum: float
    persona_consensus: float
    risk_penalty: float

    @property
    def trade_score(self) -> float:
        raw = (
            self.fundamental
            + self.regime
            + self.momentum
            + self.persona_consensus
            + self.risk_penalty
        )
        return max(0.0, min(100.0, raw))

    @property
    def sizing_factor(self) -> float:
        """포지션 크기 조정 계수 (max_position × factor)."""
        score = self.trade_score
        if score >= 90:
            return 1.0
        elif score >= 80:
            return 0.7
        elif score >= 70:
            return 0.4
        return 0.0

    @property
    def action(self) -> str:
        """ORDER / NOTIFY / IGNORE 세 단계 결정."""
        score = self.trade_score
        if score >= 80:
            return "ORDER"
        elif score >= 60:
            return "NOTIFY"
        return "IGNORE"
