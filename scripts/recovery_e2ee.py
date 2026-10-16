"""Verify persisted E2EE payloads, then a worker-only bounded socket outage.

Run only after a completed, accepted soak. A fresh peer opt-in and new text,
image/file ACKs are required. This is a socket reset plus CONNECT unavailability,
not a silent network blackhole, and never changes the machine network settings.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
import signal
import subprocess
import sys
import threading
import time
from collections import Counter
from pathlib import Path
from queue import Empty
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts._fault_proxy import (  # noqa: E402
    LoopbackConnectProxy,
    child_environment,
)
from scripts.soak_e2ee import (  # noqa: E402
    SRC,
    Canary,
    configure_utf8_console,
    dataGetHome,
    device_identity,
    diagnostic,
    EVIDENCE_NAMES,
    PHASES,
    REASON_CODES,
    positive_seconds,
    replace_pending,
    safe_print,
    safe_error_type,
    utc_now,
)

MAX_JSON_BYTES = 32 * 1024 * 1024


class PeerWaitExpired(TimeoutError):
    """Only an explicit local peer-evidence deadline, never an RPC timeout."""


CONTROL_FILES = (
    "report.json",
    "report.pending",
    "stop.request",
    "outage.request",
    "network-state.json",
    "network-state.pending",
    "controller.json",
    "controller.pending",
    "worker.stdout.log",
    "worker.stderr.log",
)


def read_object(path: Path, *, limit: int = MAX_JSON_BYTES) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size > limit:
        raise ValueError("JSON input thiếu hoặc vượt giới hạn kích thước.")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON input phải là object.")
    return data


def write_object(path: Path, data: dict[str, Any]) -> None:
    pending = path.with_suffix(".pending")
    pending.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    replace_pending(pending, path)


def validate_inputs(args: argparse.Namespace, *, worker: bool = False) -> None:
    paths = [args.previous_report, args.device_path, args.binary_path, args.config]
    resolved = [path.resolve(strict=True) for path in paths]
    if any(not path.is_file() for path in resolved):
        raise ValueError("Report, device, binary và config phải là file.")
    for index, path in enumerate(resolved):
        if any(path.samefile(other) for other in resolved[:index]):
            raise ValueError("Các input không được alias cùng file.")
    output = args.output_dir.resolve()
    if any(path == output or output in path.parents for path in resolved):
        raise ValueError("Output không được chứa hoặc alias input.")
    if worker:
        if not output.is_dir() or any(
            (output / name).exists() for name in CONTROL_FILES[:2]
        ):
            raise ValueError("Worker chỉ dùng output mới do controller vừa tạo.")
    elif output.exists():
        raise ValueError("Output directory phải mới; không ghi đè evidence.")
    previous = read_object(args.previous_report)
    if previous.get("evidence_scope") == "offline_simulation":
        raise ValueError("Bằng chứng offline không được dùng làm live soak gate.")
    if (
        previous.get("status") != "completed"
        or previous.get("acceptance_passed") is not True
        or previous.get("shutdown_clean") is not True
    ):
        raise ValueError("Soak phải completed, acceptance_passed và shutdown_clean.")
    checks = previous.get("checks")
    if not isinstance(checks, dict) or any(
        checks.get(name) is not True for name in ("text_roundtrip", "media_roundtrip")
    ):
        raise ValueError("Soak phải có bằng chứng E2EE text và media hai chiều.")
    persisted_sessions(args.device_path)
    device_identity(args.device_path)


def persisted_sessions(path: Path) -> bool:
    state = read_object(path)
    sessions = state.get("sessions")
    if (
        not isinstance(sessions, dict)
        or not sessions
        or not any(
            isinstance(value, str) and bool(value) for value in sessions.values()
        )
    ):
        raise ValueError("Device chưa có session mã hóa đã lưu từ trao đổi thật.")
    return True


class RecoveryCanary(Canary):
    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__(args)
        self.network_ready = f"net-ready-{secrets.token_hex(4)}"
        self.network_ack = f"net-ok-{secrets.token_hex(4)}"
        self.sequence_prefix = f"netseq-{secrets.token_hex(4)}"
        self.sequence_counts: Counter[int] = Counter()
        self.sequence_timestamps: list[int] = []
        self.network_prompt_attempted = False
        self.network_requested = False
        self.recovery_send_attempted = False
        self.network_requested_at = 0.0
        self.network_minimum_timestamp_ms = 0
        self.before_generation: int | None = None
        self.before_pid: int | None = None
        self.baseline_error_count = 0
        self.report.update(
            test="cold-restart-and-worker-proxy-outage",
            persisted_sessions_present=False,
            cold_restart_payload=False,
            network_fault="socket reset + bounded CONNECT unavailability",
            network_prompt_rpc_ok=False,
            network_transport_recovered=False,
            both_transports_observed_down=False,
            network_recovery_reply_rpc_ok=False,
            post_network_peer_ack=False,
            numbered_sequence_complete=False,
            numbered_sequence_no_duplicates=True,
            numbered_messages_sent_during_outage=0,
            recovery_method="not_observed",
            network_stage="not_started",
        )

    def refresh_progress(self) -> None:
        if not self.cold_payload_proven():
            super().refresh_progress()
        elif not self.network_requested:
            diagnostic(
                self.report,
                "network_opt_in",
                "waiting_network_opt_in",
                ["network_opt_in"],
            )
        elif not self.report["network_transport_recovered"]:
            stage = self.report["network_stage"]
            diagnostic(
                self.report,
                "network_recovery" if stage == "recovering" else "network_fault",
                (
                    "waiting_network_recovery"
                    if stage == "recovering"
                    else "waiting_network_fault"
                ),
                (
                    ["network_recovery"]
                    if stage == "recovering"
                    else ["network_outage", "network_recovery"]
                ),
            )
        elif not self.report["numbered_sequence_complete"]:
            diagnostic(
                self.report,
                "network_sequence",
                "waiting_network_sequence",
                ["numbered_sequence"],
            )
        elif not self.report["post_network_peer_ack"]:
            diagnostic(
                self.report, "network_ack", "waiting_network_ack", ["network_ack"]
            )

    def expire_peer_wait(self) -> None:
        self.refresh_progress()
        reason = {
            "waiting_peer_text": "peer_text_timeout",
            "waiting_peer_text_ack": "peer_text_ack_timeout",
            "waiting_peer_media": "peer_media_timeout",
            "waiting_peer_media_ack": "peer_media_ack_timeout",
            "waiting_network_opt_in": "network_opt_in_timeout",
            "waiting_network_sequence": "network_sequence_timeout",
            "waiting_network_ack": "network_ack_timeout",
        }.get(self.report["reason_code"])
        if reason is None:
            raise TimeoutError("Transport/controller recovery hết hạn.")
        diagnostic(
            self.report, self.report["phase"], reason, self.report["missing_evidence"]
        )
        raise PeerWaitExpired("Peer evidence hết hạn.")

    def cold_payload_proven(self) -> bool:
        return bool(
            self.report["cold_restart_identity_reused"]
            and self.report["persisted_sessions_present"]
            and self.report["text_reply_rpc_ok"]
            and self.report["peer_confirmed_text"]
            and self.report["peer_confirmed_media"]
            and all(
                any(
                    item["kind"] == kind
                    and item.get("echo_rpc_ok")
                    and item.get("sha256_verified")
                    for item in self.report["media"]
                )
                for kind in ("image", "document")
            )
        )

    def handle_event(self, event: dict[str, Any]) -> None:
        if event.get("type") != "e2eeMessage":
            return
        received = self.report["counts"]["e2ee_received"]
        duplicates = self.report["counts"]["duplicate_e2ee_event"]
        super().handle_event(event)
        data = event.get("data")
        if not isinstance(data, dict):
            return
        fresh = self.report["counts"]["e2ee_received"] > received
        duplicate = self.report["counts"]["duplicate_e2ee_event"] > duplicates
        if not fresh and not duplicate:
            return
        text = data.get("text")
        if not self.network_requested:
            if (
                fresh
                and text == self.network_ready
                and self.report["network_prompt_rpc_ok"]
                and self.cold_payload_proven()
            ):
                self.request_outage()
            return
        timestamp = data.get("timestampMs")
        if type(timestamp) is not int or timestamp < self.network_minimum_timestamp_ms:
            return
        for number in range(1, 6):
            if text == f"{self.sequence_prefix}-{number}":
                self.sequence_counts[number] += 1
                if duplicate or self.sequence_counts[number] > 1:
                    self.report["numbered_sequence_no_duplicates"] = False
                if fresh and len(self.sequence_timestamps) < 4096:
                    self.sequence_timestamps.append(timestamp)
                break
        self.report["numbered_sequence_complete"] = set(self.sequence_counts) == set(
            range(1, 6)
        )
        self.report["numbered_sequence_unique_count"] = len(self.sequence_counts)
        if (
            fresh
            and text == self.network_ack
            and self.report["network_recovery_reply_rpc_ok"]
        ):
            self.report["post_network_peer_ack"] = True
        self.refresh_progress()
        self.save()

    def prompt_network(self) -> None:
        if self.network_prompt_attempted or not self.cold_payload_proven():
            return
        self.report["cold_restart_payload"] = True
        self.network_prompt_attempted = True
        sequence = ", ".join(
            f"{self.sequence_prefix}-{number}" for number in range(1, 6)
        )
        self.send_text(
            "Cold restart text/ảnh/file E2EE đã đạt. Khi sẵn sàng, gửi: "
            f"{self.network_ready}. Sau tin báo bắt đầu, gửi riêng 5 tin, cách nhau "
            f"khoảng 10 giây: {sequence}. Bridge sẽ mất kết nối trong 30 giây."
        )
        self.report["network_prompt_rpc_ok"] = True
        self.refresh_progress()
        safe_print("[recovery] cold payload OK; waiting for peer network opt-in")
        self.save()

    def request_outage(self) -> None:
        if self.network_requested:
            return
        self.network_requested = True
        # Consume the one-shot before a non-idempotent send; unknown is not retried.
        self.send_text(
            "Bắt đầu kiểm mất mạng riêng bridge. Gửi chuỗi 5 tin đã hướng dẫn ngay nhé."
        )
        if self.listener is None or self.listener._bridge is None:
            raise RuntimeError("Bridge không tồn tại trước fault.")
        bridge = self.listener._bridge
        self.before_generation, self.before_pid = bridge._generation, bridge._proc.pid
        self.baseline_error_count = self.bridge_error_events
        self.report["bridge_errors_before_fault"] = self.baseline_error_count
        self.network_requested_at = time.monotonic()
        self.network_minimum_timestamp_ms = int(time.time() * 1000)
        write_object(self.output / "outage.request", {"requested": True})
        self.report["status"] = "network_fault_requested"
        self.report["network_stage"] = "requested"
        self.refresh_progress()
        self.save()

    def network_state(self) -> dict[str, Any]:
        path = self.output / "network-state.json"
        return read_object(path, limit=4096) if path.exists() else {}

    def poll_network(self) -> None:
        if not self.network_requested:
            return
        if not self.network_requested_at:
            raise RuntimeError("Network start send chưa được xác nhận; không retry.")
        if time.monotonic() - self.network_requested_at > self.args.network_timeout:
            self.expire_peer_wait()
        state = self.network_state()
        if state.get("error"):
            raise RuntimeError("Controller không thể tạo fault đã cô lập.")
        if state.get("injected") is True:
            self.report["network_stage"] = (
                "recovering" if state.get("completed") is True else "outage"
            )
            if self.report["network_transport_recovered"]:
                self.report["network_stage"] = "completed"
        self.refresh_progress()
        start, end = state.get("started_at_ms"), state.get("ended_at_ms")
        if type(start) is int and type(end) is int:
            self.report["numbered_messages_sent_during_outage"] = sum(
                start <= timestamp <= end for timestamp in self.sequence_timestamps
            )
        if (
            state.get("injected") is not True
            or self.report["network_transport_recovered"]
        ):
            return
        proxy_counts = state.get("proxy")
        if not isinstance(proxy_counts, dict) or proxy_counts.get("cut_tunnels", 0) < 2:
            raise RuntimeError(
                "Fault chưa cắt đủ các tunnel; không chấp nhận bằng chứng mạng."
            )
        try:
            healthy = self.call("isConnected", {})
        except Exception as error:
            self.report["network_health_probe_failures"] = (
                self.report.get("network_health_probe_failures", 0) + 1
            )
            self.report["last_network_probe_error_type"] = safe_error_type(error)
            return
        if state.get("completed") is not True:
            if (
                healthy.get("connected") is False
                and healthy.get("e2eeConnected") is False
            ):
                self.report["both_transports_observed_down"] = True
            return
        if (
            healthy.get("connected") is not True
            or healthy.get("e2eeConnected") is not True
        ):
            return
        if self.listener is None or self.listener._bridge is None:
            return
        bridge = self.listener._bridge
        same_process = bridge._proc.pid == self.before_pid
        same_generation = bridge._generation == self.before_generation
        self.report["network_transport_recovered"] = True
        self.report["network_stage"] = "completed"
        self.report["same_bridge_process_after_fault"] = same_process
        self.report["same_bridge_generation_after_fault"] = same_generation
        self.report["recovery_method"] = (
            "native_socket_reconnect"
            if same_process and same_generation
            else "watchdog_respawn"
        )
        self.report["bridge_errors_during_fault_recovery"] = (
            self.bridge_error_events - self.baseline_error_count
        )
        self.recovery_send_attempted = True
        self.send_text(
            "Hai transport đã phục hồi sau socket reset và 30 giây CONNECT unavailable. "
            f"Gửi đủ 5 tin rồi xác nhận qua E2EE: {self.network_ack}"
        )
        self.report["network_recovery_reply_rpc_ok"] = True
        self.refresh_progress()
        self.save()

    def run(self) -> int:
        def monitor_stop() -> None:
            while not self.stop_requested.wait(0.25):
                if (self.output / "stop.request").exists():
                    self.stop_requested.set()

        monitor = threading.Thread(target=monitor_stop, daemon=True)
        monitor.start()
        try:
            # Validate again inside the isolated worker before touching credentials.
            validate_inputs(self.args, worker=True)
            self.save()
            if (self.output / "stop.request").exists():
                raise InterruptedError("Recovery đã được yêu cầu dừng.")
            identity = device_identity(self.device_path)
            self.report["persisted_sessions_present"] = persisted_sessions(
                self.device_path
            )
            cookie = os.getenv("FBCHAT_COOKIE", "").strip()
            if not cookie:
                config = read_object(self.args.config, limit=1024 * 1024)
                cookie = str(config.get("cookies") or "").strip()
            if not cookie:
                raise ValueError("Chưa cấu hình cookie clone.")
            session = asyncio.run(dataGetHome(cookie))
            if not isinstance(session, dict):
                raise RuntimeError("Không tạo được Facebook session.")
            self.session = session
            self.start_listener()
            self.report["cold_restart_identity_reused"] = identity == device_identity(
                self.device_path
            )
            if not self.report["cold_restart_identity_reused"]:
                raise RuntimeError("Cold restart thay identity thiết bị.")
            self.started_at = time.monotonic()
            self.minimum_event_timestamp_ms = int(time.time() * 1000)
            self.report.update(status="cold_restart_ready", ready_at=utc_now())
            self.refresh_progress()
            self.save()
            safe_print(
                f"[recovery] READY; send {self.args.challenge}, image/file <=2 MiB; confirm both ACKs"
            )
            next_sample = 0.0
            while not self.stop_requested.is_set():
                if (self.output / "stop.request").exists():
                    self.stop_requested.set()
                    break
                elapsed = time.monotonic() - self.started_at
                if elapsed > self.args.duration:
                    self.expire_peer_wait()
                if (
                    not self.report["cold_restart_payload"]
                    and elapsed > self.args.cold_timeout
                ):
                    self.expire_peer_wait()
                try:
                    failure = self.listener_failures.get_nowait()
                except Empty:
                    pass
                else:
                    raise RuntimeError("Listener đã dừng ngoài dự kiến.") from failure
                try:
                    self.handle_event(self.events.get(timeout=0.25))
                except Empty:
                    pass
                except Exception as error:
                    self.record_error("peer_roundtrip", error)
                if self.report["errors"]:
                    raise RuntimeError(
                        "Roundtrip đã có lỗi; không chuyển sang fault mạng."
                    )
                self.prompt_network()
                self.poll_network()
                if elapsed >= next_sample:
                    try:
                        self.sample()
                    except Exception as error:
                        if (
                            self.network_requested
                            and not self.report["network_transport_recovered"]
                        ):
                            self.report["network_sample_failures"] = (
                                self.report.get("network_sample_failures", 0) + 1
                            )
                        else:
                            raise RuntimeError(
                                "Health sample ngoài fault thất bại."
                            ) from error
                    next_sample = elapsed + self.args.sample_interval
                if (
                    self.report["post_network_peer_ack"]
                    and self.report["numbered_sequence_complete"]
                ):
                    self.report["status"] = "completed"
                    break
            if self.stop_requested.is_set():
                self.report["status"] = "cancelled"
        except Exception as error:
            if self.stop_requested.is_set():
                self.report.update(status="cancelled", outcome="cancelled")
                diagnostic(
                    self.report,
                    self.report["phase"],
                    "run_cancelled",
                    self.report["missing_evidence"],
                )
            elif (
                isinstance(error, PeerWaitExpired)
                and not self.report["errors"]
                and not self.bridge_error_events
            ):
                self.report.update(status="inconclusive", outcome="inconclusive")
            else:
                self.report.update(status="failed", outcome="failed")
                reason = (
                    "startup_failure" if not self.started_at else "internal_failure"
                )
                if self.report["network_stage"] in {
                    "requested",
                    "outage",
                    "recovering",
                }:
                    reason = (
                        "network_recovery_timeout"
                        if isinstance(error, TimeoutError)
                        else "transport_failure"
                    )
                    self.report["network_stage"] = "failed"
                if any(
                    item["stage"] == "media_ack_notice"
                    for item in self.report["errors"]
                ):
                    reason = "media_ack_notice_failed"
                diagnostic(
                    self.report,
                    (
                        "media_ack"
                        if reason == "media_ack_notice_failed"
                        else self.report["phase"]
                    ),
                    reason,
                    ["media_ack_notice"] if reason == "media_ack_notice_failed" else [],
                )
                self.record_error("run", error)
        finally:
            self.stop_requested.set()
            monitor.join(timeout=1)
            try:
                self.report["shutdown_clean"] = self.stop_listener()
            except Exception as error:
                self.report["shutdown_clean"] = False
                self.record_error("run", error)
            self.report["ended_at"] = utc_now()
            if self.started_at:
                self.report["elapsed_seconds"] = round(
                    time.monotonic() - self.started_at, 2
                )
            self.report["final_bridge_queue_drops"] = self.final_bridge_drops
            recovered_errors = self.report.get("bridge_errors_during_fault_recovery", 0)
            self.report["bridge_errors_outside_fault_recovery"] = (
                self.bridge_error_events - recovered_errors
            )
            self.report["checks"] = {
                "cold_restart_payload": self.report["cold_restart_payload"],
                "network_transport_recovered": self.report[
                    "network_transport_recovered"
                ],
                "both_transports_observed_down": self.report[
                    "both_transports_observed_down"
                ],
                "post_network_peer_ack": self.report["post_network_peer_ack"],
                "numbered_sequence_complete": self.report["numbered_sequence_complete"],
                "numbered_sequence_no_duplicates": self.report[
                    "numbered_sequence_no_duplicates"
                ],
                "numbered_sent_during_outage": self.report[
                    "numbered_messages_sent_during_outage"
                ]
                > 0,
                "no_queue_drop": not self.observer_drops
                and not self.final_bridge_drops,
                "no_unexpected_errors": not self.report["errors"]
                and self.report["bridge_errors_outside_fault_recovery"] == 0,
                "clean_shutdown": self.report["shutdown_clean"],
                "media_ack_notice": self.report["media_ack_notice_rpc_ok"],
            }
            self.report["acceptance_passed"] = self.report[
                "status"
            ] == "completed" and all(self.report["checks"].values())
            if self.report["acceptance_passed"]:
                self.report["outcome"] = "passed"
                diagnostic(self.report, "completed", "accepted", [])
            elif not self.report["shutdown_clean"]:
                self.report.update(status="failed", outcome="failed")
                diagnostic(self.report, "shutdown", "cleanup_failed", [])
            elif self.report["status"] == "cancelled":
                self.report["outcome"] = "cancelled"
                diagnostic(
                    self.report,
                    self.report["phase"],
                    "run_cancelled",
                    self.report["missing_evidence"],
                )
            elif (
                self.report["errors"]
                or not self.report["shutdown_clean"]
                or self.report["bridge_errors_outside_fault_recovery"]
                or self.observer_drops
                or self.final_bridge_drops
                or not self.report["numbered_sequence_no_duplicates"]
            ):
                self.report.update(status="failed", outcome="failed")
                if self.report["reason_code"] not in {
                    "startup_failure",
                    "internal_failure",
                    "transport_failure",
                    "network_recovery_timeout",
                    "media_ack_notice_failed",
                }:
                    diagnostic(self.report, self.report["phase"], "checks_failed", [])
            elif self.report["status"] != "inconclusive":
                self.report.update(status="failed", outcome="failed")
                diagnostic(self.report, self.report["phase"], "checks_failed", [])
            self.save()
        return 0 if self.report["acceptance_passed"] else 2


def controller_diagnostic(worker: dict[str, Any]) -> dict[str, Any]:
    phase, reason, missing = (
        worker.get(name) for name in ("phase", "reason_code", "missing_evidence")
    )
    report: dict[str, Any] = {}
    if (
        isinstance(phase, str)
        and phase in PHASES
        and isinstance(reason, str)
        and reason in REASON_CODES
        and isinstance(missing, list)
        and all(isinstance(item, str) and item in EVIDENCE_NAMES for item in missing)
    ):
        diagnostic(report, phase, reason, missing)
    else:
        diagnostic(report, "controller", "worker_failed", [])
    return report


def run_controller(
    args: argparse.Namespace,
    *,
    outage_seconds: float = 30.0,
    controller_grace_seconds: float = 300.0,
    stop_timeout_seconds: float = 120.0,
    kill_timeout_seconds: float = 15.0,
    poll_interval_seconds: float = 0.25,
) -> int:
    for value in (
        outage_seconds,
        controller_grace_seconds,
        stop_timeout_seconds,
        kill_timeout_seconds,
        poll_interval_seconds,
    ):
        positive_seconds(str(value))
    validate_inputs(args)
    device = args.device_path.resolve(strict=True)
    lease = device.with_name(device.name + ".recovery.lock")
    # Never delete an existing lease automatically, including after a crash.
    descriptor = os.open(lease, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    child: subprocess.Popen[bytes] | None = None
    interrupted = False
    forced_cleanup = False
    deadline_expired = False

    def cancel(*_: object) -> None:
        nonlocal interrupted
        interrupted = True

    previous_int = signal.signal(signal.SIGINT, cancel)
    previous_term = signal.signal(signal.SIGTERM, cancel)
    try:
        args.output_dir.mkdir(parents=True, exist_ok=False)
        with LoopbackConnectProxy() as proxy:
            state: dict[str, Any] = {
                "stage": "not_started",
                "injected": False,
                "completed": False,
            }
            start = 0.0
            command = worker_command(args)
            with (
                (args.output_dir / "worker.stdout.log").open("wb") as stdout,
                (args.output_dir / "worker.stderr.log").open("wb") as stderr,
            ):
                child = subprocess.Popen(
                    command,
                    env=child_environment(proxy.url, os.environ),
                    stdout=stdout,
                    stderr=stderr,
                    start_new_session=os.name != "nt",
                )
                deadline = time.monotonic() + args.duration + controller_grace_seconds
                while child.poll() is None:
                    if interrupted or time.monotonic() > deadline:
                        deadline_expired = not interrupted
                        (args.output_dir / "stop.request").touch(exist_ok=True)
                        try:
                            child.wait(timeout=stop_timeout_seconds)
                        except subprocess.TimeoutExpired:
                            forced_cleanup = True
                            kill_worker_tree(child)
                            child.wait(timeout=kill_timeout_seconds)
                        break
                    if (
                        not state["injected"]
                        and (args.output_dir / "outage.request").exists()
                    ):
                        snapshot = proxy.snapshot()
                        if snapshot["active_tunnels"] < 2:
                            state["error"] = "insufficient_active_proxy_tunnels"
                            state["stage"] = "failed"
                        else:
                            state.update(
                                injected=True,
                                stage="outage",
                                started_at_ms=int(time.time() * 1000),
                            )
                            start = time.monotonic()
                            proxy.begin_outage(outage_seconds)
                    if (
                        state["injected"]
                        and not state["completed"]
                        and time.monotonic() - start >= outage_seconds
                    ):
                        state.update(
                            completed=True,
                            stage="completed",
                            ended_at_ms=int(time.time() * 1000),
                        )
                    state["proxy"] = proxy.snapshot()
                    write_object(args.output_dir / "network-state.json", state)
                    time.sleep(poll_interval_seconds)
            proxy_clean = proxy.close()
            worker_path = args.output_dir / "report.json"
            try:
                worker = read_object(worker_path) if worker_path.exists() else {}
            except (OSError, ValueError, json.JSONDecodeError):
                worker = {}
            accepted = (
                child.returncode == 0
                and proxy_clean
                and not forced_cleanup
                and not interrupted
                and not deadline_expired
                and worker.get("acceptance_passed") is True
                and worker.get("shutdown_clean") is True
                and worker.get("status") == "completed"
            )
            result = controller_diagnostic(worker)
            outcome = worker.get("outcome")
            outcome = (
                outcome
                if isinstance(outcome, str)
                and outcome in {"inconclusive", "failed", "cancelled"}
                else "failed"
            )
            if accepted:
                outcome = "passed"
                diagnostic(result, "completed", "accepted", [])
            elif deadline_expired or forced_cleanup or not proxy_clean:
                outcome = "failed"
                diagnostic(
                    result,
                    "controller",
                    "controller_timeout" if deadline_expired else "cleanup_failed",
                    [],
                )
            elif worker.get("shutdown_clean") is False:
                outcome = "failed"
                diagnostic(result, "shutdown", "cleanup_failed", [])
            elif interrupted:
                outcome = "cancelled"
                diagnostic(
                    result, result["phase"], "run_cancelled", result["missing_evidence"]
                )
            elif child.returncode != 2:
                outcome = "failed"
                diagnostic(result, "controller", "worker_failed", [])
            write_object(
                args.output_dir / "controller.json",
                {
                    **result,
                    "status": "completed" if accepted else outcome,
                    "outcome": outcome,
                    "evidence_scope": (
                        "offline_simulation"
                        if worker.get("evidence_scope") == "offline_simulation"
                        else "live_provider"
                    ),
                    "acceptance_passed": accepted,
                    "worker_exit_code": child.returncode,
                    "proxy_shutdown_clean": proxy_clean,
                    "forced_cleanup": forced_cleanup,
                    "worker_only_proxy_environment": True,
                    "network": state,
                },
            )
            if not proxy_clean or forced_cleanup or deadline_expired:
                return 3
            return 0 if accepted else (child.returncode or 2)
    finally:
        if child is not None and child.poll() is None:
            (args.output_dir / "stop.request").touch(exist_ok=True)
            try:
                child.wait(timeout=stop_timeout_seconds)
            except subprocess.TimeoutExpired:
                kill_worker_tree(child)
                child.wait(timeout=kill_timeout_seconds)
        if child is None or child.poll() is not None:
            lease.unlink()
        signal.signal(signal.SIGINT, previous_int)
        signal.signal(signal.SIGTERM, previous_term)


def kill_worker_tree(child: subprocess.Popen[bytes]) -> None:
    # The PID comes only from this controller's own live Popen object.
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill.exe", "/PID", str(child.pid), "/T", "/F"],
            check=False,
            capture_output=True,
        )
    else:
        os.killpg(child.pid, signal.SIGKILL)


def worker_command(args: argparse.Namespace) -> list[str]:
    command = [sys.executable, str(Path(__file__).resolve()), "--worker"]
    for flag, value in (
        ("--soak-report", args.previous_report),
        ("--device-path", args.device_path),
        ("--binary-path", args.binary_path),
        ("--config", args.config),
        ("--output-dir", args.output_dir),
        ("--duration", args.duration),
        ("--cold-timeout", args.cold_timeout),
        ("--network-timeout", args.network_timeout),
        ("--sample-interval", args.sample_interval),
    ):
        command.extend((flag, str(value)))
    if args.debug_errors:
        command.append("--debug-errors")
    return command


def main() -> int:
    configure_utf8_console()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--soak-report",
        "--previous-report",
        dest="previous_report",
        type=Path,
        required=True,
    )
    parser.add_argument("--device-path", type=Path, required=True)
    parser.add_argument("--binary-path", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=SRC / "config.json")
    parser.add_argument("--duration", type=positive_seconds, default=1800.0)
    parser.add_argument("--cold-timeout", type=positive_seconds, default=900.0)
    parser.add_argument("--network-timeout", type=positive_seconds, default=600.0)
    parser.add_argument("--sample-interval", type=positive_seconds, default=5.0)
    parser.add_argument("--debug-errors", action="store_true")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    args.challenge = f"restart-233-{secrets.token_hex(4)}"
    if (
        args.duration > 3600
        or min(args.cold_timeout, args.network_timeout) < 60
        or args.sample_interval < 5
    ):
        parser.error(
            "Duration tối đa 3600 giây; phase timeout tối thiểu 60, sample interval tối thiểu 5."
        )
    if max(args.cold_timeout, args.network_timeout) >= args.duration:
        parser.error("Phase timeout phải nhỏ hơn duration.")
    try:
        validate_inputs(args, worker=args.worker)
        if args.worker:
            canary = RecoveryCanary(args)
            signal.signal(signal.SIGINT, lambda *_: canary.stop_requested.set())
            signal.signal(signal.SIGTERM, lambda *_: canary.stop_requested.set())
            return canary.run()
        return run_controller(args)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        safe_print(
            f"[recovery] input/controller rejected: {type(error).__name__}; no secret details exported"
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
