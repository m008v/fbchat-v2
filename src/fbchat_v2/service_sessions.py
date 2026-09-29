"""Private session registry used by the fbchat provider HTTP service.

The registry deliberately keeps Facebook credentials in memory only. Public
responses contain a provider-service session ID and never expose cookies,
Facebook account IDs, or the internal ``dataFB`` structure.
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken

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
    tenant_id: str = "default"
    last_activity_at: datetime | None = None
    status: str = "connected"
    last_error: str | None = None

    def public(self) -> dict[str, Any]:
        return {
            "sessionId": self.session_id,
            "label": self.label,
            "status": self.status,
            "createdAt": self.created_at.isoformat(),
            "validatedAt": self.validated_at.isoformat(),
        }

    def detailed(self) -> dict[str, Any]:
        return {
            "sessionId": self.session_id,
            "tenantId": self.tenant_id,
            "label": self.label,
            "status": self.status,
            "createdAt": self.created_at.isoformat(),
            "validatedAt": self.validated_at.isoformat(),
            "lastActivityAt": (
                self.last_activity_at.isoformat() if self.last_activity_at else None
            ),
            "lastError": self.last_error,
        }

    def clear_secrets(self) -> None:
        self.cookie_header = ""
        self.provider_data.clear()


class EncryptedSessionStore:
    """Persists encrypted session records at rest with tenant isolation."""

    def __init__(self, state_dir: Path | None = None) -> None:
        configured_dir = os.environ.get("FBCHAT_STATE_DIR", "").strip()
        self._state_dir = state_dir or Path(configured_dir or ".fbchat-state")
        self._sessions_dir = self._state_dir / "sessions"
        self._key_path = self._state_dir / ".sessions.key"

    def _ensure_dir(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        try:
            directory.chmod(0o700)
        except OSError:
            pass

    def _fernet(self) -> Fernet:
        self._ensure_dir(self._state_dir)
        if not self._key_path.exists():
            temporary = self._key_path.with_suffix(".tmp")
            temporary.write_bytes(Fernet.generate_key())
            try:
                temporary.chmod(0o600)
            except OSError:
                pass
            os.replace(temporary, self._key_path)
        try:
            return Fernet(self._key_path.read_bytes().strip())
        except (OSError, ValueError) as error:
            raise RuntimeError("Session encryption key is invalid.") from error

    def _tenant_dir(self, tenant_id: str) -> Path:
        clean_tenant = (
            "".join(c for c in tenant_id if c.isalnum() or c in "-_") or "default"
        )
        directory = self._sessions_dir / clean_tenant
        self._ensure_dir(directory)
        return directory

    def save(self, record: SessionRecord) -> None:
        tenant_dir = self._tenant_dir(record.tenant_id)
        session_file = tenant_dir / f"{record.session_id}.enc"
        payload = {
            "sessionId": record.session_id,
            "tenantId": record.tenant_id,
            "label": record.label,
            "cookieHeader": record.cookie_header,
            "providerData": record.provider_data,
            "createdAt": record.created_at.isoformat(),
            "validatedAt": record.validated_at.isoformat(),
            "lastActivityAt": (
                record.last_activity_at.isoformat() if record.last_activity_at else None
            ),
            "status": record.status,
            "lastError": record.last_error,
        }
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        encrypted = self._fernet().encrypt(encoded)
        temporary = session_file.with_suffix(".tmp")
        temporary.write_bytes(encrypted)
        try:
            temporary.chmod(0o600)
        except OSError:
            pass
        os.replace(temporary, session_file)

    def delete(self, tenant_id: str, session_id: str) -> None:
        tenant_dir = self._tenant_dir(tenant_id)
        session_file = tenant_dir / f"{session_id}.enc"
        if session_file.exists():
            try:
                session_file.unlink()
            except OSError:
                pass

    def load_all(self) -> list[SessionRecord]:
        if not self._sessions_dir.exists():
            return []
        fernet = self._fernet()
        records: list[SessionRecord] = []
        for enc_file in self._sessions_dir.glob("*/*.enc"):
            try:
                decrypted = fernet.decrypt(enc_file.read_bytes())
                data = json.loads(decrypted.decode("utf-8"))
                records.append(
                    SessionRecord(
                        session_id=str(data["sessionId"]),
                        tenant_id=str(data.get("tenantId") or "default"),
                        label=str(data.get("label") or "Facebook account"),
                        cookie_header=str(data.get("cookieHeader") or ""),
                        provider_data=dict(data.get("providerData") or {}),
                        created_at=datetime.fromisoformat(data["createdAt"]),
                        validated_at=datetime.fromisoformat(data["validatedAt"]),
                        last_activity_at=(
                            datetime.fromisoformat(data["lastActivityAt"])
                            if data.get("lastActivityAt")
                            else None
                        ),
                        status=str(data.get("status") or "connected"),
                        last_error=data.get("lastError"),
                    )
                )
            except (OSError, ValueError, TypeError, json.JSONDecodeError, InvalidToken):
                continue
        return records


class SessionRegistry:
    """Concurrency-safe registry for Facebook sessions with encrypted persistence."""

    def __init__(
        self,
        authenticator: SessionAuthenticator = dataGetHome,
        storage: EncryptedSessionStore | None = None,
    ) -> None:
        self._authenticator = authenticator
        self._storage = storage
        self._sessions: dict[str, SessionRecord] = {}
        self._lock = asyncio.Lock()
        if self._storage:
            for rec in self._storage.load_all():
                self._sessions[rec.session_id] = rec

    async def create(
        self,
        *,
        label: str,
        cookies: Iterable[tuple[str, str]],
        tenant_id: str = "default",
    ) -> dict[str, Any]:
        cookie_header = build_cookie_header(cookies)
        provider_data = await self._authenticator(cookie_header)
        if provider_data is None:
            raise SessionAuthenticationError(
                "Facebook did not accept the supplied session cookies."
            )

        now = _utc_now()
        clean_tenant = (
            "".join(c for c in tenant_id if c.isalnum() or c in "-_") or "default"
        )
        record = SessionRecord(
            session_id=str(uuid4()),
            tenant_id=clean_tenant,
            label=label.strip() or "Facebook account",
            cookie_header=cookie_header,
            provider_data=provider_data,
            created_at=now,
            validated_at=now,
            last_activity_at=now,
            status="connected",
        )
        async with self._lock:
            self._sessions[record.session_id] = record
            if self._storage:
                self._storage.save(record)
        return record.public()

    async def list_public(
        self, tenant_id: str | None = None, detailed: bool = False
    ) -> list[dict[str, Any]]:
        async with self._lock:
            records = list(self._sessions.values())
        if tenant_id:
            records = [r for r in records if r.tenant_id == tenant_id]
        return [
            record.detailed() if detailed else record.public() for record in records
        ]

    async def validate(self, session_id: str) -> dict[str, Any]:
        async with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                raise SessionNotFoundError(session_id)
            cookie_header = record.cookie_header

        provider_data = await self._authenticator(cookie_header)
        if provider_data is None:
            async with self._lock:
                current = self._sessions.get(session_id)
                if current:
                    current.status = "expired"
                    current.last_error = "The Facebook session is no longer valid."
                    if self._storage:
                        self._storage.save(current)
            raise SessionAuthenticationError("The Facebook session is no longer valid.")

        async with self._lock:
            current = self._sessions.get(session_id)
            if current is None:
                raise SessionNotFoundError(session_id)
            current.provider_data = provider_data
            current.validated_at = _utc_now()
            current.last_activity_at = _utc_now()
            current.status = "connected"
            current.last_error = None
            if self._storage:
                self._storage.save(current)
            return current.public()

    async def delete(self, session_id: str) -> None:
        async with self._lock:
            record = self._sessions.pop(session_id, None)
            if record is None:
                raise SessionNotFoundError(session_id)
            if self._storage:
                self._storage.delete(record.tenant_id, session_id)
        record.clear_secrets()

    async def record_activity(self, session_id: str) -> None:
        async with self._lock:
            record = self._sessions.get(session_id)
            if record:
                record.last_activity_at = _utc_now()
                if self._storage:
                    self._storage.save(record)

    async def record_error(self, session_id: str, error_message: str) -> None:
        async with self._lock:
            record = self._sessions.get(session_id)
            if record:
                record.last_error = error_message
                record.status = "degraded"
                if self._storage:
                    self._storage.save(record)

    async def get_session_status(self, session_id: str) -> dict[str, Any]:
        async with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                raise SessionNotFoundError(session_id)
            return record.detailed()

    async def count(self) -> int:
        async with self._lock:
            return len(self._sessions)

    async def get(self, session_id: str) -> SessionRecord:
        async with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                raise SessionNotFoundError(session_id)
            return record

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
