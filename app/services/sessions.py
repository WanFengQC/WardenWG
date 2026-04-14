from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe


@dataclass
class SessionRecord:
    subject: str
    role: str
    expires_at: datetime


class SessionStore:
    def __init__(self) -> None:
        self._records: dict[str, SessionRecord] = {}

    def create(self, subject: str, role: str, ttl_hours: int = 12) -> str:
        token = token_urlsafe(32)
        self._records[token] = SessionRecord(
            subject=subject,
            role=role,
            expires_at=datetime.now(UTC) + timedelta(hours=ttl_hours),
        )
        return token

    def get(self, token: str | None, role: str) -> SessionRecord | None:
        if not token:
            return None
        record = self._records.get(token)
        if not record:
            return None
        if record.role != role or record.expires_at < datetime.now(UTC):
            self._records.pop(token, None)
            return None
        return record

    def delete(self, token: str | None) -> None:
        if token:
            self._records.pop(token, None)


session_store = SessionStore()

