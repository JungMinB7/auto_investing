from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum


class MarketRegime(str, Enum):
    BULL = "BULL"
    NEUTRAL = "NEUTRAL"
    BEAR = "BEAR"


class MarketRegimePort(ABC):
    @abstractmethod
    def get_regime(self) -> MarketRegime: ...

    @abstractmethod
    def set_regime(self, regime: MarketRegime) -> None: ...

    @property
    def position_factor(self) -> float:
        """시장 상황에 따른 포지션 크기 조정 계수. BEAR = 50% 축소."""
        return {MarketRegime.BULL: 1.0, MarketRegime.NEUTRAL: 1.0, MarketRegime.BEAR: 0.5}[
            self.get_regime()
        ]

    @property
    def allow_new_buy(self) -> bool:
        """BEAR 국면에서도 기본적으로 허용하되, 사이징으로 제어한다."""
        return True
