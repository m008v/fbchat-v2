"""Controller/subprocess/proxy rehearsal, not Messenger or cryptographic proof."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import signal
import socket
import sys
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest

from scripts import recovery_e2ee as recovery
from scripts._fault_proxy import LoopbackConnectProxy

FAKE_WORKER = Path(__file__).parent / "fixtures" / "recovery_fake_worker.py"
DUMMY_SECRET = "offline-dummy-private-config-and-device-secret"


class EchoTarget:
    def __init__(self) -> None:
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.bind(("127.0.0.1", 0))
        self.address = self.listener.getsockname()
        self.listener.listen()
        self.listener.settimeout(0.05)
        self.stop = threading.Event()
        self.clients: list[socket.socket] = []
        self.workers: list[threading.Thread] = []
        self.accepted = 0
        self.finished = 0
        self.lock = threading.Lock()
        self.accept_thread = threading.Thread(target=self.accept, daemon=True)
        self.accept_thread.start()

    def accept(self) -> None:
        while not self.stop.is_set():
            try:
                client, _ = self.listener.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            client.settimeout(0.05)
            worker = threading.Thread(target=self.echo, args=(client,), daemon=True)
            with self.lock:
                self.clients.append(client)
                self.workers.append(worker)
                self.accepted += 1
            worker.start()

    def echo(self, client: socket.socket) -> None:
        try:
            while not self.stop.is_set():
                try:
                    data = client.recv(4096)
                except socket.timeout:
                    continue
                if not data:
                    break
                client.sendall(data)
        except OSError:
            pass
        finally:
            client.close()
            with self.lock:
                self.finished += 1

    def idle(self) -> bool:
        with self.lock:
            return self.accepted > 0 and self.accepted == self.finished

    def close(self) -> None:
        self.stop.set()
        self.listener.close()
        self.accept_thread.join(timeout=1)
        for client in self.clients:
            client.close()
        for worker in self.workers:
            worker.join(timeout=1)
        assert not self.accept_thread.is_alive()
        assert all(not worker.is_alive() for worker in self.workers)


@pytest.fixture
def echo_targets() -> Iterator[tuple[EchoTarget, EchoTarget]]:
    first, second = EchoTarget(), EchoTarget()
    try:
        yield first, second
    finally:
        first.close()
        second.close()


def inputs(tmp_path: Path) -> argparse.Namespace:
    args = argparse.Namespace(
        previous_report=tmp_path / "synthetic-soak.json",
        device_path=tmp_path / "synthetic-device.json",
        binary_path=tmp_path / "not-a-real-bridge.fixture",
        config=tmp_path / "synthetic-config.json",
        output_dir=tmp_path / "evidence",
        duration=6.0,
        cold_timeout=5.0,
        network_timeout=5.0,
        sample_interval=0.05,
        debug_errors=False,
        challenge="offline-restart-synthetic-challenge",
    )
    # A test-owned accepted predecessor exercises the unchanged input guard.
    # The emitted report, unlike this legacy-shaped fixture, is explicitly
    # offline_simulation and may never satisfy a future live predecessor gate.
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
                "noise_key_priv": DUMMY_SECRET,
                "identity_key_priv": DUMMY_SECRET,
                "registration_id": 1,
                "jid_user": DUMMY_SECRET,
                "sessions": {"synthetic-peer": DUMMY_SECRET},
            }
        ),
        encoding="utf-8",
    )
    args.config.write_text(json.dumps({"cookies": DUMMY_SECRET}), encoding="utf-8")
    args.binary_path.touch()
    return args


def wait_for(predicate: Callable[[], bool], *, seconds: float = 2.0) -> None:
    deadline = time.monotonic() + seconds
    event = threading.Event()
    while not predicate():
        remaining = deadline - time.monotonic()
        assert remaining > 0, "Offline integration condition exceeded its deadline"
        event.wait(min(0.01, remaining))


def install_boundaries(
    monkeypatch: pytest.MonkeyPatch,
    args: argparse.Namespace,
    targets: tuple[EchoTarget, EchoTarget],
    mode: str,
) -> list[LoopbackConnectProxy]:
    proxies: list[LoopbackConnectProxy] = []
    original_connect = socket.create_connection

    def loopback_only(address: tuple[str, int], *positional: Any, **kwargs: Any):
        assert ipaddress.ip_address(address[0]).is_loopback
        return original_connect(address, *positional, **kwargs)

    def real_proxy() -> LoopbackConnectProxy:
        proxy = LoopbackConnectProxy(
            local_targets=[target.address for target in targets], cleanup_timeout=1
        )
        proxies.append(proxy)
        return proxy

    def command(_: argparse.Namespace) -> list[str]:
        result = [sys.executable, "-u", str(FAKE_WORKER.resolve()), "--mode", mode]
        for name in (
            "previous_report",
            "device_path",
            "binary_path",
            "config",
            "output_dir",
        ):
            result.extend((f"--{name.replace('_', '-')}", str(getattr(args, name))))
        for target in targets:
            result.extend(("--target", str(target.address[1])))
        return result

    # These two boundaries choose test inputs; neither proxy behavior nor Popen,
    # its lifecycle, the controller loop, reports or protocol logic are mocked.
    monkeypatch.setattr(recovery, "LoopbackConnectProxy", real_proxy)
    monkeypatch.setattr(recovery, "worker_command", command)
    monkeypatch.setattr(socket, "create_connection", loopback_only)
    return proxies


def run_controller(args: argparse.Namespace) -> int:
    return recovery.run_controller(
        args,
        outage_seconds=0.85,
        controller_grace_seconds=2,
        stop_timeout_seconds=2,
        kill_timeout_seconds=2,
        poll_interval_seconds=0.02,
    )


def assert_cleanup_and_privacy(
    args: argparse.Namespace,
    targets: tuple[EchoTarget, EchoTarget],
    proxies: list[LoopbackConnectProxy],
    original_env: dict[str, str],
    original_signals: tuple[Any, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    worker = recovery.read_object(args.output_dir / "report.json")
    controller = recovery.read_object(args.output_dir / "controller.json")
    assert os.environ == original_env
    assert (
        tuple(signal.getsignal(item) for item in (signal.SIGINT, signal.SIGTERM))
        == original_signals
    )
    assert not args.device_path.with_name(
        args.device_path.name + ".recovery.lock"
    ).exists()
    assert worker["shutdown_clean"] is True
    assert controller["proxy_shutdown_clean"] is True
    assert controller["forced_cleanup"] is False
    assert worker["evidence_scope"] == "offline_simulation"
    assert worker["test"] == "offline-controller-rehearsal"
    assert worker["offline_transport"]["peer_thread_clean"] is True
    assert worker["offline_transport"]["proxy_environment_consistent"] is True
    assert len(proxies) == 1
    assert proxies[0].snapshot()["active_tunnels"] == 0
    assert proxies[0].close() is True
    proxy_url = urlsplit(proxies[0].url)
    with pytest.raises(OSError):
        socket.create_connection(("127.0.0.1", proxy_url.port), timeout=0.2)
    wait_for(lambda: all(target.idle() for target in targets))
    exported = "\n".join(
        (args.output_dir / filename).read_text(encoding="utf-8")
        for filename in ("report.json", "controller.json", "network-state.json")
    )
    for private in (
        DUMMY_SECRET,
        "offline-dummy-private-peer",
        "offline-dummy-private-chat",
        "offline-dummy-private-media-never-export",
        "offline-dummy-private-media-key",
        "offline-dummy-private-path",
        "offline-dummy-private-filename",
        "offline-dummy-private-cookie",
    ):
        assert private not in exported
    assert (args.output_dir / "worker.stderr.log").read_text(encoding="utf-8") == ""
    return worker, controller


def test_real_controller_worker_proxy_cut_restore_and_protocol(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    echo_targets: tuple[EchoTarget, EchoTarget],
) -> None:
    args = inputs(tmp_path)
    proxies = install_boundaries(monkeypatch, args, echo_targets, "success")
    original_env = dict(os.environ)
    original_signals = tuple(
        signal.getsignal(item) for item in (signal.SIGINT, signal.SIGTERM)
    )
    assert run_controller(args) == 0
    worker, controller = assert_cleanup_and_privacy(
        args, echo_targets, proxies, original_env, original_signals
    )
    assert worker["status"] == controller["status"] == "completed"
    assert worker["outcome"] == controller["outcome"] == "passed"
    assert worker["phase"] == controller["phase"] == "completed"
    assert worker["reason_code"] == controller["reason_code"] == "accepted"
    assert worker["acceptance_passed"] is controller["acceptance_passed"] is True
    assert worker["missing_evidence"] == []
    assert all(worker["checks"].values())
    assert worker["offline_transport"]["stream_cuts_observed"] == 2
    assert worker["offline_transport"]["connect_rejections_observed"] > 0
    assert worker["numbered_sequence_unique_count"] == 5
    assert worker["numbered_messages_sent_during_outage"] > 0
    assert controller["network"]["stage"] == "completed"
    assert controller["network"]["proxy"]["cut_tunnels"] == 2
    assert controller["network"]["proxy"]["rejected_connects"] > 0
    assert all(target.accepted == 2 for target in echo_targets)
    # A passing rehearsal must never unlock a subsequent live recovery run.
    args.previous_report = args.output_dir / "report.json"
    args.output_dir = tmp_path / "would-be-live-evidence"
    with pytest.raises(ValueError, match="offline"):
        recovery.validate_inputs(args)
    assert not args.output_dir.exists()


def test_real_worker_peer_timeout_is_inconclusive_not_transport_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    echo_targets: tuple[EchoTarget, EchoTarget],
) -> None:
    args = inputs(tmp_path)
    proxies = install_boundaries(monkeypatch, args, echo_targets, "incomplete")
    original_env = dict(os.environ)
    original_signals = tuple(
        signal.getsignal(item) for item in (signal.SIGINT, signal.SIGTERM)
    )
    assert run_controller(args) == 2
    worker, controller = assert_cleanup_and_privacy(
        args, echo_targets, proxies, original_env, original_signals
    )
    assert worker["status"] == controller["status"] == "inconclusive"
    assert worker["outcome"] == controller["outcome"] == "inconclusive"
    assert worker["phase"] == controller["phase"] == "text"
    assert worker["reason_code"] == controller["reason_code"] == "peer_text_timeout"
    assert worker["acceptance_passed"] is controller["acceptance_passed"] is False
    assert "text_challenge" in worker["missing_evidence"]
    assert worker["errors"] == []
    assert controller["network"]["stage"] == "not_started"
    assert controller["network"]["injected"] is False
    assert proxies[0].snapshot()["cut_tunnels"] == 0


def test_real_worker_stop_request_cancels_and_releases_owned_resources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    echo_targets: tuple[EchoTarget, EchoTarget],
) -> None:
    args = inputs(tmp_path)
    proxies = install_boundaries(monkeypatch, args, echo_targets, "cancel")
    original_env = dict(os.environ)
    original_signals = tuple(
        signal.getsignal(item) for item in (signal.SIGINT, signal.SIGTERM)
    )
    request_errors: list[BaseException] = []

    def request_stop() -> None:
        try:
            path = args.output_dir / "report.json"
            wait_for(
                lambda: path.exists()
                and recovery.read_object(path).get("status") == "cold_restart_ready"
            )
            (args.output_dir / "stop.request").touch()
        except BaseException as error:
            request_errors.append(error)

    requester = threading.Thread(target=request_stop, daemon=True)
    requester.start()
    try:
        assert run_controller(args) == 2
    finally:
        requester.join(timeout=1)
    assert not requester.is_alive() and not request_errors
    worker, controller = assert_cleanup_and_privacy(
        args, echo_targets, proxies, original_env, original_signals
    )
    assert worker["status"] == controller["status"] == "cancelled"
    assert worker["outcome"] == controller["outcome"] == "cancelled"
    assert worker["reason_code"] == controller["reason_code"] == "run_cancelled"
    assert worker["acceptance_passed"] is controller["acceptance_passed"] is False
    assert controller["network"]["stage"] == "not_started"
    assert controller["network"]["injected"] is False


def test_real_controller_deadline_forces_only_owned_worker_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    echo_targets: tuple[EchoTarget, EchoTarget],
) -> None:
    args = inputs(tmp_path)
    proxies = install_boundaries(monkeypatch, args, echo_targets, "stalled")
    original_env = dict(os.environ)
    original_signals = tuple(
        signal.getsignal(item) for item in (signal.SIGINT, signal.SIGTERM)
    )
    assert (
        recovery.run_controller(
            args,
            outage_seconds=0.85,
            controller_grace_seconds=0.05,
            stop_timeout_seconds=0.1,
            kill_timeout_seconds=2,
            poll_interval_seconds=0.02,
        )
        == 3
    )
    controller = recovery.read_object(args.output_dir / "controller.json")
    worker = recovery.read_object(args.output_dir / "report.json")
    assert worker["evidence_scope"] == "offline_simulation"
    assert worker["shutdown_clean"] is False
    assert worker.get("acceptance_passed", False) is False
    assert controller["acceptance_passed"] is False
    assert controller["status"] == controller["outcome"] == "failed"
    assert controller["phase"] == "controller"
    assert controller["reason_code"] == "controller_timeout"
    assert controller["worker_exit_code"] != 0
    assert controller["forced_cleanup"] is True
    assert controller["proxy_shutdown_clean"] is True
    assert controller["network"]["injected"] is False
    assert os.environ == original_env
    assert (
        tuple(signal.getsignal(item) for item in (signal.SIGINT, signal.SIGTERM))
        == original_signals
    )
    assert not args.device_path.with_name(
        args.device_path.name + ".recovery.lock"
    ).exists()
    assert proxies[0].snapshot()["active_tunnels"] == 0
    assert proxies[0].close() is True
    wait_for(lambda: all(target.idle() for target in echo_targets))
    assert all(target.accepted == 1 for target in echo_targets)
