from abc import ABC, abstractmethod
from uuid import UUID


class AuditLogger(ABC):
    """Append-only 이벤트 로거 — audit_events 테이블에 기록."""

    @abstractmethod
    async def log(
        self,
        event_type: str,   # 'ORDER_PLACED', 'ORDER_FILLED', 'RISK_HALT', ...
        entity_type: str,  # 'trade', 'signal', 'risk_snapshot', ...
        entity_id: UUID,
        payload: dict,
    ) -> None: ...
