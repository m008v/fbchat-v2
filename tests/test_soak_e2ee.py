from __future__ import annotations

import argparse
import base64
import hashlib
import json
import time
from pathlib import Path
from typing import Any

import pytest

from scripts.soak_e2ee import (
    Canary,
    device_identity,
    positive_seconds,
    process_rss,
    replace_pending,
    validate_device_path,
)


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
    canary.save()
    assert canary.report["observed"]["event_message"] == 1
    assert canary.report["observed"]["challenge_message"] == 1


def test_observer_diagnostics_do_not_export_payload_or_identifiers(
    tmp_path: Path,
) -> None:
    canary = make_canary(tmp_path)
    canary.on_event(
        {"type": "raw", "data": {"type": "FBMessage", "data": "private-key-payload"}}
    )
    canary.on_event({"type": {"invalid": "private-key-payload"}})
    rejected = event("private-text")
    rejected["data"]["timestampMs"] = 0
    canary.handle_event(rejected)
    canary.save()
    report = (canary.output / "report.json").read_text(encoding="utf-8")
    assert canary.report["observed"]["raw_FBMessage"] == 1
    assert canary.report["observed"]["reject_timestamp"] == 1
    assert "private-key-payload" not in report and "private-text" not in report


def test_regular_notice_is_opt_in_one_shot_and_never_counts_as_e2ee(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canary = make_canary(tmp_path)
    canary.args.regular_notice = True
    calls = []

    def call(method: str, params: dict) -> dict:
        calls.append((method, params))
        return {}

    monkeypatch.setattr(canary, "call", call)
    regular = event("canary-test")
    regular["type"] = "message"
    regular["data"]["threadId"] = 12345
    canary.on_event(regular)
    canary.handle_event(canary.events.get_nowait())
    canary.handle_event(regular)
    assert len(calls) == 1 and calls[0][0] == "sendMessage"
    assert canary.report["regular_notice_rpc_ok"] is True
    assert canary.report["text_reply_rpc_ok"] is False
    assert canary.peer is None and not canary.report["counts"]


def test_regular_notice_timeout_is_not_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canary = make_canary(tmp_path)
    canary.args.regular_notice = True
    calls = []

    def call(method: str, params: dict) -> dict:
        calls.append(method)
        raise TimeoutError("uncertain")

    monkeypatch.setattr(canary, "call", call)
    regular = event("canary-test")
    regular["type"] = "message"
    regular["data"]["threadId"] = 12345
    with pytest.raises(TimeoutError):
        canary.handle_event(regular)
    canary.handle_event(regular)
    assert calls == ["sendMessage"]


@pytest.mark.parametrize(
    "reason",
    [
        "disabled",
        "self",
        "stale",
        "wrong_text",
        "thread_bool",
        "thread_zero",
        "thread_string",
    ],
)
def test_regular_notice_rejects_untrusted_or_unrelated_events(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reason: str
) -> None:
    canary = make_canary(tmp_path)
    canary.args.regular_notice = reason != "disabled"
    calls = []
    monkeypatch.setattr(canary, "call", lambda *args: calls.append(args))
    regular = event("canary-test")
    regular["type"] = "message"
    regular["data"]["threadId"] = 12345
    if reason == "self":
        regular["data"]["senderId"] = "clone-self"
    elif reason == "stale":
        regular["data"]["timestampMs"] = canary.minimum_event_timestamp_ms - 1
    elif reason == "wrong_text":
        regular["data"]["text"] = "unrelated"
    elif reason.startswith("thread_"):
        regular["data"]["threadId"] = {
            "thread_bool": True,
            "thread_zero": 0,
            "thread_string": "12345",
        }[reason]
    canary.handle_event(regular)
    assert not calls and not canary.report["regular_notice_rpc_ok"]


@pytest.mark.parametrize(
    "name",
    [
        "config.json",
        "bridge.exe",
        "evidence",
        "evidence/report.json",
        "evidence/report.pending",
        "evidence/stop.request",
    ],
)
def test_device_path_cannot_alias_input_or_evidence(tmp_path: Path, name: str) -> None:
    with pytest.raises(ValueError):
        validate_device_path(
            tmp_path / name,
            output_dir=tmp_path / "evidence",
            config=tmp_path / "config.json",
            binary_path=tmp_path / "bridge.exe",
        )


def test_shared_device_path_is_allowed_without_reading_it(tmp_path: Path) -> None:
    validate_device_path(
        tmp_path / "previous-run/device.json",
        output_dir=tmp_path / "evidence",
        config=tmp_path / "config.json",
        binary_path=tmp_path / "bridge.exe",
    )


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
    assert "image" not in canary.echoed


@pytest.mark.parametrize(
    ("kind", "category", "send_method"),
    [("image", "image", "sendE2EEImage"), ("file", "document", "sendE2EEDocument")],
)
def test_media_download_failure_allows_fresh_valid_media(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    category: str,
    send_method: str,
) -> None:
    canary = make_canary(tmp_path)
    canary.peer = ("test@msgr", "peer@msgr")
    payload = b"fresh canary media"
    calls: list[str] = []

    def fake_call(method: str, params: dict[str, Any]) -> dict[str, Any]:
        calls.append(method)
        if len(calls) == 1:
            raise TimeoutError("transient download failure")
        if method == "downloadE2EEMedia":
            return {"data": base64.b64encode(payload).decode()}
        return {}

    monkeypatch.setattr(canary, "call", fake_call)
    attachment = {
        "type": kind,
        "fileSize": len(payload),
        "mediaSha256": base64.b64encode(hashlib.sha256(payload).digest()).decode(),
        "directPath": "/first-media",
    }
    with pytest.raises(TimeoutError, match="download"):
        canary.handle_media(attachment)
    assert category not in canary.echoed
    assert not canary.report["media"]

    canary.handle_media({**attachment, "directPath": "/fresh-media"})
    assert calls == ["downloadE2EEMedia", "downloadE2EEMedia", send_method]
    assert category in canary.echoed
    assert canary.report["media"][0]["echo_rpc_ok"] is True


@pytest.mark.parametrize(
    ("kind", "category", "send_method"),
    [("image", "image", "sendE2EEImage"), ("file", "document", "sendE2EEDocument")],
)
def test_uncertain_media_send_is_never_retried(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    category: str,
    send_method: str,
) -> None:
    canary = make_canary(tmp_path)
    canary.peer = ("test@msgr", "peer@msgr")
    payload = b"canary media with uncertain delivery"
    calls: list[str] = []

    def fake_call(method: str, params: dict[str, Any]) -> dict[str, Any]:
        calls.append(method)
        if method == "downloadE2EEMedia":
            return {"data": base64.b64encode(payload).decode()}
        raise TimeoutError("uncertain send")

    monkeypatch.setattr(canary, "call", fake_call)
    attachment = {
        "type": kind,
        "fileSize": len(payload),
        "mediaSha256": base64.b64encode(hashlib.sha256(payload).digest()).decode(),
        "directPath": "/first-media",
    }
    with pytest.raises(TimeoutError, match="uncertain"):
        canary.handle_media(attachment)
    canary.handle_media(attachment)
    canary.handle_media({**attachment, "directPath": "/fresh-media"})
    assert calls == ["downloadE2EEMedia", send_method]
    assert category in canary.echoed
    assert "echo_rpc_ok" not in canary.report["media"][0]


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


def media_ack_ready(canary: Canary) -> None:
    canary.peer = ("test@msgr", "peer@msgr")
    canary.media_ack_prompted = True
    canary.report["media"] = [
        {"kind": kind, "echo_rpc_ok": True, "sha256_verified": True}
        for kind in ("image", "document")
    ]


def test_final_media_ack_sends_exactly_one_truthful_confirmation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canary = make_canary(tmp_path)
    media_ack_ready(canary)
    calls = []

    def send(text: str) -> None:
        calls.append(text)
        checkpoint = json.loads(
            (canary.output / "report.json").read_text(encoding="utf-8")
        )
        assert checkpoint["peer_confirmed_media"] is True
        assert checkpoint["media_ack_notice_attempted"] is True
        assert checkpoint["media_ack_notice_delivery"] == "unknown"

    monkeypatch.setattr(canary, "send_text", send)
    incoming = event(canary.media_ack, message_id="media-ack")
    canary.handle_event(incoming)
    canary.handle_event(incoming)
    canary.handle_event(event(canary.media_ack, message_id="new-ack-id"))
    assert len(calls) == 1
    assert "Text" not in calls[0]  # No text ACK was received in this case.
    assert canary.report["peer_confirmed_media"] is True
    assert canary.report["peer_confirmed_text"] is False
    assert canary.report["media_ack_notice_rpc_ok"] is True
    assert canary.report["media_ack_notice_delivery"] == "rpc_confirmed"


@pytest.mark.parametrize("kind", [TimeoutError, RuntimeError])
def test_final_media_ack_notice_failure_preserves_proof_without_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: type[Exception],
) -> None:
    canary = make_canary(tmp_path)
    media_ack_ready(canary)
    calls = []

    def send(text: str) -> None:
        calls.append(text)
        raise kind("private-provider-message-id")

    monkeypatch.setattr(canary, "send_text", send)
    canary.handle_event(event(canary.media_ack, message_id="ack1"))
    canary.handle_event(event(canary.media_ack, message_id="ack2"))
    assert len(calls) == 1
    assert canary.report["peer_confirmed_media"] is True
    assert canary.report["media_ack_notice_rpc_ok"] is False
    assert canary.report["media_ack_notice_delivery"] == "unknown"
    assert canary.report["errors"] == [
        {"stage": "media_ack_notice", "type": kind.__name__}
    ]
    assert "private-provider-message-id" not in json.dumps(canary.report)


@pytest.mark.parametrize(
    "reason",
    ["self", "stale", "other_peer", "not_prompted", "regular", "unverified_digest"],
)
def test_final_media_ack_rejects_untrusted_or_premature_events(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reason: str,
) -> None:
    canary = make_canary(tmp_path)
    media_ack_ready(canary)
    incoming = event(canary.media_ack)
    if reason == "self":
        incoming["data"]["senderId"] = "clone-self"
    elif reason == "stale":
        incoming["data"]["timestampMs"] = canary.minimum_event_timestamp_ms - 1
    elif reason == "other_peer":
        incoming["data"]["senderJid"] = "other-peer"
    elif reason == "not_prompted":
        canary.media_ack_prompted = False
    elif reason == "regular":
        incoming["type"] = "message"
    elif reason == "unverified_digest":
        canary.report["media"][0]["sha256_verified"] = False
    sent = []
    monkeypatch.setattr(canary, "send_text", sent.append)
    canary.handle_event(incoming)
    # A fresh prompt may be sent for the missing-prompt case, never a final notice.
    assert not any("Đã nhận ACK" in text for text in sent)
    assert canary.report["peer_confirmed_media"] is False
    assert canary.report["media_ack_notice_attempted"] is False


def test_pending_replace_retries_only_bounded_sharing_violation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import soak_e2ee

    pending, destination = tmp_path / "report.pending", tmp_path / "report.json"
    calls = []

    def replace(path: Path, target: Path) -> Path:
        calls.append(target)
        if len(calls) < 3:
            raise PermissionError("synthetic sharing violation")
        return target

    monkeypatch.setattr(Path, "replace", replace)
    monkeypatch.setattr(soak_e2ee.time, "sleep", lambda seconds: None)
    replace_pending(pending, destination)
    assert len(calls) == 3

    def fail(path: Path, target: Path) -> Path:
        raise PermissionError("persistent permission denied")

    monkeypatch.setattr(Path, "replace", fail)
    clock = iter([1.0, 2.1])
    monkeypatch.setattr(soak_e2ee.time, "monotonic", lambda: next(clock))
    with pytest.raises(PermissionError):
        replace_pending(pending, destination)


def test_pending_replace_never_retries_other_io_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import soak_e2ee

    def fail(path: Path, target: Path) -> Path:
        raise FileNotFoundError("synthetic absent pending")

    monkeypatch.setattr(Path, "replace", fail)
    monkeypatch.setattr(
        soak_e2ee.time, "sleep", lambda seconds: pytest.fail("must not retry")
    )
    with pytest.raises(FileNotFoundError):
        replace_pending(tmp_path / "missing.pending", tmp_path / "report.json")


@pytest.mark.parametrize("cleanup_raises", [False, True])
def test_soak_startup_timeout_and_cleanup_error_are_failed_not_peer_wait(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cleanup_raises: bool,
) -> None:
    from scripts import soak_e2ee

    canary = make_canary(tmp_path)
    canary.output.rmdir()  # run() owns its fresh synthetic output directory.

    async def login(cookie: str) -> dict:
        return {"FacebookID": "synthetic"}

    def startup() -> None:
        raise TimeoutError("private-provider-message")

    def cleanup() -> bool:
        if cleanup_raises:
            raise OSError("private-cleanup-message")
        return True

    monkeypatch.setenv("FBCHAT_COOKIE", "synthetic-offline-cookie")
    monkeypatch.setattr(soak_e2ee, "dataGetHome", login)
    monkeypatch.setattr(canary, "start_listener", startup)
    monkeypatch.setattr(canary, "stop_listener", cleanup)
    assert canary.run() == 1
    assert canary.report["status"] == canary.report["outcome"] == "failed"
    assert canary.report["phase"] == ("shutdown" if cleanup_raises else "startup")
    assert canary.report["reason_code"] == (
        "cleanup_failed" if cleanup_raises else "startup_failure"
    )
    assert canary.report["acceptance_passed"] is False
    assert "private-provider-message" not in json.dumps(canary.report)
    assert "private-cleanup-message" not in json.dumps(canary.report)
