from __future__ import annotations

import argparse
import base64
import hashlib
import json
import time
from pathlib import Path
from typing import Any

import pytest

from scripts.soak_e2ee import Canary, device_identity, positive_seconds, process_rss


def make_canary(tmp_path: Path) -> Canary:
    args = argparse.Namespace(
        output_dir=tmp_path / "evidence",
        binary_path=tmp_path / "bridge",
        challenge="canary-test",
        duration=30.0,
        sample_interval=5.0,
        fault_after=10.0,
        debug_errors=False,
    )
    canary = Canary(args)
    canary.output.mkdir()
    canary.session = {"FacebookID": "clone-self"}
    return canary


def event(text: str, *, chat: str = "test@msgr", message_id: str = "m1") -> dict:
    return {
        "type": "e2eeMessage",
        "data": {
            "id": message_id,
            "chatJid": chat,
            "senderJid": "peer@msgr",
            "senderId": "peer",
            "text": text,
            "timestampMs": int(time.time() * 1000),
        },
    }


def test_observer_never_counts_regular_events_as_e2ee(tmp_path: Path) -> None:
    canary = make_canary(tmp_path)
    canary.on_event({"type": "message", "data": event("canary-test")["data"]})
    assert canary.events.empty()
    assert not canary.report["counts"]


def test_challenge_pins_peer_and_deduplicates_replies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canary = make_canary(tmp_path)
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_call(method: str, params: dict[str, Any]) -> dict[str, Any]:
        calls.append((method, params))
        return {}

    monkeypatch.setattr(canary, "call", fake_call)
    canary.handle_event(event("unrelated"))
    assert not calls and canary.peer is None
    challenge = event("canary-test")
    canary.handle_event(challenge)
    canary.handle_event(challenge)
    canary.handle_event(event("canary-test", message_id="m2"))
    canary.handle_event(event("canary-test", chat="other@msgr", message_id="m3"))
    assert len(calls) == 1
    assert canary.report["counts"]["duplicate_e2ee_event"] == 1
    assert canary.report["text_reply_rpc_ok"] is True
    report = (canary.output / "report.json").read_text(encoding="utf-8")
    assert "test@msgr" not in report and "peer@msgr" not in report


def test_old_challenge_and_premature_confirmations_are_ignored(tmp_path: Path) -> None:
    canary = make_canary(tmp_path)
    stale = event("canary-test")
    stale["data"]["timestampMs"] = canary.minimum_event_timestamp_ms - 1
    canary.handle_event(stale)
    assert canary.peer is None
    canary.peer = ("test@msgr", "peer@msgr")
    canary.handle_event(event(canary.text_ack, message_id="text-ack"))
    canary.handle_event(event(canary.media_ack, message_id="media-ack"))
    assert canary.report["peer_confirmed_text"] is False
    assert canary.report["peer_confirmed_media"] is False


def test_error_events_are_counted_without_payload(tmp_path: Path) -> None:
    canary = make_canary(tmp_path)
    canary.on_event({"type": "error", "data": {"message": "private-decrypt-error"}})
    canary.save()
    assert canary.bridge_error_events == 1
    assert "private-decrypt-error" not in (canary.output / "report.json").read_text()


def test_stop_during_startup_cancels_listener(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts import soak_e2ee

    canary = make_canary(tmp_path)
    stopped = []

    class FakeListener:
        startup_timeout = 60

        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def on_message(self, callback: object) -> None:
            pass

        def connect_mqtt_blocking(self) -> None:
            pass

        def wait_until_connected(self, timeout: float, *, require_e2ee: bool) -> bool:
            assert timeout <= 0.25
            canary.stop_requested.set()
            return False

        def stop(self) -> None:
            stopped.append(True)

    monkeypatch.setattr(soak_e2ee, "listeningE2EEEvent", FakeListener)
    with pytest.raises(InterruptedError):
        canary.start_listener()
    assert stopped
    assert canary.thread is not None
    canary.thread.join(timeout=1)
    with pytest.raises(InterruptedError):
        canary.start_listener()


def test_uncertain_text_send_is_never_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canary = make_canary(tmp_path)
    calls = []

    def unknown_send(text: str) -> None:
        calls.append(text)
        raise TimeoutError("uncertain")

    monkeypatch.setattr(canary, "send_text", unknown_send)
    with pytest.raises(TimeoutError):
        canary.handle_event(event("canary-test"))
    canary.handle_event(event("canary-test", message_id="m2"))
    assert len(calls) == 1
    assert canary.report["text_reply_rpc_ok"] is False


def test_media_digest_is_verified_before_echo_and_echo_is_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canary = make_canary(tmp_path)
    canary.peer = ("test@msgr", "peer@msgr")
    payload = b"real decoded canary bytes"
    calls: list[str] = []

    def fake_call(method: str, params: dict[str, Any]) -> dict[str, Any]:
        calls.append(method)
        if method == "downloadE2EEMedia":
            return {"data": base64.b64encode(payload).decode()}
        return {}

    monkeypatch.setattr(canary, "call", fake_call)
    attachment = {
        "type": "file",
        "fileSize": len(payload),
        "mediaSha256": base64.b64encode(hashlib.sha256(payload).digest()).decode(),
    }
    canary.handle_media(attachment)
    canary.handle_media(attachment)
    assert calls == ["downloadE2EEMedia", "sendE2EEDocument"]
    assert canary.report["media"] == [
        {
            "kind": "document",
            "bytes": len(payload),
            "sha256_verified": True,
            "echo_rpc_ok": True,
        }
    ]


def test_media_digest_mismatch_never_sends(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canary = make_canary(tmp_path)
    canary.peer = ("test@msgr", "peer@msgr")
    calls = []

    def fake_call(method: str, params: dict[str, Any]) -> dict[str, Any]:
        calls.append(method)
        return {"data": base64.b64encode(b"wrong payload").decode()}

    monkeypatch.setattr(canary, "call", fake_call)
    with pytest.raises(RuntimeError, match="digest"):
        canary.handle_media(
            {
                "type": "image",
                "fileSize": 5,
                "mediaSha256": base64.b64encode(
                    hashlib.sha256(b"right").digest()
                ).decode(),
            }
        )
    assert calls == ["downloadE2EEMedia"]


@pytest.mark.parametrize("size", [0, -1, 2 * 1024 * 1024 + 1, True, "10"])
def test_invalid_media_size_does_not_trigger_download(
    tmp_path: Path, size: object
) -> None:
    canary = make_canary(tmp_path)
    canary.handle_media({"type": "image", "fileSize": size})
    assert canary.report["counts"]["media_rejected_size"] == 1


def test_device_identity_compares_persisted_identity_without_exporting_keys(
    tmp_path: Path,
) -> None:
    path = tmp_path / "device.json"
    identity = {
        "noise_key_priv": "private-noise",
        "identity_key_priv": "private-identity",
        "registration_id": 1,
        "jid_user": "opaque-peer",
        "sessions": {},
    }
    path.write_text(json.dumps(identity), encoding="utf-8")
    original = device_identity(path)
    identity["sessions"] = {"peer": "rotated-session"}
    path.write_text(json.dumps(identity), encoding="utf-8")
    assert device_identity(path) == original
    identity["jid_device"] = 12
    path.write_text(json.dumps(identity), encoding="utf-8")
    assert device_identity(path) != original
    identity.pop("jid_device")
    identity["registration_id"] = 2
    path.write_text(json.dumps(identity), encoding="utf-8")
    assert device_identity(path) != original


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf"])
def test_duration_rejects_invalid_numbers(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        positive_seconds(value)


def test_process_rss_reads_current_process() -> None:
    import os

    rss = process_rss(os.getpid())
    assert rss is None or rss > 0
