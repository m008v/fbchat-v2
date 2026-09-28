"""Private session registry used by the fbchat provider HTTP service.

The registry deliberately keeps Facebook credentials in memory only. Public
responses contain a provider-service session ID and never expose cookies,
Facebook account IDs, or the internal ``dataFB`` structure.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from ._core._session import dataGetHome

SessionAuthenticator = Callable[[str], Awaitable[dict[str, Any] | None]]


class SessionAuthenticationError(RuntimeError):
    """Raised when Facebook rejects or cannot parse the supplied cookies."""


class SessionNotFoundError(KeyError):
    """Raised when a provider-service session ID does not exist."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def build_cookie_header(cookies: Iterable[tuple[str, str]]) -> str:
    """Build a validated Cookie header without logging credential material."""

    values: dict[str, str] = {}
    for raw_name, raw_value in cookies:
        name = raw_name.strip()
        value = raw_value.strip()
        if not name or not value:
            raise ValueError("Cookie names and values cannot be empty.")
        if any(character in name for character in "=;\r\n"):
            raise ValueError("A cookie name contains invalid characters.")
        if any(character in value for character in ";\r\n"):
            raise ValueError("A cookie value contains invalid characters.")
        if name in values:
            raise ValueError(f"Duplicate cookie name: {name}.")
        values[name] = value

    missing = sorted({"c_user", "xs"} - values.keys())
    if missing:
        raise ValueError("Missing required Facebook session cookies.")
    return "; ".join(f"{name}={value}" for name, value in values.items())


@dataclass(slots=True)
class SessionRecord:
    session_id: str
    label: str
    cookie_header: str = field(repr=False)
    provider_data: dict[str, Any] = field(repr=False)
    created_at: datetime
    validated_at: datetime

    def public(self) -> dict[str, Any]:
        return {
            "sessionId": self.session_id,
            "label": self.label,
            "status": "connected",
            "createdAt": self.created_at.isoformat(),
            "validatedAt": self.validated_at.isoformat(),
        }

    def clear_secrets(self) -> None:
        self.cookie_header = ""
        self.provider_data.clear()


class SessionRegistry:
    """Concurrency-safe, process-local registry for Facebook sessions."""

    def __init__(self, authenticator: SessionAuthenticator = dataGetHome) -> None:
        self._authenticator = authenticator
        self._sessions: dict[str, SessionRecord] = {}
        self._lock = asyncio.Lock()

    async def create(
        self, *, label: str, cookies: Iterable[tuple[str, str]]
    ) -> dict[str, Any]:
        cookie_header = build_cookie_header(cookies)
        provider_data = await self._authenticator(cookie_header)
        if provider_data is None:
            raise SessionAuthenticationError(
                "Facebook did not accept the supplied session cookies."
            )

        now = _utc_now()
        record = SessionRecord(
            session_id=str(uuid4()),
            label=label.strip() or "Facebook account",
            cookie_header=cookie_header,
            provider_data=provider_data,
            created_at=now,
            validated_at=now,
        )
        async with self._lock:
            self._sessions[record.session_id] = record
        return record.public()

    async def list_public(self) -> list[dict[str, Any]]:
        async with self._lock:
            records = list(self._sessions.values())
        return [record.public() for record in records]

    async def validate(self, session_id: str) -> dict[str, Any]:
        async with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                raise SessionNotFoundError(session_id)
            cookie_header = record.cookie_header

        provider_data = await self._authenticator(cookie_header)
        if provider_data is None:
            raise SessionAuthenticationError("The Facebook session is no longer valid.")

        async with self._lock:
            current = self._sessions.get(session_id)
            if current is None:
                raise SessionNotFoundError(session_id)
            current.provider_data = provider_data
            current.validated_at = _utc_now()
            return current.public()

    async def delete(self, session_id: str) -> None:
        async with self._lock:
            record = self._sessions.pop(session_id, None)
        if record is None:
            raise SessionNotFoundError(session_id)
        record.clear_secrets()

    async def count(self) -> int:
        async with self._lock:
            return len(self._sessions)

    async def get_provider_data(self, session_id: str) -> dict[str, Any]:
        """Return a private copy for an in-process provider operation."""

        async with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                raise SessionNotFoundError(session_id)
            return dict(record.provider_data)

    async def close(self) -> None:
        async with self._lock:
            records = list(self._sessions.values())
            self._sessions.clear()
        for record in records:
            record.clear_secrets()
