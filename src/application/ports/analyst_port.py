from abc import ABC, abstractmethod


class AnalystPort(ABC):
    @abstractmethod
    async def analyze(self, ticker: str) -> str: ...  # Markdown 브로커 리포트 원문
