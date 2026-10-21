from __future__ import annotations

import asyncio
import json
import sys
import textwrap
import threading
import time
from pathlib import Path
from queue import Empty, Queue
from typing import Any

import pytest

from _messaging import _listening_e2ee as e2ee
from _messaging._reconnect import ReconnectPolicy


def _write_bridge_script(tmp_path: Path, source: str) -> tuple[str, ...]:
    script = tmp_path / "fake_reconnect_bridge.py"
    script.write_text(textwrap.dedent(source), encoding="utf-8")
    return (sys.executable, "-u", str(script))


def _test_policy(*, max_attempts: int | None = 3) -> ReconnectPolicy:
    return ReconnectPolicy(
        initial_delay=0.001,
        max_delay=0.001,
        jitter=0.0,
        max_attempts=max_attempts,
        stable_reset_after=0.05,
    )


def _wait_for_event(
    events: Queue[dict[str, Any]], event_type: str, timeout: float = 3.0
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AssertionError(f"event {event_type!r} was not emitted")
        try:
            event = events.get(timeout=remaining)
        except Empty as error:
            raise AssertionError(f"event {event_type!r} was not emitted") from error
        if event.get("type") == event_type:
            return event


def _hello_payload() -> dict[str, Any]:
    return {
        "protocolVersion": 1,
        "bridgeVersion": e2ee.BRIDGE_RELEASE_VERSION
        or e2ee._expected_package_version(),
        "capabilities": [
            "newClient",
            "connect",
            "connectE2EE",
            "isConnected",
            "events",
            "structuredConnectionStatus",
        ],
    }


def test_startup_network_retry_reuses_client_and_only_replays_failed_phase(
    tmp_path: Path,
) -> None:
    methods_path = tmp_path / "methods.jsonl"
    command = _write_bridge_script(
        tmp_path,
        f"""
        import json
        import pathlib
        import sys

        methods_path = pathlib.Path({str(methods_path)!r})
        hello = {_hello_payload()!r}
        connect_calls = 0
        for raw in sys.stdin:
            request = json.loads(raw)
            method = request.get("method")
            with methods_path.open("a", encoding="utf-8") as handle:
                print(json.dumps(method), file=handle)
            if method == "hello":
                response = {{"id": request["id"], "ok": True, "data": hello}}
            elif method == "connect":
                connect_calls += 1
                if connect_calls == 1:
                    response = {{
                        "id": request["id"],
                        "ok": False,
                        "error": "hidden provider detail",
                        "errorCode": "network_disconnected",
                        "retryable": True,
                    }}
                else:
                    response = {{"id": request["id"], "ok": True, "data": {{}}}}
            elif method == "isConnected":
                response = {{
                    "id": request["id"],
                    "ok": True,
                    "data": {{"connected": True, "e2eeConnected": False}},
                }}
            else:
                response = {{"id": request["id"], "ok": True, "data": {{}}}}
            print(json.dumps(response), flush=True)
        """,
    )
    retries: list[tuple[str, int, float]] = []
    bridge = e2ee._BridgeProcess(Path(command[0]), command=command)
    try:
        bridge.connect_client(
            {"cookies": {}},
            enable_e2ee=False,
            reconnect_policy=_test_policy(),
            on_retry=lambda reason, attempt, delay: retries.append(
                (reason, attempt, delay)
            ),
        )
    finally:
        bridge.close()

    methods = [
        json.loads(line)
        for line in methods_path.read_text(encoding="utf-8").splitlines()
    ]
    assert methods.count("newClient") == 1
    assert methods.count("connect") == 2
    assert retries == [("network", 1, pytest.approx(0.001))]


def test_startup_auth_failure_is_not_retried(tmp_path: Path) -> None:
    methods_path = tmp_path / "auth-methods.jsonl"
    command = _write_bridge_script(
        tmp_path,
        f"""
        import json
        import pathlib
        import sys

        methods_path = pathlib.Path({str(methods_path)!r})
        hello = {_hello_payload()!r}
        for raw in sys.stdin:
            request = json.loads(raw)
            method = request.get("method")
            with methods_path.open("a", encoding="utf-8") as handle:
                print(json.dumps(method), file=handle)
            if method == "hello":
                response = {{"id": request["id"], "ok": True, "data": hello}}
            elif method == "connect":
                response = {{
                    "id": request["id"],
                    "ok": False,
                    "error": "must never surface",
                    "errorCode": "auth_failed",
                    "retryable": False,
                }}
            else:
                response = {{"id": request["id"], "ok": True, "data": {{}}}}
            print(json.dumps(response), flush=True)
        """,
    )
    bridge = e2ee._BridgeProcess(Path(command[0]), command=command)
    try:
        with pytest.raises(e2ee.BridgeStartupError) as raised:
            bridge.connect_client(
                {"cookies": {}},
                enable_e2ee=False,
                reconnect_policy=_test_policy(max_attempts=None),
            )
        assert raised.value.phase == "regular connect"
        assert "must never surface" not in str(raised.value)
        assert e2ee._classify_bridge_connection_error(raised.value) == "auth_required"
    finally:
        bridge.close()

    methods = [
        json.loads(line)
        for line in methods_path.read_text(encoding="utf-8").splitlines()
    ]
    assert methods.count("newClient") == 1
    assert methods.count("connect") == 1


def test_unknown_permanent_startup_failure_is_not_retried(tmp_path: Path) -> None:
    methods_path = tmp_path / "permanent-methods.jsonl"
    command = _write_bridge_script(
        tmp_path,
        f"""
        import json
        import pathlib
        import sys

        methods_path = pathlib.Path({str(methods_path)!r})
        hello = {_hello_payload()!r}
        for raw in sys.stdin:
            request = json.loads(raw)
            method = request.get("method")
            with methods_path.open("a", encoding="utf-8") as handle:
                print(json.dumps(method), file=handle)
            if method == "hello":
                response = {{"id": request["id"], "ok": True, "data": hello}}
            elif method == "connect":
                response = {{
                    "id": request["id"],
                    "ok": False,
                    "errorCode": "connection_failed",
                    "retryable": False,
                }}
            else:
                response = {{"id": request["id"], "ok": True, "data": {{}}}}
            print(json.dumps(response), flush=True)
        """,
    )
    bridge = e2ee._BridgeProcess(Path(command[0]), command=command)
    try:
        with pytest.raises(e2ee.BridgeStartupError) as raised:
            bridge.connect_client(
                {"cookies": {}},
                enable_e2ee=False,
                reconnect_policy=_test_policy(max_attempts=None),
            )
        assert e2ee._classify_bridge_connection_error(raised.value) == "unknown"
    finally:
        bridge.close()
    methods = [
        json.loads(line)
        for line in methods_path.read_text(encoding="utf-8").splitlines()
    ]
    assert methods.count("connect") == 1


@pytest.mark.parametrize("memory_only", [False, True])
def test_startup_process_loss_respawns_only_with_persistent_device(
    tmp_path: Path, memory_only: bool
) -> None:
    launches_path = tmp_path / f"startup-launches-{memory_only}.txt"
    methods_path = tmp_path / f"startup-methods-{memory_only}.txt"
    command = _write_bridge_script(
        tmp_path,
        f"""
        import json
        import os
        import pathlib
        import sys

        launches_path = pathlib.Path({str(launches_path)!r})
        methods_path = pathlib.Path({str(methods_path)!r})
        old = launches_path.read_text(encoding="utf-8").splitlines() if launches_path.exists() else []
        generation = len(old) + 1
        with launches_path.open("a", encoding="utf-8") as handle:
            print(generation, file=handle)
        hello = {_hello_payload()!r}
        for raw in sys.stdin:
            request = json.loads(raw)
            method = request.get("method")
            with methods_path.open("a", encoding="utf-8") as handle:
                print(f"{{generation}}:{{method}}", file=handle)
            if generation == 1 and method == "connect":
                os._exit(21)
            if method == "hello":
                data = hello
            elif method == "isConnected":
                data = {{"connected": True, "e2eeConnected": True}}
            else:
                data = {{}}
            print(json.dumps({{"id": request["id"], "ok": True, "data": data}}), flush=True)
        """,
    )
    bridge = e2ee._BridgeProcess(
        Path(command[0]), command=command, reconnect_policy=_test_policy()
    )
    cfg = {"cookies": {}, "e2eeMemoryOnly": memory_only}
    try:
        if memory_only:
            with pytest.raises(e2ee.BridgeStartupError) as raised:
                bridge.connect_client(cfg, enable_e2ee=True)
            assert (
                e2ee._classify_bridge_connection_error(raised.value)
                == "device_state_lost"
            )
        else:
            bridge.connect_client(cfg, enable_e2ee=True)
    finally:
        bridge.close()

    launches = launches_path.read_text(encoding="utf-8").splitlines()
    methods = methods_path.read_text(encoding="utf-8").splitlines()
    if memory_only:
        assert launches == ["1"]
        assert methods.count("1:newClient") == 1
    else:
        assert launches == ["1", "2"]
        assert methods.count("1:newClient") == 1
        assert methods.count("2:newClient") == 1


def test_watchdog_waits_for_native_reconnect_without_respawning(tmp_path: Path) -> None:
    command = _write_bridge_script(
        tmp_path,
        f"""
        import json
        import sys

        hello = {_hello_payload()!r}
        status_calls = 0
        for raw in sys.stdin:
            request = json.loads(raw)
            method = request.get("method")
            if method == "hello":
                data = hello
            elif method == "isConnected":
                status_calls += 1
                if status_calls == 1 or status_calls >= 4:
                    data = {{"connected": True, "e2eeConnected": False}}
                else:
                    data = {{
                        "connected": False,
                        "e2eeConnected": False,
                        "nativeReconnecting": True,
                        "failureCode": "network_disconnected",
                        "retryable": True,
                        "permanent": False,
                    }}
            else:
                data = {{}}
            print(json.dumps({{"id": request["id"], "ok": True, "data": data}}), flush=True)
        """,
    )
    bridge = e2ee._BridgeProcess(
        Path(command[0]), command=command, reconnect_policy=_test_policy()
    )
    original_proc = bridge._proc
    bridge.HEALTH_INTERVAL = 0.01
    bridge.HEALTH_RPC_TIMEOUT = 0.5
    bridge.connect_client({"cookies": {}}, enable_e2ee=False)
    bridge.start_watchdog(connect_cfg={"cookies": {}}, enable_e2ee=False)
    try:
        reconnecting = _wait_for_event(bridge.events, e2ee._BRIDGE_STATE_EVENT)
        assert reconnecting["data"]["nativeReconnecting"] is True
        connected = _wait_for_event(bridge.events, e2ee._BRIDGE_STATE_EVENT)
        while connected.get("data", {}).get("connected") is not True:
            connected = _wait_for_event(bridge.events, e2ee._BRIDGE_STATE_EVENT)
        assert connected["data"]["connected"] is True
        assert bridge._proc is original_proc
        assert original_proc.poll() is None
    finally:
        bridge.close()


@pytest.mark.parametrize(
    ("policy", "expected_reason", "expected_retries"),
    [
        (ReconnectPolicy(enabled=False), "retry_disabled", 0),
        (_test_policy(max_attempts=1), "retry_exhausted", 1),
    ],
)
def test_bounded_policy_stops_native_reconnect_without_respawn(
    tmp_path: Path,
    policy: ReconnectPolicy,
    expected_reason: str,
    expected_retries: int,
) -> None:
    command = _write_bridge_script(
        tmp_path,
        f"""
        import json
        import sys

        hello = {_hello_payload()!r}
        status_calls = 0
        for raw in sys.stdin:
            request = json.loads(raw)
            method = request.get("method")
            if method == "hello":
                data = hello
            elif method == "isConnected":
                status_calls += 1
                if status_calls == 1:
                    data = {{"connected": True, "e2eeConnected": False}}
                else:
                    data = {{
                        "connected": False,
                        "e2eeConnected": False,
                        "nativeReconnecting": True,
                        "failureCode": "network_disconnected",
                        "retryable": True,
                        "permanent": False,
                    }}
            else:
                data = {{}}
            print(json.dumps({{"id": request["id"], "ok": True, "data": data}}), flush=True)
        """,
    )
    bridge = e2ee._BridgeProcess(
        Path(command[0]), command=command, reconnect_policy=policy
    )
    original_proc = bridge._proc
    bridge.HEALTH_INTERVAL = 0.01
    bridge.HEALTH_RPC_TIMEOUT = 0.5
    bridge.connect_client({"cookies": {}}, enable_e2ee=False)
    bridge.start_watchdog(connect_cfg={"cookies": {}}, enable_e2ee=False)
    try:
        fatal = _wait_for_event(bridge.events, "bridge_fatal")
        assert fatal["reason"] == expected_reason
        assert fatal["retries"] == expected_retries
        assert bridge._proc is original_proc
        assert original_proc.poll() is None
    finally:
        bridge.close()


def test_memory_only_device_state_loss_never_respawns(tmp_path: Path) -> None:
    launches_path = tmp_path / "memory-launches.txt"
    command = _write_bridge_script(
        tmp_path,
        f"""
        import json
        import os
        import pathlib
        import sys

        launches_path = pathlib.Path({str(launches_path)!r})
        with launches_path.open("a", encoding="utf-8") as handle:
            print("launch", file=handle)
        hello = {_hello_payload()!r}
        for raw in sys.stdin:
            request = json.loads(raw)
            method = request.get("method")
            if method == "crash":
                os._exit(12)
            if method == "hello":
                data = hello
            elif method == "isConnected":
                data = {{"connected": True, "e2eeConnected": True}}
            else:
                data = {{}}
            print(json.dumps({{"id": request["id"], "ok": True, "data": data}}), flush=True)
        """,
    )
    bridge = e2ee._BridgeProcess(
        Path(command[0]),
        command=command,
        reconnect_policy=_test_policy(max_attempts=None),
    )
    bridge.HEALTH_INTERVAL = 0.01
    bridge.HEALTH_RPC_TIMEOUT = 0.5
    cfg = {"cookies": {}, "e2eeMemoryOnly": True}
    try:
        bridge.connect_client(cfg, enable_e2ee=True)
        bridge.start_watchdog(connect_cfg=cfg, enable_e2ee=True)
        with pytest.raises(e2ee.BridgeError):
            bridge.call_blocking("crash", timeout=0.5)
        fatal = _wait_for_event(bridge.events, "bridge_fatal")
        assert fatal["reason"] == "device_state_lost"
        assert launches_path.read_text(encoding="utf-8").splitlines() == ["launch"]
    finally:
        bridge.close()


def test_persistent_respawn_emits_payload_free_gap_event(tmp_path: Path) -> None:
    launches_path = tmp_path / "persistent-launches.txt"
    command = _write_bridge_script(
        tmp_path,
        f"""
        import json
        import os
        import pathlib
        import sys

        launches_path = pathlib.Path({str(launches_path)!r})
        old = launches_path.read_text(encoding="utf-8").splitlines() if launches_path.exists() else []
        generation = len(old) + 1
        with launches_path.open("a", encoding="utf-8") as handle:
            print(generation, file=handle)
        hello = {_hello_payload()!r}
        for raw in sys.stdin:
            request = json.loads(raw)
            method = request.get("method")
            if method == "crash" and generation == 1:
                os._exit(13)
            if method == "hello":
                data = hello
            elif method == "isConnected":
                data = {{"connected": True, "e2eeConnected": True}}
            else:
                data = {{}}
            print(json.dumps({{"id": request["id"], "ok": True, "data": data}}), flush=True)
        """,
    )
    bridge = e2ee._BridgeProcess(
        Path(command[0]), command=command, reconnect_policy=_test_policy()
    )
    bridge.HEALTH_INTERVAL = 0.01
    bridge.HEALTH_RPC_TIMEOUT = 0.5
    cfg = {"cookies": {}, "e2eeMemoryOnly": False}
    try:
        bridge.connect_client(cfg, enable_e2ee=True)
        bridge.start_watchdog(connect_cfg=cfg, enable_e2ee=True)
        with pytest.raises(e2ee.BridgeError):
            bridge.call_blocking("crash", timeout=0.5)
        gap = _wait_for_event(bridge.events, "potential_message_gap")
        assert gap == {
            "type": "potential_message_gap",
            "data": {"reason": "bridge_respawn", "generation": 2},
        }
        assert launches_path.read_text(encoding="utf-8").splitlines() == ["1", "2"]
    finally:
        bridge.close()


@pytest.mark.asyncio
async def test_async_cancellation_stops_and_joins_bridge_worker(
    monkeypatch: pytest.MonkeyPatch,
    mock_dataFB: dict[str, Any],
    tmp_path: Path,
) -> None:
    binary = tmp_path / "bridge"
    binary.write_bytes(b"placeholder")
    connect_started = threading.Event()

    class BlockingBridge:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.events: Queue[dict[str, Any]] = Queue()
            self.closed = threading.Event()

        def connect_client(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            connect_started.set()
            if not self.closed.wait(2.0):
                raise AssertionError("listener cancellation did not close bridge")
            raise e2ee.BridgeError("bridge process is closing")

        def start_watchdog(self, *args: Any, **kwargs: Any) -> None:
            raise AssertionError("watchdog must not start after cancellation")

        def close(self) -> None:
            self.closed.set()

    created: list[BlockingBridge] = []

    def create_bridge(*args: Any, **kwargs: Any) -> BlockingBridge:
        bridge = BlockingBridge()
        created.append(bridge)
        return bridge

    monkeypatch.setattr(e2ee, "_resolve_binary", lambda: binary)
    monkeypatch.setattr(e2ee, "_BridgeProcess", create_bridge)
    listener = e2ee.listeningE2EEEvent(mock_dataFB)
    task = asyncio.create_task(listener.connect_mqtt())
    assert await asyncio.to_thread(connect_started.wait, 1.0)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert created[0].closed.is_set()
    assert listener._bridge is None
    assert listener.connection_status == {
        "state": "stopped",
        "reason": "stopped",
        "attempt": 0,
        "next_retry_in": 0.0,
    }


@pytest.mark.asyncio
async def test_cancelling_unclaimed_second_caller_does_not_stop_owner(
    monkeypatch: pytest.MonkeyPatch,
    mock_dataFB: dict[str, Any],
    tmp_path: Path,
) -> None:
    binary = tmp_path / "bridge"
    binary.write_bytes(b"placeholder")
    owner_ready = threading.Event()

    class RunningBridge:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.events: Queue[dict[str, Any]] = Queue()
            self.closed = threading.Event()

        def connect_client(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            return {}

        def start_watchdog(self, *args: Any, **kwargs: Any) -> None:
            owner_ready.set()

        def close(self) -> None:
            self.closed.set()

    bridge = RunningBridge()
    monkeypatch.setattr(e2ee, "_resolve_binary", lambda: binary)
    monkeypatch.setattr(e2ee, "_BridgeProcess", lambda *args, **kwargs: bridge)

    real_to_thread = asyncio.to_thread
    release_second = asyncio.Event()
    to_thread_calls = 0

    async def controlled_to_thread(function: Any, /, *args: Any, **kwargs: Any) -> Any:
        nonlocal to_thread_calls
        to_thread_calls += 1
        if to_thread_calls == 2:
            await release_second.wait()
        return await real_to_thread(function, *args, **kwargs)

    monkeypatch.setattr(e2ee.asyncio, "to_thread", controlled_to_thread)
    listener = e2ee.listeningE2EEEvent(mock_dataFB, enable_e2ee=False)
    owner = asyncio.create_task(listener.connect_mqtt())
    assert await real_to_thread(owner_ready.wait, 1.0)

    second = asyncio.create_task(listener.connect_mqtt())
    await asyncio.sleep(0)
    second.cancel()
    await asyncio.sleep(0)
    release_second.set()
    with pytest.raises(asyncio.CancelledError):
        await second

    assert not bridge.closed.is_set()
    assert not owner.done()
    listener.stop()
    await asyncio.wait_for(owner, timeout=2.0)
    assert bridge.closed.is_set()


def test_listener_exposes_safe_terminal_state_and_bounds_cross_generation_dedupe(
    mock_dataFB: dict[str, Any],
) -> None:
    snapshots: list[dict[str, Any]] = []
    delivered: list[dict[str, Any]] = []
    listener = e2ee.listeningE2EEEvent(
        mock_dataFB, on_connection_state=snapshots.append
    )
    listener._update_connection_state("starting")
    listener._update_connection_state("connected")
    listener.on_message(delivered.append)

    event = {"type": "e2eeMessage", "data": {"id": "mid.1", "text": "x"}}
    listener._dispatch(event)
    listener._dispatch(event)
    assert delivered == [event]
    assert len(listener._recent_message_keys) == 1

    listener._update_connection_state("auth_required", reason="auth_required")
    listener._update_connection_state("reconnecting", reason="network", attempt=99)
    assert listener.connection_status == {
        "state": "auth_required",
        "reason": "auth_required",
        "attempt": 0,
        "next_retry_in": 0.0,
    }
    assert snapshots[-1]["state"] == "auth_required"
    assert all(
        set(snapshot) == {"state", "reason", "attempt", "next_retry_in"}
        for snapshot in snapshots
    )


def test_parent_dedupe_ignores_empty_ids_and_uses_fixed_ttl(
    monkeypatch: pytest.MonkeyPatch, mock_dataFB: dict[str, Any]
) -> None:
    listener = e2ee.listeningE2EEEvent(mock_dataFB)
    delivered: list[dict[str, Any]] = []
    listener.on_message(delivered.append)
    times = iter((0.0, 5.0, listener._RECENT_MESSAGE_TTL + 1.0, 612.0))
    monkeypatch.setattr(e2ee.time, "monotonic", lambda: next(times))

    empty = {"type": "message", "data": {"id": "", "text": "empty"}}
    first = {"type": "message", "data": {"id": "mid.1", "text": "one"}}
    second = {"type": "message", "data": {"id": "mid.2", "text": "two"}}
    listener._dispatch(empty)
    listener._dispatch(empty)
    listener._dispatch(first)
    listener._dispatch(first)
    listener._dispatch(second)
    listener._dispatch(first)

    assert delivered == [empty, empty, first, second, first]


def test_device_state_lost_reason_survives_nonretryable_wrapper() -> None:
    loss = e2ee._BridgeConnectionError(
        "device_state_lost", retryable=False, permanent=True
    )
    wrapped = e2ee.BridgeStartupError("new client", loss)

    assert e2ee._classify_bridge_connection_error(wrapped) == "device_state_lost"


@pytest.mark.parametrize("publish_native_state", [False, True])
def test_native_reconnect_events_restore_ready_flags_without_generation_barrier(
    mock_dataFB: dict[str, Any], publish_native_state: bool
) -> None:
    class FakeBridge:
        def __init__(self) -> None:
            self.events: Queue[dict[str, Any]] = Queue()

        def close(self) -> None:
            return None

    bridge = FakeBridge()
    if publish_native_state:
        bridge.events.put(
            {
                "type": e2ee._BRIDGE_STATE_EVENT,
                "data": {
                    "connected": False,
                    "e2eeConnected": False,
                    "nativeReconnecting": True,
                    "reason": "network",
                    "attempt": 1,
                    "nextRetryIn": 0.01,
                },
            }
        )
    bridge.events.put(
        {
            "type": "disconnected",
            "data": {
                "isE2EE": False,
                "failureCode": "network_disconnected",
                "retryable": True,
            },
        }
    )
    bridge.events.put({"type": "reconnected", "data": {}})
    bridge.events.put({"type": "e2eeConnected", "data": {}})
    bridge.events.put({"type": "bridge_fatal", "reason": "unknown"})

    listener = e2ee.listeningE2EEEvent(mock_dataFB)
    listener._bridge = bridge  # type: ignore[assignment]
    observed: list[tuple[str, bool, bool]] = []
    listener.on_message(
        lambda event: observed.append(
            (
                str(event["type"]),
                listener._connected.is_set(),
                listener._e2ee_connected.is_set(),
            )
        )
    )

    with pytest.raises(e2ee.BridgeError, match="retry budget"):
        listener._poll_loop(bridge)  # type: ignore[arg-type]

    assert observed[-3:] == [
        ("disconnected", False, False),
        ("reconnected", True, False),
        ("e2eeConnected", True, True),
    ]


@pytest.mark.asyncio
async def test_double_cancellation_keeps_cleanup_alive_and_does_not_block_loop(
    monkeypatch: pytest.MonkeyPatch,
    mock_dataFB: dict[str, Any],
    tmp_path: Path,
) -> None:
    binary = tmp_path / "bridge"
    binary.write_bytes(b"placeholder")
    connect_started = threading.Event()
    close_started = threading.Event()

    class SlowCloseBridge:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.events: Queue[dict[str, Any]] = Queue()
            self.closed = threading.Event()

        def connect_client(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            connect_started.set()
            self.closed.wait()
            raise e2ee.BridgeError("bridge process is closing")

        def start_watchdog(self, *args: Any, **kwargs: Any) -> None:
            raise AssertionError("watchdog must not start after cancellation")

        def close(self) -> None:
            close_started.set()
            time.sleep(0.1)
            self.closed.set()

    bridge = SlowCloseBridge()
    monkeypatch.setattr(e2ee, "_resolve_binary", lambda: binary)
    monkeypatch.setattr(e2ee, "_BridgeProcess", lambda *args, **kwargs: bridge)
    listener = e2ee.listeningE2EEEvent(mock_dataFB)
    task = asyncio.create_task(listener.connect_mqtt())
    assert await asyncio.to_thread(connect_started.wait, 1.0)

    task.cancel()
    assert await asyncio.to_thread(close_started.wait, 1.0)
    await asyncio.sleep(0.01)
    assert not bridge.closed.is_set()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert bridge.closed.is_set()
    assert listener._bridge is None
