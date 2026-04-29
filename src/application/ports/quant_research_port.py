from __future__ import annotations

from abc import ABC, abstractmethod


class QuantResearchPort(ABC):
    @abstractmethod
    async def build_context(self, ticker: str) -> str:
        """Claude quant-research 스킬에 주입할 백테스트/팩터 검증 컨텍스트."""
        ...
