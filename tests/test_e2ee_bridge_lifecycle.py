from __future__ import annotations

import asyncio
import io
import sys
import textwrap
import threading
import time
from pathlib import Path
from queue import Empty, Queue
from typing import Any

import pytest

import main as sample_main
from _messaging import _listening_e2ee as e2ee
from _messaging import _send_e2ee as e2ee_sender


def _write_bridge_script(tmp_path: Path, source: str) -> tuple[str, ...]:
    script = tmp_path / "fake_bridge.py"
    script.write_text(textwrap.dedent(source), encoding="utf-8")
    return (sys.executable, "-u", str(script))


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


def _wait_for_blocked_writer(bridge: e2ee._BridgeProcess, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        acquired = bridge._write_lock.acquire(blocking=False)
        if not acquired:
            return
        bridge._write_lock.release()
        time.sleep(0.005)
    raise AssertionError("bridge writer did not block")


def _contract_script(
    *,
    bridge_version: str = "2.3.2",
    connected: bool = True,
    e2ee_connected: bool = True,
) -> str:
    return f"""
        import json
        import sys

        hello = {{
            "protocolVersion": 1,
            "bridgeVersion": {bridge_version!r},
            "capabilities": [
                "newClient", "connect", "connectE2EE", "isConnected", "events"
            ],
        }}
        for raw in sys.stdin:
            request = json.loads(raw)
            method = request.get("method")
            if method == "hello":
                data = hello
            elif method == "isConnected":
                data = {{
                    "connected": {connected!r},
                    "e2eeConnected": {e2ee_connected!r},
                }}
            else:
                data = {{}}
            print(json.dumps({{"id": request["id"], "ok": True, "data": data}}), flush=True)
    """


def test_bridge_subprocess_contract_and_shutdown_are_hermetic(tmp_path: Path) -> None:
    command = _write_bridge_script(tmp_path, _contract_script())
    bridge = e2ee._BridgeProcess(Path(command[0]), command=command)
    proc = bridge._proc
    try:
        hello = bridge._validate_contract()
        assert hello["protocolVersion"] == 1
        assert hello["bridgeVersion"] == "2.3.2"
    finally:
        bridge.close()
    assert proc.poll() is not None


@pytest.mark.parametrize("failing_method", ["newClient", "connect", "connectE2EE"])
def test_standalone_sender_reaps_bridge_after_handshake_failure(
    monkeypatch: pytest.MonkeyPatch,
    mock_dataFB: dict[str, Any],
    failing_method: str,
) -> None:
    instances: list[Any] = []

    class FakeBridge:
        def __init__(self, binary: Path) -> None:
            self.binary = binary
            self.closed = False
            self.calls: list[str] = []
            instances.append(self)

        def call_blocking(
            self,
            method: str,
            params: dict[str, Any] | None = None,
            timeout: float = 60.0,
        ) -> dict[str, Any]:
            self.calls.append(method)
            if method == failing_method:
                raise e2ee.BridgeError(f"{method} failed")
            if method == "connect":
                return {"user": {"id": "10001234567890"}}
            return {}

        def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(e2ee_sender, "_BridgeProcess", FakeBridge)
    sender = e2ee_sender.api(dataFB=mock_dataFB, binary_path="fake-bridge")

    with pytest.raises(e2ee.BridgeError, match=f"{failing_method} failed"):
        sender.connect()

    assert len(instances) == 1
    assert instances[0].closed is True
    assert sender._bridge is None
    assert sender._connected is False


def test_standalone_sender_exposes_unknown_delivery_without_success() -> None:
    class FakeBridge:
        def call_blocking(
            self,
            method: str,
            params: dict[str, Any] | None = None,
            timeout: float = 60.0,
        ) -> dict[str, Any]:
            assert method == "sendE2EEMessage"
            return {
                "messageId": "mid-timeout",
                "timestampMs": 1_700_000_000_123,
                "deliveryStatus": e2ee.DELIVERY_STATUS_UNKNOWN,
            }

    class FakeListener:
        _bridge = FakeBridge()

    sender = e2ee_sender.api(listener=FakeListener())  # type: ignore[arg-type]

    result = sender.send("2000@msgr", "không được tự gửi lại")

    assert "success" not in result
    assert result["uncertain"] == 1
    assert result["payload"] == {
        "messageID": "mid-timeout",
        "timestamp": 1_700_000_000_123,
        "deliveryStatus": e2ee.DELIVERY_STATUS_UNKNOWN,
        "retryable": False,
    }


def test_bridge_event_queue_drops_oldest_and_reports_redacted_telemetry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(e2ee._BridgeProcess, "MAX_EVENT_QUEUE_SIZE", 2)
    command = _write_bridge_script(tmp_path, _contract_script())
    bridge = e2ee._BridgeProcess(Path(command[0]), command=command)
    try:
        bridge._enqueue_event(
            {"type": "message", "data": {"id": "old", "text": "OLD_SECRET"}}
        )
        second = {
            "type": "message",
            "data": {"id": "second", "text": "SECOND_SECRET"},
        }
        newest = {"type": "ready", "data": {"marker": "NEWEST_SECRET"}}
        bridge._enqueue_event(second)
        bridge._enqueue_event(newest)

        assert bridge.events.qsize() == 2
        assert bridge.events.get_nowait() == second
        assert bridge.events.get_nowait() == newest
        assert bridge.dropped_event_count == 1
        stderr = capsys.readouterr().err
        assert "dropped 1 oldest event" in stderr
        assert "OLD_SECRET" not in stderr
        assert "SECOND_SECRET" not in stderr
        assert "NEWEST_SECRET" not in stderr
    finally:
        bridge.close()


def test_bridge_contract_rejects_wrong_binary_version(tmp_path: Path) -> None:
    command = _write_bridge_script(
        tmp_path, _contract_script(bridge_version="0.0.0-incompatible")
    )
    bridge = e2ee._BridgeProcess(Path(command[0]), command=command)
    try:
        with pytest.raises(e2ee.BridgeError, match="version does not match"):
            bridge._validate_contract()
    finally:
        bridge.close()


def test_bridge_reader_ignores_valid_json_that_is_not_an_object(tmp_path: Path) -> None:
    command = _write_bridge_script(
        tmp_path,
        f"""
        import json
        import sys

        sys.stdout.buffer.write(b"\\xff\\n")
        sys.stdout.buffer.flush()
        print(json.dumps([]), flush=True)
        print(json.dumps("diagnostic"), flush=True)
        {_contract_script()}
        """,
    )
    bridge = e2ee._BridgeProcess(Path(command[0]), command=command)
    try:
        assert bridge._validate_contract()["bridgeVersion"] == "2.3.2"
        assert bridge._reader.is_alive()
    finally:
        bridge.close()


def test_bridge_reader_rejects_malformed_event_shapes_before_callback_queue(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    command = _write_bridge_script(
        tmp_path,
        """
        import json
        import sys

        invalid_envelopes = [
            {"event": "PRIVATE_NON_OBJECT"},
            {"event": {"type": 123, "data": {}, "timestamp": 1}},
            {"event": {"type": "message", "data": ["PRIVATE_LIST"], "timestamp": 1}},
            {"event": {"type": "message", "data": {"text": "PRIVATE"}}},
        ]
        for envelope in invalid_envelopes:
            print(json.dumps(envelope), flush=True)
        valid_event = {"type": "ready", "data": {}, "timestamp": 2}
        print(json.dumps({"event": valid_event}), flush=True)

        for raw in sys.stdin:
            request = json.loads(raw)
            print(
                json.dumps({"id": request["id"], "ok": True, "data": {}}),
                flush=True,
            )
        """,
    )
    bridge = e2ee._BridgeProcess(Path(command[0]), command=command)
    try:
        assert bridge.call_blocking("barrier") == {}
        assert bridge.events.get(timeout=0.5) == {
            "type": "ready",
            "data": {},
            "timestamp": 2,
        }
        assert bridge.events.empty()
        stderr = capsys.readouterr().err
        assert stderr.count("invalid event shape") == 4
        assert "PRIVATE" not in stderr
    finally:
        bridge.close()


def test_safe_print_escapes_unicode_for_cp1252_console() -> None:
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(
        buffer,
        encoding="cp1252",
        errors="strict",
        newline="\n",
        write_through=True,
    )

    e2ee._safe_print("handler raised: lỗi 💥", file=stream)

    logged = buffer.getvalue().decode("cp1252")
    assert "handler raised:" in logged
    assert "\\u1ed7" in logged
    assert "\\U0001f4a5" in logged
    stream.close()


def test_bridge_spawn_reaps_process_when_reader_thread_cannot_start(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    command = _write_bridge_script(
        tmp_path,
        """
        import time

        while True:
            time.sleep(1)
        """,
    )
    created: list[Any] = []
    real_popen = e2ee.subprocess.Popen

    def tracked_popen(*args: Any, **kwargs: Any) -> Any:
        proc = real_popen(*args, **kwargs)
        created.append(proc)
        return proc

    def fail_thread_start(self: threading.Thread) -> None:
        raise RuntimeError("thread runtime unavailable")

    monkeypatch.setattr(e2ee.subprocess, "Popen", tracked_popen)
    monkeypatch.setattr(e2ee.threading.Thread, "start", fail_thread_start)

    with pytest.raises(RuntimeError, match="thread runtime unavailable"):
        e2ee._BridgeProcess(Path(command[0]), command=command)

    assert len(created) == 1
    assert created[0].poll() is not None


def test_stale_reader_exit_cannot_stop_new_generation_writer(tmp_path: Path) -> None:
    command = _write_bridge_script(tmp_path, _contract_script())
    bridge = e2ee._BridgeProcess(Path(command[0]), command=command)
    old_proc, old_generation = bridge._snapshot_process()
    old_writer_queue = bridge._writer_queue
    try:
        bridge._terminate_process(old_proc, graceful_timeout=0.0)
        new_generation = bridge._spawn()
        assert new_generation == old_generation + 1

        bridge._mark_generation_exited(old_proc, old_generation, old_writer_queue)
        assert bridge._validate_contract()["bridgeVersion"] == "2.3.2"
        assert bridge._writer.is_alive()
    finally:
        bridge.close()


def test_bridge_writer_handles_short_raw_pipe_writes(tmp_path: Path) -> None:
    command = _write_bridge_script(tmp_path, _contract_script())
    bridge = e2ee._BridgeProcess(Path(command[0]), command=command)
    raw_stdin = bridge._proc.stdin
    assert raw_stdin is not None

    class ShortWritePipe:
        def write(self, data: Any) -> int:
            chunk = bytes(data[:7])
            written = raw_stdin.write(chunk)
            assert written is not None
            return written

        def flush(self) -> None:
            raw_stdin.flush()

        def close(self) -> None:
            raw_stdin.close()

    bridge._proc.stdin = ShortWritePipe()  # type: ignore[assignment]
    try:
        assert bridge._validate_contract()["bridgeVersion"] == "2.3.2"
    finally:
        bridge.close()


def test_writer_transport_failure_taints_generation_and_watchdog_recovers(
    tmp_path: Path,
) -> None:
    command = _write_bridge_script(tmp_path, _contract_script())
    bridge = e2ee._BridgeProcess(Path(command[0]), command=command)
    first_proc = bridge._proc
    raw_stdin = first_proc.stdin
    assert raw_stdin is not None

    class BrokenWritePipe:
        def write(self, data: Any) -> int:
            raise BrokenPipeError("synthetic broken pipe")

        def flush(self) -> None:
            return None

        def close(self) -> None:
            raw_stdin.close()

    first_proc.stdin = BrokenWritePipe()  # type: ignore[assignment]
    bridge.HEALTH_INTERVAL = 0.01
    bridge.HEALTH_RPC_TIMEOUT = 0.5
    bridge.BASE_BACKOFF = 0.01
    try:
        with pytest.raises(e2ee.BridgeError, match="write failed"):
            bridge.call_blocking("hello", timeout=0.5)
        assert first_proc.poll() is None
        assert not bridge._writer.is_alive()

        started = time.monotonic()
        with pytest.raises(e2ee.BridgeError, match="recovering after an RPC timeout"):
            bridge.call_blocking("must-not-queue", timeout=0.5)
        assert time.monotonic() - started < 0.1

        bridge.start_watchdog(enable_e2ee=False)
        state = _wait_for_event(bridge.events, e2ee._BRIDGE_STATE_EVENT)
        while not isinstance(state.get("data", {}).get("generation"), int):
            state = _wait_for_event(bridge.events, e2ee._BRIDGE_STATE_EVENT)
        assert first_proc.poll() is not None
        assert bridge._validate_contract()["bridgeVersion"] == "2.3.2"
    finally:
        bridge.close()


def test_reader_transport_failure_taints_generation_and_watchdog_recovers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    command = _write_bridge_script(tmp_path, _contract_script())
    real_popen = e2ee.subprocess.Popen
    wrapped_streams: list[Any] = []

    class FailingStdout:
        def __init__(self, raw: Any) -> None:
            self.raw = raw

        def __iter__(self) -> FailingStdout:
            return self

        def __next__(self) -> bytes:
            raise OSError("synthetic stdout failure")

        def close(self) -> None:
            self.raw.close()

    def failing_reader_popen(*args: Any, **kwargs: Any) -> Any:
        proc = real_popen(*args, **kwargs)
        assert proc.stdout is not None
        wrapped = FailingStdout(proc.stdout)
        wrapped_streams.append(wrapped)
        proc.stdout = wrapped
        return proc

    monkeypatch.setattr(e2ee.subprocess, "Popen", failing_reader_popen)
    bridge = e2ee._BridgeProcess(Path(command[0]), command=command)
    first_proc = bridge._proc
    monkeypatch.setattr(e2ee.subprocess, "Popen", real_popen)
    bridge.HEALTH_INTERVAL = 0.01
    bridge.HEALTH_RPC_TIMEOUT = 0.5
    bridge.BASE_BACKOFF = 0.01
    try:
        deadline = time.monotonic() + 1.0
        while bridge._timed_out_generation is None and time.monotonic() < deadline:
            time.sleep(0.005)
        assert bridge._timed_out_generation == 1
        assert first_proc.poll() is None

        with pytest.raises(e2ee.BridgeError, match="recovering after an RPC timeout"):
            bridge.call_blocking("must-not-queue", timeout=0.5)

        bridge.start_watchdog(enable_e2ee=False)
        state = _wait_for_event(bridge.events, e2ee._BRIDGE_STATE_EVENT)
        while not isinstance(state.get("data", {}).get("generation"), int):
            state = _wait_for_event(bridge.events, e2ee._BRIDGE_STATE_EVENT)
        assert first_proc.poll() is not None
        assert bridge._validate_contract()["bridgeVersion"] == "2.3.2"
    finally:
        bridge.close()
        for stream in wrapped_streams:
            stream.close()


def test_close_cannot_overtake_an_accepted_writer_enqueue(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    command = _write_bridge_script(tmp_path, _contract_script())
    bridge = e2ee._BridgeProcess(Path(command[0]), command=command)
    proc = bridge._proc
    enqueue_entered = threading.Event()
    allow_enqueue = threading.Event()
    original_put = bridge._writer_queue.put

    def barrier_put(item: Any, *args: Any, **kwargs: Any) -> None:
        if item is not None and not enqueue_entered.is_set():
            enqueue_entered.set()
            if not allow_enqueue.wait(2.0):
                raise RuntimeError("test did not release writer enqueue")
        original_put(item, *args, **kwargs)

    monkeypatch.setattr(bridge._writer_queue, "put", barrier_put)
    call_errors: list[BaseException] = []

    def call_hello() -> None:
        try:
            bridge.call_blocking("hello", timeout=1.0)
        except BaseException as exc:
            call_errors.append(exc)

    caller = threading.Thread(target=call_hello)
    closer = threading.Thread(target=bridge.close)
    caller.start()
    try:
        assert enqueue_entered.wait(2.0)
        closer.start()
        time.sleep(0.05)
        assert closer.is_alive()

        allow_enqueue.set()
        caller.join(timeout=2.0)
        closer.join(timeout=2.0)
        assert not caller.is_alive()
        assert not closer.is_alive()
        assert proc.poll() is not None
        assert len(call_errors) <= 1
    finally:
        allow_enqueue.set()
        bridge.close()
        caller.join(timeout=2.0)
        if closer.ident is not None:
            closer.join(timeout=2.0)


def test_watchdog_keeps_contract_valid_idle_bridge_alive(tmp_path: Path) -> None:
    command = _write_bridge_script(
        tmp_path,
        _contract_script(connected=False, e2ee_connected=False),
    )
    bridge = e2ee._BridgeProcess(Path(command[0]), command=command)
    original_proc = bridge._proc
    bridge.HEALTH_INTERVAL = 0.01
    bridge.HEALTH_RPC_TIMEOUT = 0.5
    bridge.BASE_BACKOFF = 0.01
    bridge.UNHEALTHY_CHECK_LIMIT = 1
    bridge.start_watchdog(enable_e2ee=False)
    try:
        time.sleep(0.15)
        assert bridge._proc is original_proc
        assert original_proc.poll() is None
    finally:
        bridge.close()


def test_malformed_health_payload_causes_recovery_instead_of_watchdog_death(
    tmp_path: Path,
) -> None:
    launches = tmp_path / "launches.txt"
    command = _write_bridge_script(
        tmp_path,
        f"""
        import json
        import pathlib
        import sys

        launches = pathlib.Path({str(launches)!r})
        previous = launches.read_text(encoding="utf-8").splitlines() if launches.exists() else []
        generation = len(previous) + 1
        with launches.open("a", encoding="utf-8") as handle:
            print(generation, file=handle)
        hello_calls = 0
        hello = {{
            "protocolVersion": 1,
            "bridgeVersion": "2.3.2",
            "capabilities": [
                "newClient", "connect", "connectE2EE", "isConnected", "events"
            ],
        }}
        for raw in sys.stdin:
            request = json.loads(raw)
            method = request.get("method")
            if method == "hello":
                hello_calls += 1
                data = [1] if generation == 1 and hello_calls > 1 else hello
            elif method == "isConnected":
                data = {{"connected": False, "e2eeConnected": False}}
            else:
                data = {{}}
            print(json.dumps({{"id": request["id"], "ok": True, "data": data}}), flush=True)
        """,
    )
    bridge = e2ee._BridgeProcess(Path(command[0]), command=command)
    first_proc = bridge._proc
    bridge.HEALTH_INTERVAL = 0.01
    bridge.HEALTH_RPC_TIMEOUT = 0.5
    bridge.BASE_BACKOFF = 0.01
    try:
        assert bridge._validate_contract()["bridgeVersion"] == "2.3.2"
        watchdog = bridge.start_watchdog(enable_e2ee=False)

        state = _wait_for_event(bridge.events, e2ee._BRIDGE_STATE_EVENT)
        while not isinstance(state.get("data", {}).get("generation"), int):
            state = _wait_for_event(bridge.events, e2ee._BRIDGE_STATE_EVENT)
        assert watchdog.is_alive()
        assert first_proc.poll() is not None
        assert bridge._proc is not first_proc
        assert bridge._validate_contract()["bridgeVersion"] == "2.3.2"
    finally:
        bridge.close()


def test_watchdog_does_not_kill_a_valid_long_running_rpc(tmp_path: Path) -> None:
    launches = tmp_path / "launches.txt"
    command = _write_bridge_script(
        tmp_path,
        f"""
        import json
        import pathlib
        import sys
        import time

        state = pathlib.Path({str(launches)!r})
        with state.open("a", encoding="utf-8") as handle:
            print("launch", file=handle)
        hello = {{
            "protocolVersion": 1,
            "bridgeVersion": "2.3.2",
            "capabilities": [
                "newClient", "connect", "connectE2EE", "isConnected", "events"
            ],
        }}
        for raw in sys.stdin:
            request = json.loads(raw)
            method = request.get("method")
            if method == "slow":
                time.sleep(0.25)
            data = hello if method == "hello" else {{
                "connected": True, "e2eeConnected": False
            }} if method == "isConnected" else {{"finished": True}}
            print(json.dumps({{"id": request["id"], "ok": True, "data": data}}), flush=True)
        """,
    )
    bridge = e2ee._BridgeProcess(Path(command[0]), command=command)
    bridge.HEALTH_INTERVAL = 0.01
    bridge.HEALTH_RPC_TIMEOUT = 0.05
    bridge.start_watchdog(enable_e2ee=False)
    try:
        assert bridge.call_blocking("slow", timeout=1.0) == {"finished": True}
        time.sleep(0.1)
        assert len(launches.read_text(encoding="utf-8").splitlines()) == 1
        assert bridge._proc.poll() is None
    finally:
        bridge.close()


def test_watchdog_kills_hung_rpc_and_respawns(tmp_path: Path) -> None:
    launches = tmp_path / "launches.txt"
    command = _write_bridge_script(
        tmp_path,
        f"""
        import json
        import pathlib
        import sys
        import time

        state = pathlib.Path({str(launches)!r})
        with state.open("a", encoding="utf-8") as handle:
            print("launch", file=handle)
        hello = {{
            "protocolVersion": 1,
            "bridgeVersion": "2.3.2",
            "capabilities": [
                "newClient", "connect", "connectE2EE", "isConnected", "events"
            ],
        }}
        for raw in sys.stdin:
            request = json.loads(raw)
            method = request.get("method")
            if method == "hang":
                time.sleep(3600)
            data = hello if method == "hello" else {{
                "connected": True, "e2eeConnected": True
            }} if method == "isConnected" else {{}}
            print(json.dumps({{"id": request["id"], "ok": True, "data": data}}), flush=True)
        """,
    )
    bridge = e2ee._BridgeProcess(Path(command[0]), command=command)
    bridge.HEALTH_INTERVAL = 0.02
    bridge.HEALTH_RPC_TIMEOUT = 0.5
    bridge.BASE_BACKOFF = 0.01
    bridge.STABLE_UPTIME = 10.0
    try:
        bridge._validate_contract()
        bridge.start_watchdog(enable_e2ee=False)
        with pytest.raises(e2ee.BridgeError, match="timed out"):
            bridge.call_blocking("hang", timeout=0.05)

        state = _wait_for_event(bridge.events, e2ee._BRIDGE_STATE_EVENT)
        while state.get("data", {}).get("generation") is None:
            state = _wait_for_event(bridge.events, e2ee._BRIDGE_STATE_EVENT)
        assert len(launches.read_text(encoding="utf-8").splitlines()) >= 2
        bridge._validate_contract()
    finally:
        bridge.close()


def test_blocked_pipe_write_honors_timeout_and_close_is_bounded(tmp_path: Path) -> None:
    command = _write_bridge_script(
        tmp_path,
        """
        import time

        while True:
            time.sleep(1)
        """,
    )
    bridge = e2ee._BridgeProcess(Path(command[0]), command=command)
    proc = bridge._proc
    errors: list[BaseException] = []

    def send_large_request() -> None:
        try:
            bridge.call_blocking(
                "large",
                {"payload": "x" * (8 * 1024 * 1024)},
                timeout=0.1,
            )
        except BaseException as exc:
            errors.append(exc)

    caller = threading.Thread(target=send_large_request)
    caller.start()
    try:
        _wait_for_blocked_writer(bridge)
        caller.join(timeout=1.0)
        assert not caller.is_alive()
        assert len(errors) == 1
        assert isinstance(errors[0], e2ee.BridgeError)
        assert "timed out" in str(errors[0])
        assert proc.poll() is None

        retry_started = time.monotonic()
        with pytest.raises(e2ee.BridgeError, match="recovering after an RPC timeout"):
            bridge.call_blocking("must-not-queue", timeout=0.5)
        assert time.monotonic() - retry_started < 0.1

        started = time.monotonic()
        bridge.close()
        assert time.monotonic() - started < 2.0
        assert proc.poll() is not None
    finally:
        bridge.close()
        caller.join(timeout=1.0)


def test_cancelled_queued_write_taints_generation_and_fails_later_queue(
    tmp_path: Path,
) -> None:
    methods = tmp_path / "methods.txt"
    command = _write_bridge_script(
        tmp_path,
        f"""
        import json
        import pathlib
        import sys
        import time

        methods = pathlib.Path({str(methods)!r})
        time.sleep(0.5)
        for raw in sys.stdin:
            request = json.loads(raw)
            method = request.get("method")
            with methods.open("a", encoding="utf-8") as handle:
                print(method, file=handle)
            print(json.dumps({{
                "id": request["id"], "ok": True, "data": {{"method": method}}
            }}), flush=True)
        """,
    )
    bridge = e2ee._BridgeProcess(Path(command[0]), command=command)
    first_results: list[dict[str, Any]] = []
    first_errors: list[BaseException] = []
    second_errors: list[BaseException] = []
    third_errors: list[BaseException] = []

    def send_first() -> None:
        try:
            first_results.append(
                bridge.call_blocking(
                    "first",
                    {"payload": "x" * (8 * 1024 * 1024)},
                    timeout=2.0,
                )
            )
        except BaseException as exc:
            first_errors.append(exc)

    def send_second() -> None:
        try:
            bridge.call_blocking("second", timeout=0.15)
        except BaseException as exc:
            second_errors.append(exc)

    def send_third() -> None:
        try:
            bridge.call_blocking("third", timeout=1.0)
        except BaseException as exc:
            third_errors.append(exc)

    first = threading.Thread(target=send_first)
    second = threading.Thread(target=send_second)
    third = threading.Thread(target=send_third)
    first.start()
    try:
        _wait_for_blocked_writer(bridge)
        second.start()
        deadline = time.monotonic() + 1.0
        while bridge._writer_queue.qsize() < 1 and time.monotonic() < deadline:
            time.sleep(0.005)
        assert bridge._writer_queue.qsize() >= 1

        third.start()
        deadline = time.monotonic() + 1.0
        while bridge._writer_queue.qsize() < 2 and time.monotonic() < deadline:
            time.sleep(0.005)
        assert bridge._writer_queue.qsize() >= 2

        second.join(timeout=1.0)
        assert not second.is_alive()
        assert len(second_errors) == 1
        assert isinstance(second_errors[0], e2ee.BridgeError)
        assert "timed out" in str(second_errors[0])

        first.join(timeout=2.0)
        third.join(timeout=2.0)
        assert not first.is_alive()
        assert not third.is_alive()
        assert first_errors == []
        assert first_results == [{"method": "first"}]
        assert len(third_errors) == 1
        assert isinstance(third_errors[0], e2ee.BridgeError)
        assert "cancelled before bridge write" in str(third_errors[0])
        time.sleep(0.1)
        assert methods.read_text(encoding="utf-8").splitlines() == ["first"]
    finally:
        bridge.close()
        first.join(timeout=2.0)
        if second.ident is not None:
            second.join(timeout=2.0)
        if third.ident is not None:
            third.join(timeout=2.0)


def test_response_timeout_rejects_same_generation_calls_before_watchdog(
    tmp_path: Path,
) -> None:
    methods = tmp_path / "methods.txt"
    command = _write_bridge_script(
        tmp_path,
        f"""
        import json
        import pathlib
        import sys

        methods = pathlib.Path({str(methods)!r})
        for raw in sys.stdin:
            request = json.loads(raw)
            method = request.get("method")
            with methods.open("a", encoding="utf-8") as handle:
                print(method, file=handle)
            if method == "first":
                continue
            print(json.dumps({{
                "id": request["id"], "ok": True, "data": {{"method": method}}
            }}), flush=True)
        """,
    )
    bridge = e2ee._BridgeProcess(Path(command[0]), command=command)
    try:
        with pytest.raises(e2ee.BridgeError, match="timed out"):
            bridge.call_blocking("first", timeout=0.05)

        started = time.monotonic()
        with pytest.raises(e2ee.BridgeError, match="recovering after an RPC timeout"):
            bridge.call_blocking("second", timeout=0.5)
        assert time.monotonic() - started < 0.1
        time.sleep(0.1)
        assert methods.read_text(encoding="utf-8").splitlines() == ["first"]
    finally:
        bridge.close()


def test_watchdog_recovers_after_blocked_pipe_write_timeout(tmp_path: Path) -> None:
    launches = tmp_path / "launches.txt"
    command = _write_bridge_script(
        tmp_path,
        f"""
        import json
        import pathlib
        import sys
        import time

        launches = pathlib.Path({str(launches)!r})
        previous = launches.read_text(encoding="utf-8").splitlines() if launches.exists() else []
        generation = len(previous) + 1
        with launches.open("a", encoding="utf-8") as handle:
            print(generation, file=handle)
        if generation == 1:
            while True:
                time.sleep(1)
        hello = {{
            "protocolVersion": 1,
            "bridgeVersion": "2.3.2",
            "capabilities": [
                "newClient", "connect", "connectE2EE", "isConnected", "events"
            ],
        }}
        for raw in sys.stdin:
            request = json.loads(raw)
            method = request.get("method")
            data = hello if method == "hello" else {{
                "connected": False, "e2eeConnected": False
            }} if method == "isConnected" else {{}}
            print(json.dumps({{"id": request["id"], "ok": True, "data": data}}), flush=True)
        """,
    )
    bridge = e2ee._BridgeProcess(Path(command[0]), command=command)
    first_proc = bridge._proc
    bridge.HEALTH_INTERVAL = 0.01
    bridge.HEALTH_RPC_TIMEOUT = 0.5
    bridge.BASE_BACKOFF = 0.01
    errors: list[BaseException] = []

    def send_large_request() -> None:
        try:
            bridge.call_blocking(
                "large",
                {"payload": "x" * (8 * 1024 * 1024)},
                timeout=0.1,
            )
        except BaseException as exc:
            errors.append(exc)

    caller = threading.Thread(target=send_large_request)
    caller.start()
    try:
        _wait_for_blocked_writer(bridge)
        bridge.start_watchdog(enable_e2ee=False)
        caller.join(timeout=1.0)
        assert not caller.is_alive()
        assert len(errors) == 1
        assert isinstance(errors[0], e2ee.BridgeError)

        state = _wait_for_event(bridge.events, e2ee._BRIDGE_STATE_EVENT)
        while not isinstance(state.get("data", {}).get("generation"), int):
            state = _wait_for_event(bridge.events, e2ee._BRIDGE_STATE_EVENT)
        assert first_proc.poll() is not None
        assert bridge._proc is not first_proc
        assert bridge._validate_contract()["bridgeVersion"] == "2.3.2"
    finally:
        bridge.close()
        caller.join(timeout=1.0)


def test_watchdog_kills_each_failed_replay_before_retry(tmp_path: Path) -> None:
    launches = tmp_path / "launches.txt"
    command = _write_bridge_script(
        tmp_path,
        f"""
        import json
        import os
        import pathlib
        import sys

        state = pathlib.Path({str(launches)!r})
        previous = state.read_text(encoding="utf-8").splitlines() if state.exists() else []
        with state.open("a", encoding="utf-8") as handle:
            print("launch", file=handle)
        count = len(previous) + 1
        hello = {{
            "protocolVersion": 1,
            "bridgeVersion": "2.3.2",
            "capabilities": [
                "newClient", "connect", "connectE2EE", "isConnected", "events"
            ],
        }}
        for raw in sys.stdin:
            request = json.loads(raw)
            method = request.get("method")
            if method == "crash":
                os._exit(12)
            if count > 1 and method == "newClient":
                print(json.dumps({{
                    "id": request["id"], "ok": False, "error": "replay rejected"
                }}), flush=True)
                continue
            data = hello if method == "hello" else {{
                "connected": True, "e2eeConnected": False
            }} if method == "isConnected" else {{}}
            print(json.dumps({{"id": request["id"], "ok": True, "data": data}}), flush=True)
        """,
    )
    bridge = e2ee._BridgeProcess(Path(command[0]), command=command)
    bridge.HEALTH_INTERVAL = 0.01
    bridge.HEALTH_RPC_TIMEOUT = 0.5
    bridge.BASE_BACKOFF = 0.01
    bridge.MAX_RETRIES = 2
    try:
        bridge.start_watchdog(
            connect_cfg={"cookies": {"c_user": "test"}}, enable_e2ee=False
        )
        with pytest.raises(e2ee.BridgeError):
            bridge.call_blocking("crash", timeout=0.5)

        fatal = _wait_for_event(bridge.events, "bridge_fatal")
        assert fatal["retries"] == 2
        assert len(launches.read_text(encoding="utf-8").splitlines()) == 3
        assert bridge._proc.poll() is not None
    finally:
        bridge.close()


def test_successful_short_lived_respawns_still_exhaust_retry_budget(
    tmp_path: Path,
) -> None:
    launches = tmp_path / "launches.txt"
    command = _write_bridge_script(
        tmp_path,
        f"""
        import json
        import os
        import pathlib
        import sys
        import threading

        state = pathlib.Path({str(launches)!r})
        with state.open("a", encoding="utf-8") as handle:
            print("launch", file=handle)
        threading.Timer(0.25, lambda: os._exit(17)).start()
        hello = {{
            "protocolVersion": 1,
            "bridgeVersion": "2.3.2",
            "capabilities": [
                "newClient", "connect", "connectE2EE", "isConnected", "events"
            ],
        }}
        for raw in sys.stdin:
            request = json.loads(raw)
            method = request.get("method")
            data = hello if method == "hello" else {{
                "connected": True, "e2eeConnected": False
            }} if method == "isConnected" else {{}}
            print(json.dumps({{"id": request["id"], "ok": True, "data": data}}), flush=True)
        """,
    )
    bridge = e2ee._BridgeProcess(Path(command[0]), command=command)
    bridge.HEALTH_INTERVAL = 0.01
    bridge.HEALTH_RPC_TIMEOUT = 0.5
    bridge.CONNECTION_POLL_INTERVAL = 0.01
    bridge.BASE_BACKOFF = 0.01
    bridge.MAX_RETRIES = 2
    bridge.STABLE_UPTIME = 5.0
    try:
        bridge.start_watchdog(
            connect_cfg={"cookies": {"c_user": "test"}}, enable_e2ee=False
        )
        fatal = _wait_for_event(bridge.events, "bridge_fatal")
        assert fatal["retries"] == 2
        assert len(launches.read_text(encoding="utf-8").splitlines()) == 3
    finally:
        bridge.close()


def test_close_during_backoff_prevents_respawn(tmp_path: Path) -> None:
    launches = tmp_path / "launches.txt"
    command = _write_bridge_script(
        tmp_path,
        f"""
        import os
        import pathlib
        import threading
        import time

        state = pathlib.Path({str(launches)!r})
        with state.open("a", encoding="utf-8") as handle:
            print("launch", file=handle)
        threading.Timer(0.05, lambda: os._exit(19)).start()
        while True:
            time.sleep(1)
        """,
    )
    bridge = e2ee._BridgeProcess(Path(command[0]), command=command)
    bridge.HEALTH_INTERVAL = 0.01
    bridge.BASE_BACKOFF = 0.25
    watchdog = bridge.start_watchdog(enable_e2ee=False)

    deadline = time.monotonic() + 2.0
    while bridge._proc.poll() is None and time.monotonic() < deadline:
        time.sleep(0.01)
    assert bridge._proc.poll() is not None

    bridge.close()
    time.sleep(0.3)
    assert len(launches.read_text(encoding="utf-8").splitlines()) == 1
    assert not watchdog.is_alive()


def test_recovery_gates_external_rpc_and_timeout_covers_gate_wait(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    launches = tmp_path / "launches.txt"
    methods = tmp_path / "methods.txt"
    command = _write_bridge_script(
        tmp_path,
        f"""
        import json
        import os
        import pathlib
        import sys

        launches = pathlib.Path({str(launches)!r})
        previous = launches.read_text(encoding="utf-8").splitlines() if launches.exists() else []
        generation = len(previous) + 1
        with launches.open("a", encoding="utf-8") as handle:
            print(generation, file=handle)
        methods = pathlib.Path({str(methods)!r})
        hello = {{
            "protocolVersion": 1,
            "bridgeVersion": "2.3.2",
            "capabilities": [
                "newClient", "connect", "connectE2EE", "isConnected", "events"
            ],
        }}
        for raw in sys.stdin:
            request = json.loads(raw)
            method = request.get("method")
            with methods.open("a", encoding="utf-8") as handle:
                print(f"{{generation}}:{{method}}", file=handle)
            if generation == 1 and method == "crash":
                os._exit(12)
            if method == "hello":
                data = hello
            elif method == "isConnected":
                data = {{"connected": True, "e2eeConnected": False}}
            elif method == "external":
                data = {{"external": True}}
            else:
                data = {{}}
            print(json.dumps({{"id": request["id"], "ok": True, "data": data}}), flush=True)
        """,
    )
    bridge = e2ee._BridgeProcess(Path(command[0]), command=command)
    bridge.HEALTH_INTERVAL = 0.01
    bridge.HEALTH_RPC_TIMEOUT = 0.5
    bridge.CONNECTION_POLL_INTERVAL = 0.01
    bridge.BASE_BACKOFF = 0.01
    connect_cfg = {"cookies": {"c_user": "test"}}
    recovery_spawned = threading.Event()
    allow_replay = threading.Event()
    original_spawn = bridge._spawn

    def pause_after_spawn() -> int:
        generation = original_spawn()
        if generation > 1:
            recovery_spawned.set()
            if not allow_replay.wait(2.0):
                raise RuntimeError("test did not release bridge replay")
        return generation

    monkeypatch.setattr(bridge, "_spawn", pause_after_spawn)
    rpc_results: list[dict[str, Any]] = []
    rpc_errors: list[BaseException] = []

    def call_external() -> None:
        try:
            rpc_results.append(bridge.call_blocking("external", timeout=1.0))
        except BaseException as exc:
            rpc_errors.append(exc)

    caller = threading.Thread(target=call_external)
    try:
        bridge.connect_client(connect_cfg, enable_e2ee=False)
        bridge.start_watchdog(connect_cfg=connect_cfg, enable_e2ee=False)
        with pytest.raises(e2ee.BridgeError):
            bridge.call_blocking("crash", timeout=0.5)
        assert recovery_spawned.wait(2.0)

        started = time.monotonic()
        with pytest.raises(e2ee.BridgeError, match="bridge availability"):
            bridge.call_blocking("tooEarly", timeout=0.05)
        assert time.monotonic() - started < 0.5

        caller.start()
        time.sleep(0.1)
        assert caller.is_alive()
        generation_two = methods.read_text(encoding="utf-8").splitlines()
        assert "2:tooEarly" not in generation_two
        assert "2:external" not in generation_two

        allow_replay.set()
        caller.join(timeout=2.0)
        assert not caller.is_alive()
        assert rpc_errors == []
        assert rpc_results == [{"external": True}]

        generation_two = [
            line.removeprefix("2:")
            for line in methods.read_text(encoding="utf-8").splitlines()
            if line.startswith("2:")
        ]
        expected_order = ["hello", "newClient", "connect", "isConnected", "external"]
        positions = [generation_two.index(method) for method in expected_order]
        assert positions == sorted(positions)
    finally:
        allow_replay.set()
        bridge.close()
        if caller.ident is not None:
            caller.join(timeout=2.0)


class _StartupListener:
    def __init__(
        self,
        readiness_error: BaseException | None = None,
        *,
        ready: bool = False,
    ) -> None:
        self.readiness_error = readiness_error
        self.ready = ready
        self.stopped = False
        self.stop_calls = 0

    def on_message(self, callback: Any) -> None:
        self.callback = callback

    async def connect_mqtt(self) -> None:
        while not self.stopped:
            await asyncio.sleep(0)

    def wait_until_connected(self, timeout: float, *, require_e2ee: bool) -> bool:
        assert timeout == sample_main.DEFAULT_E2EE_READY_TIMEOUT
        assert require_e2ee is True
        if self.readiness_error is not None:
            raise self.readiness_error
        return self.ready

    def stop(self) -> None:
        self.stop_calls += 1
        self.stopped = True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "readiness_error",
    [None, RuntimeError("handshake failed")],
    ids=["timeout", "handshake-error"],
)
async def test_bot_cleans_up_listener_when_startup_is_not_ready(
    monkeypatch: pytest.MonkeyPatch,
    mock_dataFB: dict[str, Any],
    readiness_error: BaseException | None,
) -> None:
    listener = _StartupListener(readiness_error)
    monkeypatch.setattr(
        sample_main, "listeningE2EEEvent", lambda data, **options: listener
    )
    bot = sample_main.SimpleBot(mock_dataFB)

    with pytest.raises(RuntimeError):
        await bot.run()

    assert listener.stopped is True
    assert listener.stop_calls == 1
    assert not [
        task
        for task in asyncio.all_tasks()
        if task is not asyncio.current_task()
        and task.get_name() == "fbchat-e2ee-listener"
    ]


@pytest.mark.asyncio
async def test_bot_cancellation_propagates_after_listener_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    mock_dataFB: dict[str, Any],
) -> None:
    listener = _StartupListener(ready=True)
    monkeypatch.setattr(
        sample_main, "listeningE2EEEvent", lambda data, **options: listener
    )
    bot = sample_main.SimpleBot(mock_dataFB)
    task = asyncio.create_task(bot.run())
    for _ in range(100):
        if hasattr(listener, "callback"):
            break
        await asyncio.sleep(0)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert listener.stopped is True
    assert listener.stop_calls == 1


def test_listener_fails_closed_and_reaps_bridge_on_e2ee_startup_error(
    monkeypatch: pytest.MonkeyPatch,
    mock_dataFB: dict[str, Any],
    tmp_path: Path,
) -> None:
    binary = tmp_path / "bridge"
    binary.write_bytes(b"placeholder")

    class FailingBridge:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.closed = False

        def connect_client(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            raise e2ee.BridgeError("E2EE handshake rejected")

        def close(self) -> None:
            self.closed = True

    created: list[FailingBridge] = []

    def create_bridge(*args: Any, **kwargs: Any) -> FailingBridge:
        bridge = FailingBridge()
        created.append(bridge)
        return bridge

    monkeypatch.setattr(e2ee, "_resolve_binary", lambda: binary)
    monkeypatch.setattr(e2ee, "_BridgeProcess", create_bridge)
    listener = e2ee.listeningE2EEEvent(mock_dataFB)

    with pytest.raises(e2ee.BridgeError, match="handshake rejected"):
        listener.connect_mqtt_blocking()

    assert created and created[0].closed is True
    assert listener._startup_done.is_set()
    assert not listener._connected.is_set()
    assert not listener._e2ee_connected.is_set()
    with pytest.raises(RuntimeError, match="failed to start"):
        listener.wait_until_connected(0.1, require_e2ee=True)


def test_listener_is_single_use_across_concurrent_start_and_restart(
    monkeypatch: pytest.MonkeyPatch,
    mock_dataFB: dict[str, Any],
    tmp_path: Path,
) -> None:
    binary = tmp_path / "bridge"
    binary.write_bytes(b"placeholder")
    connect_started = threading.Event()
    allow_connect = threading.Event()

    class BlockingBridge:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.events: Queue[dict[str, Any]] = Queue()
            self.closed = False

        def connect_client(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            connect_started.set()
            if not allow_connect.wait(2.0):
                raise RuntimeError("test did not release listener startup")
            return {"user": {"name": "Test", "id": "1"}}

        def start_watchdog(self, *args: Any, **kwargs: Any) -> None:
            return None

        def close(self) -> None:
            self.closed = True

    created: list[BlockingBridge] = []

    def create_bridge(*args: Any, **kwargs: Any) -> BlockingBridge:
        bridge = BlockingBridge()
        created.append(bridge)
        return bridge

    monkeypatch.setattr(e2ee, "_resolve_binary", lambda: binary)
    monkeypatch.setattr(e2ee, "_BridgeProcess", create_bridge)
    listener = e2ee.listeningE2EEEvent(mock_dataFB, enable_e2ee=False)
    run_errors: list[BaseException] = []

    def run_listener() -> None:
        try:
            listener.connect_mqtt_blocking()
        except BaseException as exc:
            run_errors.append(exc)

    thread = threading.Thread(target=run_listener)
    thread.start()
    try:
        assert connect_started.wait(2.0)
        with pytest.raises(RuntimeError, match="single-use"):
            listener.connect_mqtt_blocking()

        allow_connect.set()
        assert listener._startup_done.wait(2.0)
        listener.stop()
        thread.join(timeout=2.0)
        assert not thread.is_alive()
        assert run_errors == []
        assert len(created) == 1
        assert created[0].closed is True

        with pytest.raises(RuntimeError, match="single-use"):
            listener.connect_mqtt_blocking()
    finally:
        allow_connect.set()
        listener.stop()
        thread.join(timeout=2.0)


def test_listener_never_publishes_ready_if_stopped_during_watchdog_start(
    monkeypatch: pytest.MonkeyPatch,
    mock_dataFB: dict[str, Any],
    tmp_path: Path,
) -> None:
    binary = tmp_path / "bridge"
    binary.write_bytes(b"placeholder")
    watchdog_started = threading.Event()
    allow_watchdog = threading.Event()

    class BlockingWatchdogBridge:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.events: Queue[dict[str, Any]] = Queue()
            self.closed = False

        def connect_client(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            return {"user": {"name": "Test", "id": "1"}}

        def start_watchdog(self, *args: Any, **kwargs: Any) -> None:
            watchdog_started.set()
            if not allow_watchdog.wait(2.0):
                raise RuntimeError("test did not release watchdog startup")

        def close(self) -> None:
            self.closed = True

    bridge = BlockingWatchdogBridge()
    monkeypatch.setattr(e2ee, "_resolve_binary", lambda: binary)
    monkeypatch.setattr(e2ee, "_BridgeProcess", lambda *args, **kwargs: bridge)
    listener = e2ee.listeningE2EEEvent(mock_dataFB, enable_e2ee=False)
    run_errors: list[BaseException] = []

    def run_listener() -> None:
        try:
            listener.connect_mqtt_blocking()
        except BaseException as exc:
            run_errors.append(exc)

    thread = threading.Thread(target=run_listener)
    thread.start()
    try:
        assert watchdog_started.wait(2.0)
        assert not listener._connected.is_set()
        assert not listener._startup_done.is_set()

        listener.stop()
        assert listener.wait_until_connected(0.1) is False
        allow_watchdog.set()
        thread.join(timeout=2.0)
        assert not thread.is_alive()
        assert len(run_errors) == 1
        assert isinstance(run_errors[0], e2ee.BridgeError)
        assert bridge.closed is True
        assert not listener._connected.is_set()
        assert not listener._e2ee_connected.is_set()
    finally:
        allow_watchdog.set()
        listener.stop()
        thread.join(timeout=2.0)


def test_listener_state_flags_follow_bridge_events(mock_dataFB: dict[str, Any]) -> None:
    class FakeBridge:
        def __init__(self) -> None:
            self.events: Queue[dict[str, Any]] = Queue()
            self.closed = False

        def close(self) -> None:
            self.closed = True

    bridge = FakeBridge()
    for event in (
        {"type": "ready", "data": {}},
        {"type": "e2eeConnected", "data": {}},
        {"type": "disconnected", "data": {"isE2EE": True}},
        {"type": "bridge_fatal", "error": "test"},
    ):
        bridge.events.put(event)

    listener = e2ee.listeningE2EEEvent(mock_dataFB)
    listener._bridge = bridge  # type: ignore[assignment]
    snapshots: list[tuple[str, bool, bool]] = []
    listener.on_message(
        lambda event: snapshots.append(
            (
                str(event["type"]),
                listener._connected.is_set(),
                listener._e2ee_connected.is_set(),
            )
        )
    )

    with pytest.raises(e2ee.BridgeError, match="retry budget"):
        listener._poll_loop(bridge)  # type: ignore[arg-type]

    assert snapshots == [
        ("ready", True, False),
        ("e2eeConnected", True, True),
        ("disconnected", True, False),
    ]
    assert bridge.closed is True
    assert not listener._connected.is_set()
    assert not listener._e2ee_connected.is_set()
