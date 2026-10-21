from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import Callable
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from _features._thread import _all_thread_data
from _messaging import _listening as mqtt_module
from _messaging._listening import listeningEvent
from _messaging._reconnect import ConnectionFailure, ReconnectPolicy


class _VirtualStopEvent:
    """Only policy waits are virtual; no socket or real clock is involved."""

    def __init__(self) -> None:
        self._event = threading.Event()
        self.waits: list[float] = []

    def set(self) -> None:
        self._event.set()

    def clear(self) -> None:
        self._event.clear()

    def is_set(self) -> bool:
        return self._event.is_set()

    def wait(self, timeout: float | None = None) -> bool:
        assert timeout is not None and timeout >= 0
        self.waits.append(timeout)
        return self.is_set()


class _SignallingStopEvent(threading.Event):
    def __init__(self) -> None:
        super().__init__()
        self.waiting = threading.Event()

    def wait(self, timeout: float | None = None) -> bool:
        self.waiting.set()
        return super().wait(timeout)


@pytest.fixture
def listener(monkeypatch: pytest.MonkeyPatch) -> listeningEvent:
    def forbid_graphql(*args: object, **kwargs: object) -> None:
        pytest.fail("An offline MQTT test attempted to refresh data through GraphQL")

    monkeypatch.setattr(_all_thread_data, "func_blocking", forbid_graphql)
    instance = listeningEvent(
        {"FacebookID": "offline-bot", "cookieFacebook": "synthetic-offline-cookie"},
        reconnect_policy=ReconnectPolicy(jitter=0.0),
    )
    instance.syncToken = "synthetic-sync-token"
    instance.lastSeqID = 42
    return instance


def _client(
    listener: listeningEvent,
    *,
    connect_error: BaseException | None = None,
    on_loop: Callable[[], object] | None = None,
    connection_code: int = 0,
) -> Mock:
    client = Mock()
    client.connect.side_effect = connect_error

    def loop(*args: object, **kwargs: object) -> int:
        listener._on_connect(client, None, {}, connection_code)
        if on_loop is not None:
            on_loop()
        return 0

    client.loop_forever.side_effect = loop
    return client


def _mock_clients(
    monkeypatch: pytest.MonkeyPatch,
    listener: listeningEvent,
    clients: list[Mock],
) -> Mock:
    factory = Mock(side_effect=clients)
    monkeypatch.setattr(listener, "_build_client", factory)
    return factory


def _run_thread(
    listener: listeningEvent,
) -> tuple[threading.Thread, list[BaseException]]:
    errors: list[BaseException] = []

    def run() -> None:
        try:
            listener.connect_mqtt_blocking()
        except BaseException as error:
            errors.append(error)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread, errors


def _mqtt_message(payload: dict[str, object]) -> SimpleNamespace:
    return SimpleNamespace(payload=json.dumps(payload).encode("utf-8"))


def _message_delta(message_id: str | None, body: str = "offline message") -> dict:
    return {
        "body": body,
        "messageMetadata": {
            "messageId": message_id,
            "threadKey": {"threadFbId": "offline-thread"},
            "actorFbId": "offline-peer",
            "timestamp": 1,
        },
    }


def test_mqtt_retries_initial_connect_error_then_publishes_ready(
    monkeypatch: pytest.MonkeyPatch, listener: listeningEvent
) -> None:
    virtual_stop = _VirtualStopEvent()
    monkeypatch.setattr(listener, "_stop_event", virtual_stop)
    snapshots: list[dict[str, object]] = []
    listener.set_connection_state_callback(snapshots.append)
    first = _client(listener, connect_error=OSError("synthetic outage"))
    second = _client(listener, on_loop=listener.disconnect_blocking)
    factory = _mock_clients(monkeypatch, listener, [first, second])

    listener.connect_mqtt_blocking()

    assert factory.call_count == 2
    first.loop_forever.assert_not_called()
    second.loop_forever.assert_called_once()
    assert virtual_stop.waits == [1.0]
    assert "reconnecting" in [snapshot["state"] for snapshot in snapshots]
    assert "connected" in [snapshot["state"] for snapshot in snapshots]
    assert listener.connection_state == "stopped"
    assert listener.syncToken == "synthetic-sync-token"
    assert listener.lastSeqID == 42


def test_mqtt_default_policy_survives_more_than_five_failed_reconnects(
    monkeypatch: pytest.MonkeyPatch, listener: listeningEvent
) -> None:
    virtual_stop = _VirtualStopEvent()
    monkeypatch.setattr(listener, "_stop_event", virtual_stop)
    clients = [
        _client(listener, connect_error=OSError("synthetic outage")) for _ in range(9)
    ]
    clients.append(_client(listener, on_loop=listener.disconnect_blocking))
    factory = _mock_clients(monkeypatch, listener, clients)

    listener.connect_mqtt_blocking()

    assert factory.call_count == 10
    assert virtual_stop.waits == pytest.approx(
        [1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 60.0, 60.0, 60.0]
    )
    assert all(client.disconnect.called for client in clients)


def test_mqtt_running_transport_failure_uses_the_same_retry_owner(
    monkeypatch: pytest.MonkeyPatch, listener: listeningEvent
) -> None:
    virtual_stop = _VirtualStopEvent()
    monkeypatch.setattr(listener, "_stop_event", virtual_stop)

    def interrupted_loop() -> None:
        raise OSError("synthetic established socket failure")

    first = _client(listener, on_loop=interrupted_loop)
    second = _client(listener, on_loop=listener.disconnect_blocking)
    factory = _mock_clients(monkeypatch, listener, [first, second])

    listener.connect_mqtt_blocking()

    assert factory.call_count == 2
    assert virtual_stop.waits == [1.0]
    assert first.disconnect.called
    topics = [call.args[0] for call in second.publish.call_args_list]
    assert topics == ["/messenger_sync_get_diffs"]
    resume_payload = json.loads(second.publish.call_args.args[1])
    assert resume_payload["sync_token"] == "synthetic-sync-token"
    assert resume_payload["last_seq_id"] == 42


@pytest.mark.parametrize("connection_code", [4, 5])
def test_mqtt_auth_rejection_does_not_retry(
    monkeypatch: pytest.MonkeyPatch,
    listener: listeningEvent,
    connection_code: int,
) -> None:
    virtual_stop = _VirtualStopEvent()
    monkeypatch.setattr(listener, "_stop_event", virtual_stop)
    client = _client(listener, connection_code=connection_code)
    factory = _mock_clients(monkeypatch, listener, [client])

    with pytest.raises(RuntimeError):
        listener.connect_mqtt_blocking()

    assert factory.call_count == 1
    assert virtual_stop.waits == []
    assert listener.connection_state == "auth_required"
    assert client.disconnect.called


def test_mqtt_stop_interrupts_a_long_retry_wait(
    monkeypatch: pytest.MonkeyPatch, listener: listeningEvent
) -> None:
    stop_event = _SignallingStopEvent()
    monkeypatch.setattr(listener, "_stop_event", stop_event)
    client = _client(listener, connect_error=OSError("synthetic outage"))
    factory = _mock_clients(monkeypatch, listener, [client])
    listener.reconnect_policy = ReconnectPolicy(initial_delay=60, max_delay=60)
    thread, errors = _run_thread(listener)
    try:
        assert stop_event.waiting.wait(2.0)
        listener.disconnect_blocking()
        thread.join(timeout=2.0)

        assert not thread.is_alive()
        assert errors == []
        assert factory.call_count == 1
        assert listener.connection_state == "stopped"
    finally:
        listener.disconnect_blocking()
        thread.join(timeout=2.0)


@pytest.mark.asyncio
async def test_mqtt_cancellation_joins_worker_and_prevents_further_retries(
    monkeypatch: pytest.MonkeyPatch, listener: listeningEvent
) -> None:
    stop_event = _SignallingStopEvent()
    monkeypatch.setattr(listener, "_stop_event", stop_event)
    worker_done = threading.Event()
    original_connect = listener._run_listener
    client = _client(listener, connect_error=OSError("synthetic outage"))

    def tracked_connect(
        cancelled: threading.Event | None = None,
        claimed: threading.Event | None = None,
    ) -> None:
        try:
            original_connect(cancelled, claimed)
        finally:
            worker_done.set()

    factory = _mock_clients(monkeypatch, listener, [client])
    monkeypatch.setattr(listener, "_run_listener", tracked_connect)
    task = asyncio.create_task(listener.connect_mqtt())
    try:
        assert await asyncio.to_thread(stop_event.waiting.wait, 2.0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=2.0)

        assert worker_done.is_set()
        assert factory.call_count == 1
        assert listener.connection_state == "stopped"
    finally:
        listener.disconnect_blocking()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


def test_mqtt_concurrent_starts_have_only_one_worker(
    monkeypatch: pytest.MonkeyPatch, listener: listeningEvent
) -> None:
    entered_loop = threading.Event()
    release_loop = threading.Event()

    def blocking_loop() -> None:
        entered_loop.set()
        if not release_loop.wait(2.0):
            raise AssertionError("Offline test did not release MQTT loop")
        listener.disconnect_blocking()

    client = _client(listener, on_loop=blocking_loop)
    factory = _mock_clients(monkeypatch, listener, [client])
    thread, errors = _run_thread(listener)
    try:
        assert entered_loop.wait(2.0)
        with pytest.raises(RuntimeError, match="running|single|started"):
            listener.connect_mqtt_blocking()
        assert factory.call_count == 1
    finally:
        release_loop.set()
        listener.disconnect_blocking()
        thread.join(timeout=2.0)

    assert not thread.is_alive()
    assert errors == []


def test_mqtt_client_disables_paho_internal_retry(
    monkeypatch: pytest.MonkeyPatch, listener: listeningEvent
) -> None:
    factory = Mock(return_value=Mock())
    monkeypatch.setattr(mqtt_module.mqtt, "Client", factory)

    listener._build_client()

    assert factory.call_args.kwargs["reconnect_on_failure"] is False


def test_mqtt_client_legacy_paho_fallback_keeps_only_one_retry_owner(
    monkeypatch: pytest.MonkeyPatch, listener: listeningEvent
) -> None:
    client = Mock()
    factory = Mock(side_effect=[TypeError("legacy constructor"), client])
    monkeypatch.setattr(mqtt_module.mqtt, "Client", factory)

    assert listener._build_client() is client

    assert factory.call_count == 2
    assert client._reconnect_on_failure is False
    assert client._connect_timeout <= 5.0


@pytest.mark.parametrize(
    ("policy", "expected_attempts", "reason"),
    [
        (ReconnectPolicy(enabled=False), 1, "retry_disabled"),
        (ReconnectPolicy(max_attempts=2, jitter=0), 3, "retry_exhausted"),
    ],
)
def test_mqtt_optional_retry_budget_is_enforced_after_initial_attempt(
    monkeypatch: pytest.MonkeyPatch,
    listener: listeningEvent,
    policy: ReconnectPolicy,
    expected_attempts: int,
    reason: str,
) -> None:
    virtual_stop = _VirtualStopEvent()
    monkeypatch.setattr(listener, "_stop_event", virtual_stop)
    listener.reconnect_policy = policy
    clients = [
        _client(listener, connect_error=OSError("PRIVATE_CONNECTION_DETAIL"))
        for _ in range(expected_attempts)
    ]
    factory = _mock_clients(monkeypatch, listener, clients)

    with pytest.raises(ConnectionFailure) as failure:
        listener.connect_mqtt_blocking()

    assert failure.value.reason == reason
    assert "PRIVATE" not in str(failure.value)
    assert factory.call_count == expected_attempts
    assert len(virtual_stop.waits) == expected_attempts - 1
    assert listener.connection_state == "fatal"
    assert listener.connection_status["reason"] == reason


@pytest.mark.parametrize("stable_duration", [59.0, 60.0])
def test_mqtt_retry_budget_resets_only_after_a_stable_connection(
    monkeypatch: pytest.MonkeyPatch,
    listener: listeningEvent,
    stable_duration: float,
) -> None:
    now = [0.0]
    virtual_stop = _VirtualStopEvent()
    monkeypatch.setattr(listener, "_stop_event", virtual_stop)
    monkeypatch.setattr(mqtt_module.time, "monotonic", lambda: now[0])
    listener.reconnect_policy = ReconnectPolicy(max_attempts=1, jitter=0)

    def disconnect_after_duration() -> None:
        now[0] = stable_duration
        raise OSError("synthetic runtime outage")

    first = _client(listener, connect_error=OSError("synthetic startup outage"))
    second = _client(listener, on_loop=disconnect_after_duration)
    third = _client(listener, on_loop=listener.disconnect_blocking)
    factory = _mock_clients(monkeypatch, listener, [first, second, third])

    if stable_duration < 60.0:
        with pytest.raises(ConnectionFailure) as failure:
            listener.connect_mqtt_blocking()
        assert failure.value.reason == "retry_exhausted"
        assert factory.call_count == 2
        assert virtual_stop.waits == [1.0]
    else:
        listener.connect_mqtt_blocking()
        assert factory.call_count == 3
        assert virtual_stop.waits == [1.0, 1.0]
        assert listener.connection_state == "stopped"


def test_mqtt_nonzero_connect_return_retries_without_entering_the_network_loop(
    monkeypatch: pytest.MonkeyPatch, listener: listeningEvent
) -> None:
    virtual_stop = _VirtualStopEvent()
    monkeypatch.setattr(listener, "_stop_event", virtual_stop)
    first = _client(listener)
    first.connect.return_value = mqtt_module.mqtt.MQTT_ERR_CONN_LOST
    second = _client(listener, on_loop=listener.disconnect_blocking)
    factory = _mock_clients(monkeypatch, listener, [first, second])

    listener.connect_mqtt_blocking()

    assert factory.call_count == 2
    first.loop_forever.assert_not_called()
    assert virtual_stop.waits == [1.0]


def test_mqtt_replayed_message_is_not_delivered_twice(listener: listeningEvent) -> None:
    client = Mock()
    first = _mqtt_message(
        {"deltas": [_message_delta("offline-message-1")], "lastIssuedSeqId": 43}
    )
    duplicate = _mqtt_message(
        {
            "deltas": [_message_delta("offline-message-1", "replayed body")],
            "lastIssuedSeqId": 44,
        }
    )

    listener._on_message(client, None, first)
    listener._on_message(client, None, duplicate)

    assert listener.get_message_blocking()["body"] == "offline message"
    assert listener.messageQueue.empty()
    assert listener.lastSeqID == 44


def test_mqtt_messages_without_ids_are_not_accidentally_deduplicated(
    listener: listeningEvent,
) -> None:
    message = _mqtt_message({"deltas": [_message_delta(None)]})

    listener._on_message(Mock(), None, message)
    listener._on_message(Mock(), None, message)

    assert listener.messageQueue.qsize() == 2


def test_mqtt_replay_cache_is_bounded_and_expires_without_losing_new_messages(
    monkeypatch: pytest.MonkeyPatch, listener: listeningEvent
) -> None:
    now = [1.0]
    monkeypatch.setattr(mqtt_module, "_MESSAGE_DEDUPE_MAXSIZE", 3)
    monkeypatch.setattr(mqtt_module, "_MESSAGE_DEDUPE_TTL_SECONDS", 10.0)
    monkeypatch.setattr(mqtt_module.time, "monotonic", lambda: now[0])
    for index in range(5):
        listener._on_message(
            Mock(), None, _mqtt_message({"deltas": [_message_delta(f"mid-{index}")]})
        )

    assert len(listener._recent_messages) == 3
    assert listener.messageQueue.qsize() == 5
    listener._on_message(
        Mock(), None, _mqtt_message({"deltas": [_message_delta("mid-4")]})
    )
    assert listener.messageQueue.qsize() == 5

    now[0] = 11.0
    listener._on_message(
        Mock(), None, _mqtt_message({"deltas": [_message_delta("mid-4")]})
    )
    assert listener.messageQueue.qsize() == 6
    assert len(listener._recent_messages) == 1


def test_mqtt_replay_cache_does_not_merge_different_threads(
    listener: listeningEvent,
) -> None:
    first = _message_delta("same-mid")
    second = _message_delta("same-mid")
    second["messageMetadata"]["threadKey"]["threadFbId"] = "another-offline-thread"

    listener._on_message(Mock(), None, _mqtt_message({"deltas": [first, second]}))

    assert listener.messageQueue.qsize() == 2


@pytest.mark.parametrize("reason", ["auth_required", "configuration", "protocol"])
def test_mqtt_sequence_refresh_fatal_error_does_not_reuse_a_previous_sequence(
    monkeypatch: pytest.MonkeyPatch, listener: listeningEvent, reason: str
) -> None:
    def refresh(*args: object, **kwargs: object) -> None:
        raise ConnectionFailure(reason)

    monkeypatch.setattr(_all_thread_data, "func_blocking", refresh)
    listener.syncToken = None
    client = Mock()

    assert listener._publish_pending_queue(client) is False
    client.publish.assert_not_called()
    assert listener._fatal_reason == reason
    assert listener.lastSeqID == 42


def test_mqtt_unknown_queue_error_is_fatal_without_logging_provider_details(
    listener: listeningEvent, capsys: pytest.CaptureFixture[str]
) -> None:
    client = Mock()
    message = _mqtt_message({"errorCode": "UNKNOWN_SYNTHETIC_SECRET"})

    listener._on_message(client, None, message)

    assert listener._fatal_reason == "unknown"
    assert listener._reconnect_requested.is_set()
    client.disconnect.assert_called_once_with()
    assert "SYNTHETIC_SECRET" not in capsys.readouterr().out


@pytest.mark.asyncio
async def test_mqtt_cancel_before_thread_start_never_connects_after_cleanup(
    monkeypatch: pytest.MonkeyPatch, listener: listeningEvent
) -> None:
    queued = asyncio.Event()
    release = asyncio.Event()
    original_to_thread = asyncio.to_thread
    factory = _mock_clients(monkeypatch, listener, [])
    cancellation_flags: list[threading.Event] = []

    async def deferred_to_thread(function, *args, **kwargs):
        if function == listener._run_listener:
            cancellation_flags.append(args[0])
            queued.set()
            await release.wait()
        return await original_to_thread(function, *args, **kwargs)

    monkeypatch.setattr(mqtt_module.asyncio, "to_thread", deferred_to_thread)
    task = asyncio.create_task(listener.connect_mqtt())
    try:
        await asyncio.wait_for(queued.wait(), timeout=2.0)
        task.cancel()
        await asyncio.sleep(0)
        assert cancellation_flags[0].is_set()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=2.0)

        factory.assert_not_called()
        assert listener.connection_state == "stopped"
        assert not listener._run_lock.locked()
    finally:
        release.set()
        listener.disconnect_blocking()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_mqtt_cancelling_a_queued_second_start_does_not_stop_existing_owner(
    monkeypatch: pytest.MonkeyPatch, listener: listeningEvent
) -> None:
    entered_loop = threading.Event()
    release_loop = threading.Event()
    queued = asyncio.Event()
    release_worker = asyncio.Event()
    cancellation_flags: list[threading.Event] = []
    original_to_thread = asyncio.to_thread

    def keep_owner_running() -> None:
        entered_loop.set()
        if not release_loop.wait(5.0):
            raise AssertionError("Offline test did not release the MQTT owner")

    client = _client(listener, on_loop=keep_owner_running)
    factory = _mock_clients(monkeypatch, listener, [client])
    thread, errors = _run_thread(listener)

    async def deferred_to_thread(function, *args, **kwargs):
        if function == listener._run_listener:
            cancellation_flags.append(args[0])
            queued.set()
            await release_worker.wait()
        return await original_to_thread(function, *args, **kwargs)

    task: asyncio.Task[None] | None = None
    try:
        assert await asyncio.to_thread(entered_loop.wait, 2.0)
        monkeypatch.setattr(mqtt_module.asyncio, "to_thread", deferred_to_thread)
        task = asyncio.create_task(listener.connect_mqtt())
        await asyncio.wait_for(queued.wait(), timeout=2.0)
        task.cancel()
        await asyncio.sleep(0)
        assert cancellation_flags[0].is_set()
        release_worker.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=2.0)

        assert thread.is_alive()
        assert not listener._stop_event.is_set()
        assert listener.connection_state == "connected"
        assert factory.call_count == 1
        client.disconnect.assert_not_called()
    finally:
        release_worker.set()
        listener.disconnect_blocking()
        release_loop.set()
        thread.join(timeout=2.0)
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    assert not thread.is_alive()
    assert errors == []


@pytest.mark.asyncio
async def test_mqtt_repeated_cancellation_still_joins_worker_and_offloads_cleanup(
    monkeypatch: pytest.MonkeyPatch, listener: listeningEvent
) -> None:
    worker_started = threading.Event()
    worker_release = threading.Event()
    worker_done = threading.Event()
    cleanup_started = threading.Event()
    cleanup_release = threading.Event()
    cleanup_done = threading.Event()
    cleanup_threads: list[int] = []
    event_loop_thread = threading.get_ident()

    def controlled_worker(
        cancelled: threading.Event | None = None,
        claimed: threading.Event | None = None,
    ) -> None:
        assert claimed is not None
        claimed.set()
        worker_started.set()
        try:
            if not worker_release.wait(5.0):
                raise AssertionError("Offline test did not release the MQTT worker")
        finally:
            worker_done.set()

    def controlled_cleanup() -> None:
        cleanup_threads.append(threading.get_ident())
        cleanup_started.set()
        if not cleanup_release.wait(5.0):
            raise AssertionError("Offline test did not release MQTT cleanup")
        cleanup_done.set()
        worker_release.set()

    monkeypatch.setattr(listener, "_run_listener", controlled_worker)
    monkeypatch.setattr(listener, "disconnect_blocking", controlled_cleanup)
    task = asyncio.create_task(listener.connect_mqtt())
    try:
        assert await asyncio.to_thread(worker_started.wait, 2.0)
        task.cancel()
        assert await asyncio.to_thread(cleanup_started.wait, 2.0)
        task.cancel()
        await asyncio.sleep(0)

        assert not task.done()
        assert not cleanup_done.is_set()
        assert not worker_done.is_set()
        assert len(cleanup_threads) == 1
        assert cleanup_threads[0] != event_loop_thread

        cleanup_release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=2.0)

        assert cleanup_done.is_set()
        assert worker_done.is_set()
    finally:
        cleanup_release.set()
        worker_release.set()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
