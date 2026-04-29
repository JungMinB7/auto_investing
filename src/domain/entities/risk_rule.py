from __future__ import annotations

from dataclasses import dataclass

from src.domain.entities.signal import ConfidenceLevel


@dataclass
class RiskRule:
    max_daily_loss_krw: float          # 일일 최대 손실 (원) — 초과 시 자동 중단
    max_position_count: int            # 최대 동시 보유 종목 수
    max_position_krw: float            # 종목당 최대 투자금액 (원)
    max_position_pct: float            # 포트폴리오 대비 최대 비중 (%)
    min_signal_confidence: ConfidenceLevel  # 주문 실행을 허용하는 최소 신뢰도
