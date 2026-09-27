from __future__ import annotations

from typing import Any

import pytest

from fbchat_v2.service_sessions import (
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
