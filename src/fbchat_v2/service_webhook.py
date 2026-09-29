"""Persistent global webhook configuration for the provider service."""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from cryptography.fernet import Fernet, InvalidToken

WEBHOOK_EVENTS = frozenset(
    {
        "message.received",
        "message.sent",
        "message.updated",
        "message.deleted",
        "session.status",
    }
)


class WebhookConfigError(RuntimeError):
    """Raised when persisted webhook configuration cannot be processed."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_webhook_url(value: str) -> str:
    url = value.strip()
    if not url:
        return ""
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Webhook URL must use http or https and include a host.")
    if parsed.username or parsed.password:
        raise ValueError("Webhook URL must not contain embedded credentials.")
    if parsed.fragment:
        raise ValueError("Webhook URL must not contain a fragment.")
    return urlunsplit(parsed)


def validate_webhook_events(events: list[str]) -> list[str]:
    normalized = list(dict.fromkeys(event.strip() for event in events if event.strip()))
    unsupported = sorted(set(normalized) - WEBHOOK_EVENTS)
    if unsupported:
        raise ValueError(f"Unsupported webhook events: {', '.join(unsupported)}.")
    return normalized


@dataclass(slots=True)
class WebhookConfig:
    enabled: bool = False
    url: str = ""
    events: list[str] | None = None
    secret: str = ""
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.events is None:
            self.events = []

    def public(self) -> dict[str, Any]:
        return {
            "scope": "all-sessions",
            "enabled": self.enabled,
            "url": self.url,
            "events": list(self.events or []),
            "secretConfigured": bool(self.secret),
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
            "deliveryImplemented": True,
        }


class WebhookConfigStore:
    """Atomically stores one webhook configuration shared by all sessions."""

    def __init__(self, state_dir: Path | None = None) -> None:
        configured_dir = os.environ.get("FBCHAT_STATE_DIR", "").strip()
        self._state_dir = state_dir or Path(configured_dir or ".fbchat-state")
        self._config_path = self._state_dir / "webhook.json"
        self._key_path = self._state_dir / ".config.key"
        self._lock = asyncio.Lock()

    def _ensure_state_dir(self) -> None:
        self._state_dir.mkdir(parents=True, exist_ok=True)
        try:
            self._state_dir.chmod(0o700)
        except OSError:
            pass

    def _fernet(self) -> Fernet:
        self._ensure_state_dir()
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
            raise WebhookConfigError("Webhook encryption key is invalid.") from error

    def _read_unlocked(self) -> WebhookConfig:
        if not self._config_path.exists():
            return WebhookConfig()
        try:
            payload = json.loads(self._config_path.read_text(encoding="utf-8"))
            encrypted_secret = str(payload.get("secretEncrypted") or "")
            secret = ""
            if encrypted_secret:
                secret = self._fernet().decrypt(encrypted_secret.encode()).decode()
            updated_raw = payload.get("updatedAt")
            updated_at = (
                datetime.fromisoformat(str(updated_raw)) if updated_raw else None
            )
            return WebhookConfig(
                enabled=bool(payload.get("enabled", False)),
                url=normalize_webhook_url(str(payload.get("url") or "")),
                events=validate_webhook_events(list(payload.get("events") or [])),
                secret=secret,
                updated_at=updated_at,
            )
        except (
            OSError,
            ValueError,
            TypeError,
            json.JSONDecodeError,
            InvalidToken,
        ) as error:
            raise WebhookConfigError(
                "Stored webhook configuration is invalid or cannot be decrypted."
            ) from error

    async def get_public(self) -> dict[str, Any]:
        async with self._lock:
            return self._read_unlocked().public()

    async def update(
        self,
        *,
        enabled: bool,
        url: str,
        events: list[str],
        secret: str | None,
        clear_secret: bool,
    ) -> dict[str, Any]:
        normalized_url = normalize_webhook_url(url)
        normalized_events = validate_webhook_events(events)
        if enabled and not normalized_url:
            raise ValueError("Webhook URL is required when the webhook is enabled.")
        if enabled and not normalized_events:
            raise ValueError("At least one webhook event is required when enabled.")
        if secret is not None and clear_secret:
            raise ValueError("Cannot set and clear the webhook secret together.")

        async with self._lock:
            current = self._read_unlocked()
            next_secret = "" if clear_secret else current.secret
            if secret is not None:
                next_secret = secret.strip()
            updated_at = _utc_now()
            payload = {
                "version": 1,
                "enabled": enabled,
                "url": normalized_url,
                "events": normalized_events,
                "secretEncrypted": (
                    self._fernet().encrypt(next_secret.encode()).decode()
                    if next_secret
                    else ""
                ),
                "updatedAt": updated_at.isoformat(),
            }
            self._ensure_state_dir()
            temporary = self._config_path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            try:
                temporary.chmod(0o600)
            except OSError:
                pass
            os.replace(temporary, self._config_path)
            return WebhookConfig(
                enabled=enabled,
                url=normalized_url,
                events=normalized_events,
                secret=next_secret,
                updated_at=updated_at,
            ).public()

    async def clear(self) -> dict[str, Any]:
        async with self._lock:
            if self._config_path.exists():
                self._config_path.unlink()
            return WebhookConfig().public()
