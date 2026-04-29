from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class AnalystRequest:
    """분석 어댑터에 전달하는 입력 계약.

    ticker만 넘기던 문자열 계약을 명시적 요청 객체로 바꿔서, 차트/퀀트/백테스트
    같은 분석 옵션이 늘어나도 포트 시그니처가 계속 흔들리지 않게 한다.
    """

    ticker: str
    force_quant: bool = False
    include_charts: bool = False
    quant_context: str | None = None


class AnalystPort(ABC):
    @abstractmethod
    async def analyze(self, request: AnalystRequest) -> str:
        """구조화된 JSON 분석 리포트 원문을 반환한다."""
        ...
