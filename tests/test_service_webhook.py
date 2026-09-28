from __future__ import annotations

import json

import pytest

from fbchat_v2.service_webhook import (
    WebhookConfigStore,
    normalize_webhook_url,
    validate_webhook_events,
)


def test_webhook_url_rejects_credentials_fragments_and_unknown_schemes() -> None:
    with pytest.raises(ValueError, match="embedded credentials"):
        normalize_webhook_url("https://user:pass@example.com/hook")
    with pytest.raises(ValueError, match="fragment"):
        normalize_webhook_url("https://example.com/hook#secret")
    with pytest.raises(ValueError, match="http or https"):
        normalize_webhook_url("file:///tmp/hook")


def test_webhook_events_are_deduplicated_and_restricted() -> None:
    assert validate_webhook_events(
        ["message.received", "message.received", "session.status"]
    ) == ["message.received", "session.status"]
    with pytest.raises(ValueError, match="Unsupported"):
        validate_webhook_events(["provider.raw-payload"])


@pytest.mark.asyncio
async def test_webhook_store_persists_globally_and_encrypts_secret(tmp_path) -> None:
    store = WebhookConfigStore(tmp_path)
    secret = "signing-secret-must-not-be-plaintext"

    public = await store.update(
        enabled=True,
        url="https://socialmanager.example.com/hooks/facebook",
        events=["message.received", "session.status"],
        secret=secret,
        clear_secret=False,
    )

    persisted = (tmp_path / "webhook.json").read_text(encoding="utf-8")
    payload = json.loads(persisted)
    assert public["scope"] == "all-sessions"
    assert public["secretConfigured"] is True
    assert secret not in persisted
    assert payload["secretEncrypted"]

    reloaded = await WebhookConfigStore(tmp_path).get_public()
    assert reloaded["url"] == "https://socialmanager.example.com/hooks/facebook"
    assert reloaded["events"] == ["message.received", "session.status"]
    assert reloaded["secretConfigured"] is True
    assert secret not in json.dumps(reloaded)


@pytest.mark.asyncio
async def test_webhook_update_preserves_or_clears_secret(tmp_path) -> None:
    store = WebhookConfigStore(tmp_path)
    await store.update(
        enabled=False,
        url="",
        events=[],
        secret="first-secret",
        clear_secret=False,
    )

    preserved = await store.update(
        enabled=True,
        url="http://socialmanager:3000/hooks/facebook",
        events=["message.received"],
        secret=None,
        clear_secret=False,
    )
    cleared = await store.update(
        enabled=False,
        url="",
        events=[],
        secret=None,
        clear_secret=True,
    )

    assert preserved["secretConfigured"] is True
    assert cleared["secretConfigured"] is False


@pytest.mark.asyncio
async def test_enabled_webhook_requires_url_and_events(tmp_path) -> None:
    store = WebhookConfigStore(tmp_path)
    with pytest.raises(ValueError, match="URL is required"):
        await store.update(
            enabled=True,
            url="",
            events=["message.received"],
            secret=None,
            clear_secret=False,
        )
    with pytest.raises(ValueError, match="At least one"):
        await store.update(
            enabled=True,
            url="https://example.com/hook",
            events=[],
            secret=None,
            clear_secret=False,
        )
