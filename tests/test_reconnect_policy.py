from __future__ import annotations

import math
import ssl
from dataclasses import FrozenInstanceError

import httpx
import pytest
from paho.mqtt.client import WebsocketConnectionError

from _messaging._reconnect import (
    ConnectionFailure,
    ConnectionStateTracker,
    ReconnectPolicy,
    classify_connection_error,
)


def test_unclassified_websocket_handshake_rejection_is_not_a_network_retry() -> None:
    error = WebsocketConnectionError("WebSocket handshake error")
    assert classify_connection_error(error) == "unknown"


def test_policy_defaults_allow_long_outages_without_a_retry_budget() -> None:
    policy = ReconnectPolicy()

    assert policy.enabled is True
    assert policy.max_attempts is None
    assert policy.allows(1) is True
    assert policy.allows(100_000) is True
    assert policy.stable_reset_after == 60.0


def test_policy_is_immutable() -> None:
    policy = ReconnectPolicy()

    with pytest.raises(FrozenInstanceError):
        policy.max_attempts = 1  # type: ignore[misc]


def test_policy_backoff_is_one_based_and_caps_without_overflow() -> None:
    policy = ReconnectPolicy(
        initial_delay=2.0, max_delay=9.0, multiplier=2.0, jitter=0.0
    )

    assert [policy.delay(attempt) for attempt in range(1, 6)] == pytest.approx(
        [2.0, 4.0, 8.0, 9.0, 9.0]
    )
    assert policy.delay(10**20) == 9.0


def test_policy_jitter_never_escapes_delay_cap() -> None:
    policy = ReconnectPolicy(
        initial_delay=2.0, max_delay=5.0, multiplier=2.0, jitter=0.2
    )

    first_delays = [policy.delay(1) for _ in range(100)]
    capped_delays = [policy.delay(1000) for _ in range(100)]

    assert all(1.6 <= delay <= 2.4 for delay in first_delays)
    assert all(math.isfinite(delay) and 0 <= delay <= 5 for delay in capped_delays)


def test_policy_finite_extreme_delays_do_not_overflow_intermediate_power() -> None:
    policy = ReconnectPolicy(
        initial_delay=1e-300, max_delay=1e300, multiplier=10, jitter=0
    )

    assert policy.delay(400) == pytest.approx(1e99)
    assert policy.delay(10**20) == 1e300


@pytest.mark.parametrize("max_attempts", [0, 1, 5])
def test_policy_retry_budget_excludes_the_initial_connection(max_attempts: int) -> None:
    policy = ReconnectPolicy(max_attempts=max_attempts)

    assert all(policy.allows(attempt) for attempt in range(1, max_attempts + 1))
    assert policy.allows(max_attempts + 1) is False


def test_disabling_reconnect_disallows_every_retry() -> None:
    policy = ReconnectPolicy(enabled=False)

    assert policy.allows(1) is False
    assert policy.allows(10_000) is False


@pytest.mark.parametrize(
    "options",
    [
        {"enabled": "yes"},
        {"enabled": 1},
        {"initial_delay": 0},
        {"initial_delay": -1},
        {"initial_delay": float("nan")},
        {"initial_delay": float("inf")},
        {"initial_delay": True},
        {"max_delay": 0},
        {"max_delay": float("nan")},
        {"max_delay": float("inf")},
        {"initial_delay": 2, "max_delay": 1},
        {"multiplier": 0.9},
        {"multiplier": float("nan")},
        {"multiplier": float("inf")},
        {"jitter": -0.1},
        {"jitter": 1},
        {"jitter": 1.1},
        {"jitter": float("nan")},
        {"jitter": float("inf")},
        {"max_attempts": -1},
        {"max_attempts": 1.5},
        {"max_attempts": True},
        {"stable_reset_after": -1},
        {"stable_reset_after": 0},
        {"stable_reset_after": float("nan")},
        {"stable_reset_after": float("inf")},
    ],
)
def test_policy_rejects_invalid_configuration(options: dict[str, object]) -> None:
    with pytest.raises((TypeError, ValueError)):
        ReconnectPolicy(**options)  # type: ignore[arg-type]


@pytest.mark.parametrize("attempt", [0, -1, True, 1.5, float("nan"), "1"])
def test_policy_rejects_invalid_attempt_numbers(attempt: object) -> None:
    policy = ReconnectPolicy()

    with pytest.raises((TypeError, ValueError)):
        policy.delay(attempt)  # type: ignore[arg-type]
    with pytest.raises((TypeError, ValueError)):
        policy.allows(attempt)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (OSError("offline"), "network"),
        (TimeoutError("offline"), "network"),
        (httpx.ConnectError("offline"), "network"),
        (httpx.ReadTimeout("offline"), "network"),
        (ssl.SSLCertVerificationError("bad certificate"), "configuration"),
        (FileNotFoundError("missing binary"), "configuration"),
        (PermissionError("unreadable device"), "configuration"),
        (RuntimeError("Facebook checkpoint required"), "auth_required"),
        (RuntimeError("Invalid cookie"), "auth_required"),
        (RuntimeError("bridge protocol is unsupported"), "protocol"),
        (RuntimeError("unexpected internal bug"), "unknown"),
    ],
)
def test_connection_failures_have_explicit_retry_classification(
    error: BaseException, reason: str
) -> None:
    assert classify_connection_error(error) == reason


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        (401, "auth_required"),
        (403, "auth_required"),
        (404, "configuration"),
        (408, "network"),
        (429, "network"),
        (500, "network"),
        (503, "network"),
    ],
)
def test_http_connection_failures_preserve_auth_vs_outage_semantics(
    status: int, reason: str
) -> None:
    request = httpx.Request("GET", "https://offline.example.test")
    response = httpx.Response(status, request=request)
    error = httpx.HTTPStatusError(
        "synthetic failure", request=request, response=response
    )

    assert classify_connection_error(error) == reason


def test_wrapped_network_error_is_retryable_but_unknown_error_is_not() -> None:
    wrapped = RuntimeError("safe wrapper")
    wrapped.__cause__ = httpx.ConnectError("PRIVATE_CONNECTION_DETAIL")

    assert classify_connection_error(wrapped) == "network"
    assert ConnectionFailure("network").retryable is True
    assert ConnectionFailure("unknown").retryable is False


@pytest.mark.parametrize("extra_wrapper", [False, True])
def test_network_wrapper_cannot_hide_permanent_tls_failure(extra_wrapper: bool) -> None:
    error = httpx.ConnectError("synthetic connection error")
    error.__cause__ = ssl.SSLCertVerificationError("synthetic certificate failure")
    if extra_wrapper:
        outer = OSError("synthetic network wrapper")
        outer.__cause__ = error
        assert classify_connection_error(outer) == "configuration"
    else:
        assert classify_connection_error(error) == "configuration"


def test_error_classifier_ignores_untrusted_unhashable_error_attributes() -> None:
    error = OSError("synthetic outage")
    error.reason = {"unexpected": "provider structure"}

    assert classify_connection_error(error) == "network"


def test_safe_failure_does_not_include_unrecognized_provider_details() -> None:
    failure = ConnectionFailure("PRIVATE_COOKIE_OR_CHAT_CONTENT")

    assert failure.reason == "unknown"
    assert failure.failure_code == "unknown"
    assert "PRIVATE" not in str(failure)


def test_connection_status_has_only_allowlisted_fields_and_detached_snapshots() -> None:
    events: list[dict[str, object]] = []
    tracker = ConnectionStateTracker(events.append)
    tracker.update("starting")
    tracker.update("reconnecting", "PRIVATE_COOKIE_OR_CHAT_CONTENT", 2, 5)

    status = tracker.snapshot()
    assert status == {
        "state": "reconnecting",
        "reason": "unknown",
        "attempt": 2,
        "next_retry_in": 5.0,
    }
    assert events[-1] == status
    status["reason"] = "PRIVATE_MUTATION"
    events[-1]["state"] = "PRIVATE_MUTATION"
    assert tracker.snapshot()["state"] == "reconnecting"
    assert tracker.snapshot()["reason"] == "unknown"


@pytest.mark.parametrize("terminal_state", ["auth_required", "fatal", "stopped"])
def test_terminal_connection_status_cannot_be_resurrected_by_late_callbacks(
    terminal_state: str,
) -> None:
    tracker = ConnectionStateTracker()
    tracker.update("starting")
    tracker.update(terminal_state)
    tracker.update("connected")
    tracker.update("reconnecting", "network", 1, 1)

    assert tracker.snapshot()["state"] == terminal_state

    tracker.update("starting")
    tracker.update("connected")
    assert tracker.snapshot()["state"] == "connected"


def test_callback_failure_does_not_stop_transport_or_log_provider_details(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def failing_callback(status: dict[str, object]) -> None:
        raise RuntimeError("PRIVATE_COOKIE_OR_CHAT_CONTENT")

    tracker = ConnectionStateTracker(failing_callback)
    tracker.update("starting")
    tracker.update("connected")

    assert tracker.snapshot()["state"] == "connected"
    assert "PRIVATE" not in caplog.text
