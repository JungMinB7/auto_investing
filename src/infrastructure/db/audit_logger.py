from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.application.ports.audit_port import AuditLogger
from src.infrastructure.db.models import AuditEventModel


class PostgresAuditLogger(AuditLogger):
    """append-only PostgreSQL audit_events 테이블 기록. 삭제/수정 불가."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def log(
        self,
        event_type: str,
        entity_type: str,
        entity_id: uuid.UUID,
        payload: dict,
    ) -> None:
        # Serialize UUID values in payload to strings for JSONB compatibility
        serialized = {
            k: str(v) if isinstance(v, uuid.UUID) else v
            for k, v in payload.items()
        }
        model = AuditEventModel(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=serialized,
        )
        async with self._session_factory() as session:
            session.add(model)
            await session.commit()
