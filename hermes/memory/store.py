"""Long-term memory backed by PostgreSQL full-text search."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from hermes.db.models import MemoryORM
from hermes.models.bd import MemoryEntry


class MemoryStore:
    """Persist and recall agent memories from PostgreSQL."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def remember(
        self,
        entity_type: str,
        content: str,
        entity_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryEntry:
        row = MemoryORM(
            entity_type=entity_type,
            entity_id=entity_id,
            content=content,
            metadata_=metadata or {},
        )
        self._session.add(row)
        self._session.flush()
        return self._to_schema(row)

    def recall(
        self,
        query: str,
        *,
        entity_type: str | None = None,
        limit: int = 10,
    ) -> list[MemoryEntry]:
        if not query.strip():
            stmt = select(MemoryORM).order_by(MemoryORM.created_at.desc()).limit(limit)
            if entity_type:
                stmt = stmt.where(MemoryORM.entity_type == entity_type)
            rows = self._session.scalars(stmt).all()
            return [self._to_schema(row) for row in rows]

        sql = text(
            """
            SELECT id, entity_type, entity_id, content, metadata, created_at
            FROM memory_entries
            WHERE to_tsvector('english', content) @@ plainto_tsquery('english', :query)
            """
            + (" AND entity_type = :entity_type" if entity_type else "")
            + """
            ORDER BY ts_rank(to_tsvector('english', content), plainto_tsquery('english', :query)) DESC
            LIMIT :limit
            """
        )
        params: dict[str, Any] = {"query": query, "limit": limit}
        if entity_type:
            params["entity_type"] = entity_type

        rows = self._session.execute(sql, params).mappings().all()
        return [
            MemoryEntry(
                id=row["id"],
                entity_type=row["entity_type"],
                entity_id=row["entity_id"],
                content=row["content"],
                metadata=row["metadata"] or {},
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def get_by_entity(self, entity_type: str, entity_id: str) -> list[MemoryEntry]:
        rows = self._session.scalars(
            select(MemoryORM)
            .where(
                MemoryORM.entity_type == entity_type,
                MemoryORM.entity_id == entity_id,
            )
            .order_by(MemoryORM.created_at.desc())
        ).all()
        return [self._to_schema(row) for row in rows]

    @staticmethod
    def _to_schema(row: MemoryORM) -> MemoryEntry:
        return MemoryEntry(
            id=row.id,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            content=row.content,
            metadata=row.metadata_ or {},
            created_at=row.created_at,
        )
