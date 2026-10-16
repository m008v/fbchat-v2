from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import recovery_e2ee as recovery


def inputs(tmp_path: Path) -> argparse.Namespace:
    args = argparse.Namespace(
        previous_report=tmp_path / "soak.json",
        device_path=tmp_path / "device.json",
        binary_path=tmp_path / "bridge.exe",
        config=tmp_path / "config.json",
        output_dir=tmp_path / "evidence",
        duration=1800.0,
        cold_timeout=900.0,
        network_timeout=600.0,
        sample_interval=5.0,
        debug_errors=False,
        challenge="restart-test",
    )
    args.previous_report.write_text(
        json.dumps(
            {
                "status": "completed",
                "acceptance_passed": True,
                "shutdown_clean": True,
                "checks": {"text_roundtrip": True, "media_roundtrip": True},
            }
        ),
        encoding="utf-8",
    )
    args.device_path.write_text(
        json.dumps(
            {
                "noise_key_priv": "test-noise",
                "identity_key_priv": "test-identity",
                "registration_id": 1,
                "jid_user": "test-user",
                "sessions": {"test-peer": "test-persisted-session"},
            }
        ),
        encoding="utf-8",
    )
    args.binary_path.touch()
    args.config.write_text("{}", encoding="utf-8")
    return args


def canary(tmp_path: Path) -> recovery.RecoveryCanary:
    args = inputs(tmp_path)
    args.output_dir.mkdir()
    instance = recovery.RecoveryCanary(args)
    instance.session = {"FacebookID": "self"}
    instance.listener = SimpleNamespace(
        _bridge=SimpleNamespace(_generation=1, _proc=SimpleNamespace(pid=123))
    )
    return instance


def event(text: str, number: int = 1) -> dict:
    return {
        "type": "e2eeMessage",
        "data": {
            "id": f"event-{number}",
            "chatJid": "test-chat@msgr",
            "senderJid": "test-peer@msgr",
            "senderId": "test-peer",
            "text": text,
            "timestampMs": int(time.time() * 1000),
        },
    }


def prove_cold(instance: recovery.RecoveryCanary) -> None:
    instance.peer = ("test-chat@msgr", "test-peer@msgr")
    instance.media_ack_prompted = True
    instance.report.update(
        cold_restart_identity_reused=True,
        persisted_sessions_present=True,
        text_reply_rpc_ok=True,
        peer_confirmed_text=True,
        peer_confirmed_media=True,
        media_ack_notice_rpc_ok=True,
        media=[
            {"kind": kind, "sha256_verified": True, "echo_rpc_ok": True}
            for kind in ("image", "document")
        ],
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "running"),
        ("status", "cancelled"),
        ("acceptance_passed", False),
        ("shutdown_clean", False),
        ("checks", {}),
    ],
)
def test_requires_successful_completed_soak(
    tmp_path: Path, field: str, value: object
) -> None:
    args = inputs(tmp_path)
    report = recovery.read_object(args.previous_report)
    report[field] = value
    recovery.write_object(args.previous_report, report)
    with pytest.raises(ValueError):
        recovery.validate_inputs(args)


def test_requires_real_persisted_sessions(tmp_path: Path) -> None:
    args = inputs(tmp_path)
    state = recovery.read_object(args.device_path)
    state["sessions"] = {}
    recovery.write_object(args.device_path, state)
    with pytest.raises(ValueError, match="session"):
        recovery.validate_inputs(args)


def test_rejects_path_alias_and_existing_output(tmp_path: Path) -> None:
    args = inputs(tmp_path)
    recovery.validate_inputs(args)
    args.config = args.device_path
    with pytest.raises(ValueError, match="alias"):
        recovery.validate_inputs(args)
    args.config = tmp_path / "config.json"
    args.output_dir.mkdir()
    with pytest.raises(ValueError, match="mới"):
        recovery.validate_inputs(args)


def test_rejects_hardlink_alias(tmp_path: Path) -> None:
    args = inputs(tmp_path)
    linked = tmp_path / "hardlink.json"
    try:
        os.link(args.device_path, linked)
    except OSError:
        pytest.skip("Hard links unavailable")
    args.config = linked
    with pytest.raises(ValueError, match="alias"):
        recovery.validate_inputs(args)


def test_network_prompt_requires_fresh_cold_text_media_and_acks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    instance = canary(tmp_path)
    sent = []
    monkeypatch.setattr(instance, "send_text", sent.append)
    instance.prompt_network()
    assert not sent
    prove_cold(instance)
    instance.report["peer_confirmed_media"] = False
    instance.prompt_network()
    assert not sent
    instance.report["peer_confirmed_media"] = True
    instance.prompt_network()
    instance.prompt_network()
    assert len(sent) == 1 and instance.report["cold_restart_payload"] is True


def test_initial_text_media_and_acks_are_fresh_not_inherited(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    instance = canary(tmp_path)
    payload = b"test-media"
    sent = []

    def call(method: str, params: dict) -> dict:
        sent.append(method)
        return (
            {"data": base64.b64encode(payload).decode()}
            if method == "downloadE2EEMedia"
            else {}
        )

    monkeypatch.setattr(instance, "call", call)
    instance.report.update(
        cold_restart_identity_reused=True, persisted_sessions_present=True
    )
    assert not instance.cold_payload_proven()
    instance.handle_event(event("restart-test", 1))
    instance.handle_event(event(instance.text_ack, 2))
    for number, kind in enumerate(("image", "file"), 3):
        incoming = event("", number)
        incoming["data"]["attachments"] = [
            {
                "type": kind,
                "fileSize": len(payload),
                "mediaSha256": base64.b64encode(
                    hashlib.sha256(payload).digest()
                ).decode(),
            }
        ]
        instance.handle_event(incoming)
    assert not instance.cold_payload_proven()
    instance.handle_event(event(instance.media_ack, 5))
    assert instance.cold_payload_proven()
    assert "sendE2EEImage" in sent and "sendE2EEDocument" in sent


def test_uncertain_network_prompt_or_start_is_not_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    instance = canary(tmp_path)
    prove_cold(instance)
    calls = []

    def fail(text: str) -> None:
        calls.append(text)
        raise TimeoutError("not exported")

    monkeypatch.setattr(instance, "send_text", fail)
    with pytest.raises(TimeoutError):
        instance.prompt_network()
    instance.prompt_network()
    assert len(calls) == 1
    with pytest.raises(TimeoutError):
        instance.request_outage()
    instance.request_outage()
    assert len(calls) == 2 and not (instance.output / "outage.request").exists()


@pytest.mark.parametrize(
    "reason", ["regular", "self", "stale", "other_peer", "premature"]
)
def test_network_ready_rejects_untrusted_events(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reason: str
) -> None:
    instance = canary(tmp_path)
    prove_cold(instance)
    instance.report["network_prompt_rpc_ok"] = reason != "premature"
    incoming = event(instance.network_ready)
    if reason == "regular":
        incoming["type"] = "message"
    elif reason == "self":
        incoming["data"]["senderId"] = "self"
    elif reason == "stale":
        incoming["data"]["timestampMs"] = instance.minimum_event_timestamp_ms - 1
    elif reason == "other_peer":
        incoming["data"]["senderJid"] = "someone-else"
    sent = []
    monkeypatch.setattr(instance, "send_text", sent.append)
    instance.handle_event(incoming)
    assert not instance.network_requested and not sent


def network_state(instance: recovery.RecoveryCanary, **changes: object) -> None:
    now = int(time.time() * 1000)
    state = {
        "injected": True,
        "completed": True,
        "started_at_ms": now - 1000,
        "ended_at_ms": now + 1000,
        "proxy": {"cut_tunnels": 2},
    }
    state.update(changes)
    recovery.write_object(instance.output / "network-state.json", state)


def test_numbered_sequence_detects_same_event_and_new_id_duplicates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    instance = canary(tmp_path)
    prove_cold(instance)
    monkeypatch.setattr(instance, "send_text", lambda text: None)
    instance.request_outage()
    for number in range(1, 6):
        instance.handle_event(event(f"{instance.sequence_prefix}-{number}", number))
    repeated = event(f"{instance.sequence_prefix}-1", 1)
    instance.handle_event(repeated)
    instance.handle_event(event(f"{instance.sequence_prefix}-2", 12))
    assert instance.report["numbered_sequence_complete"] is True
    assert instance.report["numbered_sequence_no_duplicates"] is False
    serialized = (instance.output / "report.json").read_text(encoding="utf-8")
    assert "test-peer@msgr" not in serialized and "test-chat@msgr" not in serialized


@pytest.mark.parametrize("respawn", [False, True])
def test_recovery_requires_two_sockets_and_e2ee_ack(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, respawn: bool
) -> None:
    instance = canary(tmp_path)
    prove_cold(instance)
    sent = []
    monkeypatch.setattr(instance, "send_text", sent.append)
    instance.request_outage()
    network_state(instance)
    healthy = {"connected": True, "e2eeConnected": False}
    monkeypatch.setattr(instance, "call", lambda *args: healthy)
    instance.poll_network()
    assert not instance.report["network_transport_recovered"]
    instance.handle_event(event(instance.network_ack, 6))
    assert not instance.report["post_network_peer_ack"]
    if respawn:
        instance.listener._bridge._generation = 2
        instance.listener._bridge._proc.pid = 456
    healthy["e2eeConnected"] = True
    instance.poll_network()
    instance.poll_network()
    assert len(sent) == 2
    assert instance.report["recovery_method"] == (
        "watchdog_respawn" if respawn else "native_socket_reconnect"
    )
    instance.handle_event(event(instance.network_ack, 7))
    assert instance.report["post_network_peer_ack"] is True


def test_recovery_send_timeout_never_retries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    instance = canary(tmp_path)
    prove_cold(instance)
    monkeypatch.setattr(instance, "send_text", lambda text: None)
    instance.request_outage()
    network_state(instance)
    monkeypatch.setattr(
        instance, "call", lambda *args: {"connected": True, "e2eeConnected": True}
    )
    sent = []

    def fail(text: str) -> None:
        sent.append(text)
        raise TimeoutError("unknown")

    monkeypatch.setattr(instance, "send_text", fail)
    with pytest.raises(TimeoutError):
        instance.poll_network()
    instance.poll_network()
    assert len(sent) == 1 and not instance.report["network_recovery_reply_rpc_ok"]


def test_controller_error_and_insufficient_cut_are_not_network_proof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    instance = canary(tmp_path)
    prove_cold(instance)
    monkeypatch.setattr(instance, "send_text", lambda text: None)
    instance.request_outage()
    network_state(instance, error="insufficient_active_proxy_tunnels")
    with pytest.raises(RuntimeError, match="Controller"):
        instance.poll_network()
    network_state(instance, proxy={"cut_tunnels": 1})
    with pytest.raises(RuntimeError, match="tunnel"):
        instance.poll_network()


def test_device_lease_refuses_parallel_controller_before_proxy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args = inputs(tmp_path)
    lease = args.device_path.with_name(args.device_path.name + ".recovery.lock")
    lease.touch()
    monkeypatch.setattr(
        recovery, "LoopbackConnectProxy", lambda: pytest.fail("must not start proxy")
    )
    with pytest.raises(FileExistsError):
        recovery.run_controller(args)
    assert lease.exists() and not args.output_dir.exists()


def test_worker_command_uses_argument_list_not_shell(tmp_path: Path) -> None:
    args = inputs(tmp_path)
    args.config = tmp_path / "folder with spaces/config.json"
    command = recovery.worker_command(args)
    assert "--worker" in command
    assert command[command.index("--config") + 1] == str(args.config)
    assert "--challenge" not in command


@pytest.mark.parametrize(
    "worker_exit,proxy_clean,expected,worker_outcome,shutdown_clean",
    [
        (0, True, 0, "normal", True),
        (2, True, 2, "normal", True),
        (0, False, 3, "normal", True),
        (1, True, 1, "inconclusive", True),
        (0, True, 2, "inconclusive", True),
        (-9, True, -9, "cancelled", True),
        (2, True, 2, "inconclusive", False),
        (2, True, 2, "cancelled", True),
        (0, True, 2, "normal", False),
    ],
)
def test_controller_worker_environment_cleanup_and_acceptance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    worker_exit: int,
    proxy_clean: bool,
    expected: int,
    worker_outcome: str,
    shutdown_clean: bool,
) -> None:
    args = inputs(tmp_path)
    captured = {}
    original_env = dict(os.environ)

    class Proxy:
        url = "http://127.0.0.1:32123"

        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            pass

        def snapshot(self) -> dict:
            return {
                "connect_requests": 2,
                "active_tunnels": 2,
                "cut_tunnels": 0,
                "rejected_connects": 0,
            }

        def close(self) -> bool:
            captured["closed"] = True
            return proxy_clean

    class Child:
        pid = 123
        returncode = worker_exit

        def __init__(self, command: list, **kwargs: object) -> None:
            captured.update(command=command, kwargs=kwargs)
            completed = worker_exit == 0 and worker_outcome == "normal"
            stale_checkpoint = worker_outcome != "normal"
            recovery.write_object(
                args.output_dir / "report.json",
                {
                    "status": (
                        worker_outcome
                        if stale_checkpoint
                        else ("completed" if completed else "failed")
                    ),
                    "outcome": (
                        worker_outcome
                        if stale_checkpoint
                        else ("passed" if completed else "failed")
                    ),
                    "phase": (
                        "text"
                        if stale_checkpoint
                        else ("completed" if completed else "startup")
                    ),
                    "reason_code": (
                        "peer_text_timeout"
                        if stale_checkpoint
                        else ("accepted" if completed else "startup_failure")
                    ),
                    "missing_evidence": ["text_challenge"] if stale_checkpoint else [],
                    "acceptance_passed": completed,
                    "shutdown_clean": shutdown_clean,
                    "evidence_scope": "offline_simulation",
                },
            )

        def poll(self) -> int:
            return self.returncode

    monkeypatch.setattr(recovery, "LoopbackConnectProxy", Proxy)
    monkeypatch.setattr(recovery.subprocess, "Popen", Child)
    monkeypatch.setattr(recovery.signal, "signal", lambda *args: None)
    assert recovery.run_controller(args) == expected
    assert captured["closed"] is True and os.environ == original_env
    assert captured["kwargs"]["env"]["HTTPS_PROXY"] == Proxy.url
    assert "shell" not in captured["kwargs"]
    report = recovery.read_object(args.output_dir / "controller.json")
    assert report["acceptance_passed"] is (expected == 0)
    if proxy_clean and not shutdown_clean:
        assert report["status"] == report["outcome"] == "failed"
        assert report["phase"] == "shutdown"
        assert report["reason_code"] == "cleanup_failed"
    elif proxy_clean and worker_exit != 2 and expected != 0:
        assert report["status"] == report["outcome"] == "failed"
        assert report["phase"] == "controller"
        assert report["reason_code"] == "worker_failed"
    elif worker_outcome == "cancelled":
        assert report["status"] == report["outcome"] == "cancelled"
    assert not args.device_path.with_name(
        args.device_path.name + ".recovery.lock"
    ).exists()


def test_worker_revalidates_soak_before_any_login_and_cleans_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    instance = canary(tmp_path)
    previous = recovery.read_object(instance.args.previous_report)
    previous["status"] = "running"
    recovery.write_object(instance.args.previous_report, previous)
    monkeypatch.setattr(
        recovery, "dataGetHome", lambda *args: pytest.fail("must not login")
    )
    stopped = []
    monkeypatch.setattr(instance, "stop_listener", lambda: stopped.append(True) or True)
    assert instance.run() == 2
    assert stopped == [True]
    assert (
        instance.report["status"] == "failed"
        and instance.report["shutdown_clean"] is True
    )


def test_network_timeout_is_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    instance = canary(tmp_path)
    prove_cold(instance)
    monkeypatch.setattr(instance, "send_text", lambda text: None)
    instance.request_outage()
    instance.network_requested_at -= instance.args.network_timeout + 1
    with pytest.raises(TimeoutError):
        instance.poll_network()


def test_outage_requires_observed_down_state_not_missing_health_rpc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    instance = canary(tmp_path)
    prove_cold(instance)
    monkeypatch.setattr(instance, "send_text", lambda text: None)
    instance.request_outage()
    network_state(instance, completed=False)

    def unavailable(*args: object) -> dict:
        raise RuntimeError("local RPC temporarily unavailable")

    monkeypatch.setattr(instance, "call", unavailable)
    instance.poll_network()
    assert not instance.report["both_transports_observed_down"]
    monkeypatch.setattr(
        instance, "call", lambda *args: {"connected": False, "e2eeConnected": False}
    )
    instance.poll_network()
    assert instance.report["both_transports_observed_down"] is True
    assert not instance.report["network_transport_recovered"]


def test_offline_report_cannot_satisfy_future_live_gate(tmp_path: Path) -> None:
    args = inputs(tmp_path)
    previous = recovery.read_object(args.previous_report)
    previous["evidence_scope"] = "offline_simulation"
    recovery.write_object(args.previous_report, previous)
    with pytest.raises(ValueError, match="offline"):
        recovery.validate_inputs(args)


@pytest.mark.parametrize(
    "progress,phase,reason,missing",
    [
        (
            "none",
            "text",
            "peer_text_timeout",
            ["text_challenge", "image_roundtrip", "document_roundtrip", "media_ack"],
        ),
        (
            "text_send",
            "text",
            "peer_text_ack_timeout",
            ["text_ack", "image_roundtrip", "document_roundtrip", "media_ack"],
        ),
        (
            "text",
            "media",
            "peer_media_timeout",
            ["image_roundtrip", "document_roundtrip", "media_ack"],
        ),
        ("media", "media_ack", "peer_media_ack_timeout", ["media_ack"]),
    ],
)
def test_peer_deadlines_are_inconclusive_with_exact_missing_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    progress: str,
    phase: str,
    reason: str,
    missing: list[str],
) -> None:
    instance = canary(tmp_path)
    instance.args.cold_timeout = 0.15
    instance.args.duration = 2.0
    if progress != "none":
        instance.report["text_reply_rpc_ok"] = True
    if progress in {"text", "media"}:
        instance.report["peer_confirmed_text"] = True
    if progress == "media":
        instance.report["media"] = [
            {"kind": kind, "echo_rpc_ok": True, "sha256_verified": True}
            for kind in ("image", "document")
        ]

    async def login(cookie: str) -> dict:
        assert cookie == "synthetic-offline-cookie"
        return {"FacebookID": "synthetic"}

    monkeypatch.setenv("FBCHAT_COOKIE", "synthetic-offline-cookie")
    monkeypatch.setattr(recovery, "dataGetHome", login)
    monkeypatch.setattr(instance, "start_listener", lambda: None)
    monkeypatch.setattr(instance, "stop_listener", lambda: True)
    monkeypatch.setattr(instance, "sample", lambda: None)
    clock = [100.0]

    def tick() -> float:
        clock[0] += 0.05
        return clock[0]

    monkeypatch.setattr(recovery.time, "monotonic", tick)
    assert instance.run() == 2
    assert instance.report["status"] == instance.report["outcome"] == "inconclusive"
    assert instance.report["phase"] == phase
    assert instance.report["reason_code"] == reason
    assert (
        instance.report["missing_evidence"] == instance.report["waiting_for"] == missing
    )
    assert instance.report["network_stage"] == "not_started"
    assert instance.report["errors"] == []
    assert instance.report["shutdown_clean"] is True
    assert instance.report["acceptance_passed"] is False


@pytest.mark.parametrize("fault", ["startup", "health", "peer_send"])
def test_real_fault_timeouts_are_not_reported_as_missing_peer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    instance = canary(tmp_path)
    instance.args.cold_timeout = 1.0

    async def login(cookie: str) -> dict:
        return {"FacebookID": "synthetic"}

    monkeypatch.setenv("FBCHAT_COOKIE", "synthetic-offline-cookie")
    monkeypatch.setattr(recovery, "dataGetHome", login)
    monkeypatch.setattr(instance, "stop_listener", lambda: True)

    def fail() -> None:
        raise TimeoutError("private-provider-message")

    monkeypatch.setattr(
        instance, "start_listener", fail if fault == "startup" else lambda: None
    )
    if fault == "health":
        monkeypatch.setattr(instance, "sample", fail)
    if fault == "peer_send":
        instance.record_error(
            "peer_roundtrip", TimeoutError("private-provider-message")
        )
        # Worker validates the absence of an existing report, so remove only this
        # synthetic test report written by record_error before invoking run().
        (instance.output / "report.json").unlink()
    assert instance.run() == 2
    assert instance.report["status"] == instance.report["outcome"] == "failed"
    assert instance.report["reason_code"] in {
        "startup_failure",
        "internal_failure",
        "checks_failed",
    }
    assert instance.report["errors"]
    assert "private-provider-message" not in json.dumps(instance.report)


def test_controller_diagnostics_reject_arbitrary_provider_strings() -> None:
    result = recovery.controller_diagnostic(
        {
            "phase": "private-chat-id",
            "reason_code": "private-provider-message",
            "missing_evidence": ["secret-key"],
        }
    )
    assert result == {
        "phase": "controller",
        "reason_code": "worker_failed",
        "missing_evidence": [],
        "waiting_for": [],
    }


@pytest.mark.parametrize(
    "known_failure", ["observer_drop", "bridge_drop", "duplicate_sequence"]
)
def test_known_failure_is_not_masked_by_missing_peer_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    known_failure: str,
) -> None:
    instance = canary(tmp_path)
    instance.args.cold_timeout = 0.001
    if known_failure == "observer_drop":
        instance.observer_drops = 1
    elif known_failure == "bridge_drop":
        instance.final_bridge_drops = 1
    else:
        instance.report["numbered_sequence_no_duplicates"] = False

    async def login(cookie: str) -> dict:
        return {"FacebookID": "synthetic"}

    monkeypatch.setenv("FBCHAT_COOKIE", "synthetic-offline-cookie")
    monkeypatch.setattr(recovery, "dataGetHome", login)
    monkeypatch.setattr(instance, "start_listener", lambda: None)
    monkeypatch.setattr(instance, "stop_listener", lambda: True)
    monkeypatch.setattr(instance, "sample", lambda: None)
    clock = [100.0]

    def tick() -> float:
        clock[0] += 0.05
        return clock[0]

    monkeypatch.setattr(recovery.time, "monotonic", tick)
    assert instance.run() == 2
    assert instance.report["status"] == instance.report["outcome"] == "failed"
    assert instance.report["reason_code"] == "checks_failed"
    assert instance.report["acceptance_passed"] is False


@pytest.mark.parametrize("sequence_complete", [False, True])
def test_network_peer_deadline_reports_sequence_or_ack_not_transport_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    sequence_complete: bool,
) -> None:
    instance = canary(tmp_path)
    prove_cold(instance)
    monkeypatch.setattr(instance, "send_text", lambda text: None)
    instance.request_outage()
    instance.report.update(
        network_transport_recovered=True,
        network_stage="completed",
        numbered_sequence_complete=sequence_complete,
    )
    instance.network_requested_at -= instance.args.network_timeout + 1
    with pytest.raises(recovery.PeerWaitExpired):
        instance.poll_network()
    assert instance.report["phase"] == (
        "network_ack" if sequence_complete else "network_sequence"
    )
    assert instance.report["reason_code"] == (
        "network_ack_timeout" if sequence_complete else "network_sequence_timeout"
    )
    assert instance.report["missing_evidence"] == (
        ["network_ack"] if sequence_complete else ["numbered_sequence"]
    )


def test_cleanup_failure_overrides_cancellation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = canary(tmp_path)
    monkeypatch.setattr(instance, "stop_listener", lambda: False)
    instance.stop_requested.set()
    assert instance.run() == 2
    assert instance.report["status"] == instance.report["outcome"] == "failed"
    assert instance.report["phase"] == "shutdown"
    assert instance.report["reason_code"] == "cleanup_failed"
