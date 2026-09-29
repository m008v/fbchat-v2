from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from fbchat_v2.service_sessions import (
    EncryptedSessionStore,
    SessionAuthenticationError,
    SessionNotFoundError,
    SessionRegistry,
    build_cookie_header,
)


def test_cookie_header_requires_minimum_facebook_session_material() -> None:
    with pytest.raises(ValueError, match="Missing required"):
        build_cookie_header([("xs", "secret")])


def test_cookie_header_rejects_injection_and_duplicates() -> None:
    with pytest.raises(ValueError, match="invalid"):
        build_cookie_header([("c_user", "1"), ("xs", "secret\r\nInjected: yes")])
    with pytest.raises(ValueError, match="Duplicate"):
        build_cookie_header([("c_user", "1"), ("xs", "secret"), ("xs", "second")])


@pytest.mark.asyncio
async def test_registry_rejects_invalid_facebook_session() -> None:
    async def reject(_: str) -> dict[str, Any] | None:
        return None

    registry = SessionRegistry(reject)

    with pytest.raises(SessionAuthenticationError):
        await registry.create(
            label="invalid", cookies=[("c_user", "1"), ("xs", "secret")]
        )


@pytest.mark.asyncio
async def test_registry_clears_session_and_rejects_unknown_id() -> None:
    async def accept(cookie_header: str) -> dict[str, Any] | None:
        return {"cookieFacebook": cookie_header, "FacebookID": "1"}

    registry = SessionRegistry(accept)
    session = await registry.create(
        label="account", cookies=[("c_user", "1"), ("xs", "secret")]
    )
    await registry.delete(session["sessionId"])

    assert await registry.list_public() == []
    with pytest.raises(SessionNotFoundError):
        await registry.validate(session["sessionId"])


@pytest.mark.asyncio
async def test_encrypted_session_store_persists_and_reloads(tmp_path: Path) -> None:
    store = EncryptedSessionStore(state_dir=tmp_path)

    async def accept(cookie_header: str) -> dict[str, Any] | None:
        return {"cookieFacebook": cookie_header, "FacebookID": "98765"}

    registry = SessionRegistry(accept, storage=store)
    session = await registry.create(
        label="tenant-session",
        cookies=[("c_user", "98765"), ("xs", "secret-xs")],
        tenant_id="tenant-alpha",
    )
    session_id = session["sessionId"]

    # Verify encrypted file on disk
    enc_file = tmp_path / "sessions" / "tenant-alpha" / f"{session_id}.enc"
    assert enc_file.exists()
    content = enc_file.read_bytes()
    # Confirm secrets are not plain in ciphertext
    assert b"secret-xs" not in content
    assert b"98765" not in content

    # Test detailed status
    status = await registry.get_session_status(session_id)
    assert status["tenantId"] == "tenant-alpha"
    assert status["status"] == "connected"

    # Activity update
    await registry.record_activity(session_id)
    updated_status = await registry.get_session_status(session_id)
    assert updated_status["lastActivityAt"] is not None

    # Error update
    await registry.record_error(session_id, "Network drop")
    error_status = await registry.get_session_status(session_id)
    assert error_status["status"] == "degraded"
    assert error_status["lastError"] == "Network drop"

    # Reload in a fresh registry
    fresh_registry = SessionRegistry(accept, storage=store)
    loaded = await fresh_registry.list_public(detailed=True)
    assert len(loaded) == 1
    assert loaded[0]["sessionId"] == session_id
    assert loaded[0]["tenantId"] == "tenant-alpha"

    # Tenant filtering
    alpha_list = await fresh_registry.list_public(tenant_id="tenant-alpha")
    beta_list = await fresh_registry.list_public(tenant_id="tenant-beta")
    assert len(alpha_list) == 1
    assert len(beta_list) == 0

    # Delete clears encrypted file
    await fresh_registry.delete(session_id)
    assert not enc_file.exists()
