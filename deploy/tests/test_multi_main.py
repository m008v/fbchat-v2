from __future__ import annotations

import asyncio
import contextvars
import inspect
import json
from pathlib import Path
from typing import Any

import pytest

import main as upstream_main
import multi_main
from _messaging._listening_e2ee import listeningE2EEEvent


class _FakeListener:
    startup_timeout = 1.0
    device_path: str | None = None

    def on_message(self, callback: Any) -> None:
        pass

    async def connect_mqtt(self) -> None:
        await asyncio.Event().wait()

    def wait_until_connected(self, timeout: float, *, require_e2ee: bool) -> bool:
        return True

    def stop(self) -> None:
        pass


@pytest.fixture
def fake_listener(monkeypatch: pytest.MonkeyPatch) -> _FakeListener:
    listener = _FakeListener()
    monkeypatch.setattr(
        upstream_main, "listeningE2EEEvent", lambda data, **options: listener
    )
    return listener


def _write_account(root: Path, name: str, **overrides: Any) -> Path:
    account_dir = root / name
    account_dir.mkdir(parents=True)
    config = {"cookies": "c_user=1; xs=x;", "prefix": "/", "admins": []}
    config.update(overrides)
    (account_dir / "config.json").write_text(json.dumps(config), encoding="utf-8")
    return account_dir


# --- Contract với upstream: báo sớm khi src/main.py hoặc listener đổi API ---


def test_upstream_contract_used_by_fork(mock_dataFB: dict[str, Any]) -> None:
    assert callable(upstream_main.log)
    assert callable(getattr(upstream_main.SimpleBot, "_queue_event", None))
    assert callable(getattr(upstream_main.SimpleBot, "_forward_listener_event", None))
    for name in (
        "prefix",
        "admins",
        "log_message_content",
        "debug_errors",
        "http_client",
    ):
        assert name in inspect.signature(upstream_main.SimpleBot).parameters

    listener = listeningE2EEEvent(mock_dataFB)
    assert hasattr(listener, "device_path")
    assert isinstance(listener.e2ee_memory_only, bool)
    assert isinstance(listener.startup_timeout, float)
    wait_params = inspect.signature(listener.wait_until_connected).parameters
    assert "require_e2ee" in wait_params


def test_simple_bot_resolves_log_from_main_at_call_time(
    monkeypatch: pytest.MonkeyPatch,
    mock_dataFB: dict[str, Any],
    fake_listener: _FakeListener,
) -> None:
    lines: list[tuple[str, str]] = []
    monkeypatch.setattr(
        upstream_main, "log", lambda tag, message: lines.append((tag, message))
    )
    bot = upstream_main.SimpleBot(mock_dataFB)

    bot._queue_event({"type": "ready"})

    assert lines == [("e2ee", "ready")]


# --- Hành vi của runner ---


def test_discover_accounts_requires_config_and_safe_name(tmp_path: Path) -> None:
    _write_account(tmp_path, "beta")
    _write_account(tmp_path, "alpha")
    _write_account(tmp_path, "-bad")
    (tmp_path / "empty").mkdir()
    (tmp_path / "stray.json").write_text("{}", encoding="utf-8")

    names = [name for name, _ in multi_main.discover_accounts(tmp_path)]

    assert names == ["alpha", "beta"]


def test_discover_accounts_missing_root_returns_empty(tmp_path: Path) -> None:
    assert multi_main.discover_accounts(tmp_path / "missing") == []


def test_load_account_config_applies_defaults_and_validates(tmp_path: Path) -> None:
    account_dir = _write_account(tmp_path, "acc1")
    config = multi_main.load_account_config(account_dir / "config.json")
    assert config["log_message_content"] is False
    assert config["debug_errors"] is False

    bad_dir = _write_account(tmp_path, "acc2", admins="42")
    with pytest.raises(ValueError, match="admins"):
        multi_main.load_account_config(bad_dir / "config.json")


@pytest.mark.asyncio
async def test_run_account_builds_account_bot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mock_dataFB: dict[str, Any]
) -> None:
    account_dir = _write_account(tmp_path, "acc1", admins=["42"])
    created: list[dict[str, Any]] = []

    async def fake_data_get_home(**_: Any) -> dict[str, Any]:
        return mock_dataFB

    class _FakeBot:
        def __init__(self, dataFB: dict[str, Any], **options: Any) -> None:
            created.append(options)
            self.listener = self

        async def get_cookies(self) -> dict[str, str]:
            return {}

        async def run(self) -> None:
            return None

    monkeypatch.setattr(multi_main, "dataGetHome", fake_data_get_home)
    monkeypatch.setattr(multi_main, "AccountBot", _FakeBot)

    await multi_main.run_account("acc1", account_dir, object())  # type: ignore[arg-type]

    assert created[0]["account"] == "acc1"
    assert created[0]["device_path"] == str(account_dir / "e2ee_device.json")
    assert created[0]["admins"] == ["42"]


@pytest.mark.asyncio
async def test_run_account_rejects_invalid_session(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    account_dir = _write_account(tmp_path, "acc1")

    async def fake_data_get_home(**_: Any) -> None:
        return None

    reachable = {"ok": True}

    async def fake_reachable(_: Any) -> bool:
        return reachable["ok"]

    async def fake_diagnose(_: Any, cookie: str) -> str:
        assert cookie  # chẩn đoán bằng cookie của chính tài khoản
        return "revoked"

    monkeypatch.setattr(multi_main, "dataGetHome", fake_data_get_home)
    monkeypatch.setattr(multi_main, "facebook_reachable", fake_reachable)
    monkeypatch.setattr(multi_main, "diagnose_session", fake_diagnose)

    with pytest.raises(multi_main.SessionExpiredError, match="dataFB") as raised:
        await multi_main.run_account("acc1", account_dir, object())  # type: ignore[arg-type]
    assert raised.value.cause == "revoked"
    # Mất mạng: dataGetHome cũng trả None nhưng không phải hết phiên.
    reachable["ok"] = False
    with pytest.raises(ConnectionError):
        await multi_main.run_account("acc1", account_dir, object())  # type: ignore[arg-type]


def test_account_bot_sets_device_path_on_listener(
    mock_dataFB: dict[str, Any], fake_listener: _FakeListener
) -> None:
    multi_main.AccountBot(mock_dataFB, account="acc1", device_path="/d/acc1.json")

    assert fake_listener.device_path == "/d/acc1.json"
    assert fake_listener.e2ee_memory_only is False  # trạng thái E2EE được lưu ra file


def test_listener_callback_logs_with_account_label(
    monkeypatch: pytest.MonkeyPatch,
    mock_dataFB: dict[str, Any],
    fake_listener: _FakeListener,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(upstream_main, "log", multi_main.log)
    bot = multi_main.AccountBot(mock_dataFB, account="acc1", device_path="/d.json")

    # Mô phỏng call_soon_threadsafe: callback chạy trong context không có nhãn.
    contextvars.Context().run(bot._queue_event, {"type": "ready"})

    assert "[acc1] [e2ee] ready" in capsys.readouterr().out
    assert multi_main.LOG_LABEL.get() == ""


@pytest.mark.asyncio
async def test_on_ready_fires_when_listener_is_ready(
    mock_dataFB: dict[str, Any], fake_listener: _FakeListener
) -> None:
    bot = multi_main.AccountBot(mock_dataFB, account="acc1", device_path="/d.json")
    ready = asyncio.Event()

    await multi_main._notify_when_ready(bot, ready.set)

    assert ready.is_set()


@pytest.mark.asyncio
async def test_failing_account_gives_up_without_stopping_others(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: dict[str, int] = {"bad": 0, "good": 0}

    async def fake_run_account(name: str, *_: Any, **__: Any) -> None:
        calls[name] += 1
        if name == "bad":
            raise multi_main.SessionExpiredError("cookie expired")

    monkeypatch.setattr(multi_main, "run_account", fake_run_account)

    results = await asyncio.gather(
        multi_main.supervise_account(
            "bad", tmp_path, object(), max_attempts=3, retry_base=0  # type: ignore[arg-type]
        ),
        multi_main.supervise_account(
            "good", tmp_path, object(), max_attempts=3, retry_base=0  # type: ignore[arg-type]
        ),
    )

    assert results == [False, True]
    assert calls == {"bad": multi_main.SESSION_EXPIRED_ATTEMPTS, "good": 1}


@pytest.mark.asyncio
async def test_long_running_account_resets_retry_budget(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    failures = {"left": 6}

    async def flaky_run_account(*_: Any, **__: Any) -> None:
        if failures["left"]:
            failures["left"] -= 1
            raise RuntimeError("E2EE listener đã dừng ngoài dự kiến.")

    monkeypatch.setattr(multi_main, "run_account", flaky_run_account)

    # stable_after=0: mọi lần chạy được coi là ổn định nên không bao giờ bỏ cuộc.
    ok = await multi_main.supervise_account(
        "acc1",
        tmp_path,
        object(),  # type: ignore[arg-type]
        max_attempts=2,
        retry_base=0,
        stable_after=0,
    )

    assert ok is True
    assert failures["left"] == 0


@pytest.mark.asyncio
async def test_health_file_tracks_running_and_dropped_accounts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    health = tmp_path / "health.json"
    monkeypatch.setattr(multi_main, "HEALTH_FILE", str(health))
    monkeypatch.setattr(multi_main, "_account_states", {})
    seen_while_running: list[dict[str, str]] = []

    async def fake_run_account(name: str, *_: Any, on_ready: Any = None) -> None:
        if name == "bad":
            raise multi_main.SessionExpiredError("cookie expired")
        on_ready()
        seen_while_running.append(json.loads(health.read_text(encoding="utf-8")))

    monkeypatch.setattr(multi_main, "run_account", fake_run_account)

    await multi_main.supervise_account(
        "good", tmp_path, object(), max_attempts=2, retry_base=0  # type: ignore[arg-type]
    )
    await multi_main.supervise_account(
        "bad", tmp_path, object(), max_attempts=2, retry_base=0  # type: ignore[arg-type]
    )

    assert seen_while_running == [{"good": "running"}]
    assert json.loads(health.read_text(encoding="utf-8")) == {
        "good": "running",
        "bad": "dropped",
    }


@pytest.mark.asyncio
async def test_account_manager_routes_cookie_restart_and_remove(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mock_dataFB: dict[str, Any]
) -> None:
    _write_account(tmp_path, "shop")
    started: list[str] = []
    gate = asyncio.Event()

    async def fake_supervise(name: str, *_: Any, **__: Any) -> bool:
        started.append(name)
        multi_main.set_account_state(name, "running")
        await gate.wait()
        return True

    async def fake_data_get_home(cookie: str) -> dict[str, Any] | None:
        return mock_dataFB if "xs=good" in cookie else None

    monkeypatch.setattr(multi_main, "supervise_account", fake_supervise)
    monkeypatch.setattr(multi_main, "dataGetHome", fake_data_get_home)
    monkeypatch.setattr(multi_main, "_account_states", {})
    manager = multi_main.AccountManager(tmp_path, object())  # type: ignore[arg-type]
    manager.start("shop")
    await asyncio.sleep(0)

    assert await manager.handle("POST", "/send", b"") is None
    status, listed = await manager.handle("GET", "/accounts", b"")
    assert status == 200 and listed[0]["name"] == "shop"
    assert listed[0]["state"] == "running"
    assert (await manager.handle("POST", "/accounts/..%2F/cookie", b"{}"))[0] == 400

    no_xs = json.dumps({"cookie": "c_user=1;"}).encode()
    assert (await manager.handle("POST", "/accounts/new1/cookie", no_xs))[0] == 400
    bad = json.dumps({"cookie": "c_user=1; xs=bad;"}).encode()
    assert (await manager.handle("POST", "/accounts/new1/cookie", bad))[0] == 422
    assert not (tmp_path / "new1").exists()
    good = json.dumps({"cookie": "c_user=1; xs=good;"}).encode()
    status, body = await manager.handle("POST", "/accounts/new1/cookie", good)
    assert status == 200 and body["ok"] is True
    saved = json.loads((tmp_path / "new1" / "config.json").read_text(encoding="utf-8"))
    assert saved["cookies"] == "c_user=1; xs=good;"
    await asyncio.sleep(0)
    assert started == ["shop", "new1"]

    assert (await manager.handle("POST", "/accounts/shop/restart", b""))[0] == 202
    await asyncio.sleep(0)
    assert started == ["shop", "new1", "shop"]
    assert (await manager.handle("DELETE", "/accounts/new1", b""))[0] == 204
    assert not (tmp_path / "new1").exists()
    assert "new1" not in multi_main._account_states
    gate.set()
    await asyncio.gather(*manager.tasks.values())


@pytest.mark.asyncio
async def test_last_error_says_whether_to_sign_in_again(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    async def fake_run_account(
        name: str, *_: Any, on_ready: Any = None, **__: Any
    ) -> None:
        if name == "expired":
            raise multi_main.SessionExpiredError("dataFB", "checkpoint")
        if name == "flaky":
            if flaky_calls:
                await asyncio.Event().wait()  # lần sau: đang thử lại, chưa xong
            flaky_calls.append(1)
            raise RuntimeError("bridge closed")
        on_ready()

    monkeypatch.setattr(multi_main, "run_account", fake_run_account)
    monkeypatch.setattr(multi_main, "_account_errors", {"ok": {"kind": "connection"}})
    monkeypatch.setattr(multi_main, "_account_states", {})
    monkeypatch.setattr(multi_main, "_account_history", {})
    flaky_calls: list[int] = []
    for name in ("expired", "ok"):
        await multi_main.supervise_account(
            name, tmp_path / name, object(), max_attempts=1, retry_base=0  # type: ignore[arg-type]
        )
    # Lỗi kết nối không bao giờ bỏ tài khoản: vẫn đang thử lại.
    flaky = asyncio.create_task(
        multi_main.supervise_account(
            "flaky", tmp_path / "flaky", object(), max_attempts=1, retry_base=0  # type: ignore[arg-type]
        )
    )
    await asyncio.sleep(0.05)
    assert multi_main._account_states["flaky"] in ("starting", "retrying")
    flaky.cancel()
    errors = multi_main._account_errors
    assert errors["expired"]["kind"] == "session_expired"
    assert errors["expired"]["cause"] == "checkpoint"
    assert errors["expired"]["message"].startswith(multi_main.SESSION_EXPIRED_MESSAGE)
    assert "checkpoint" in errors["expired"]["message"]
    # Lịch sử: hết phiên kèm nguyên nhân, lỗi kết nối, chạy được thì "connected".
    kinds = {
        n: [h["kind"] for h in multi_main._account_history[n].list()]
        for n in ("expired", "ok", "flaky")
    }
    assert kinds == {
        "expired": ["session_expired"],
        "ok": ["connected"],
        "flaky": ["disconnected"],
    }
    assert errors["flaky"]["kind"] == "connection"
    assert "bridge closed" in errors["flaky"]["message"]
    assert "ok" not in errors  # chạy được thì xoá lỗi cũ
    manager = multi_main.AccountManager(tmp_path, object())  # type: ignore[arg-type]
    listed = {a["name"]: a for a in manager.list()}
    assert listed["expired"]["error"]["kind"] == "session_expired"
    assert listed["ok"]["error"] is None


@pytest.mark.asyncio
async def test_expired_session_stops_after_two_attempts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls = {"n": 0}

    async def fake_run_account(name: str, *_: Any, **__: Any) -> None:
        calls["n"] += 1
        raise multi_main.SessionExpiredError("dataFB")

    monkeypatch.setattr(multi_main, "run_account", fake_run_account)
    monkeypatch.setattr(multi_main, "_account_states", {})
    ok = await multi_main.supervise_account(
        "expired", tmp_path, object(), max_attempts=5, retry_base=0  # type: ignore[arg-type]
    )
    assert ok is False and calls["n"] == multi_main.SESSION_EXPIRED_ATTEMPTS
    assert multi_main._account_states["expired"] == "dropped"


def test_account_list_fills_name_from_contacts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class _Gateway:
        def cached_profile(self, uid: str) -> tuple[str, str]:
            return ("Shop Hai", "https://cdn/s.jpg") if uid == "615" else ("", "")

    monkeypatch.setattr(multi_main, "_gateway", _Gateway())
    monkeypatch.setattr(multi_main, "_account_states", {"shop2": "running"})
    monkeypatch.setattr(
        multi_main,
        "_account_profiles",
        {"shop2": {"uid": "615", "displayName": "", "avatar": ""}},
    )
    manager = multi_main.AccountManager(tmp_path, object())  # type: ignore[arg-type]
    profile = manager.list()[0]["profile"]
    assert profile == {
        "uid": "615",
        "displayName": "Shop Hai",
        "avatar": "https://cdn/s.jpg",
    }


@pytest.mark.asyncio
async def test_offline_account_keeps_retrying_until_network_returns(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls = {"n": 0}

    async def fake_run_account(
        name: str, *_: Any, on_ready: Any = None, **__: Any
    ) -> None:
        calls["n"] += 1
        if calls["n"] <= 7:  # quá max_attempts: trước đây bị bỏ
            raise ConnectionError("Không kết nối được Facebook (mất mạng?).")
        on_ready()

    monkeypatch.setattr(multi_main, "run_account", fake_run_account)
    monkeypatch.setattr(multi_main, "_account_states", {})
    ok = await multi_main.supervise_account(
        "offline", tmp_path, object(), max_attempts=3, retry_base=0  # type: ignore[arg-type]
    )
    assert ok is True and calls["n"] == 8
    assert multi_main._account_states["offline"] == "running"


@pytest.mark.asyncio
async def test_on_ready_waits_while_library_reconnects(
    mock_dataFB: dict[str, Any], fake_listener: _FakeListener
) -> None:
    # Từ 2.3.4: khởi động lúc mất mạng thì listener tự nối lại thay vì ném lỗi.
    answers = iter([False, False, True])
    fake_listener.connection_state = "reconnecting"  # type: ignore[attr-defined]
    fake_listener.wait_until_connected = (  # type: ignore[method-assign]
        lambda timeout, *, require_e2ee: next(answers)
    )
    bot = multi_main.AccountBot(mock_dataFB, account="acc1", device_path="/d.json")
    ready = asyncio.Event()

    await multi_main._notify_when_ready(bot, ready.set)

    assert ready.is_set()


@pytest.mark.asyncio
async def test_library_reconnect_status_moves_account_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mock_dataFB: dict[str, Any],
    fake_listener: _FakeListener,
) -> None:
    health = tmp_path / "health.json"
    monkeypatch.setattr(multi_main, "HEALTH_FILE", str(health))
    monkeypatch.setattr(multi_main, "_account_states", {"acc1": "running"})
    monkeypatch.setattr(multi_main, "_account_history", {})
    bot = multi_main.AccountBot(mock_dataFB, account="acc1", device_path="/d.json")
    bot._loop = asyncio.get_running_loop()

    bot._log_connection_status({"state": "reconnecting", "reason": "network"})
    await asyncio.sleep(0)
    assert json.loads(health.read_text()) == {"acc1": "retrying"}

    bot._log_connection_status({"state": "connected"})
    await asyncio.sleep(0)
    assert json.loads(health.read_text()) == {"acc1": "running"}
    kinds = [item["kind"] for item in multi_main.account_history("acc1").items]
    assert kinds[-2:] == ["network", "connected"]


@pytest.mark.asyncio
@pytest.mark.parametrize("event_type", ["reconnected", "e2eeConnected"])
async def test_e2ee_reconnect_without_transport_connected_restores_running(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mock_dataFB: dict[str, Any],
    fake_listener: _FakeListener,
    event_type: str,
) -> None:
    # shop2 30/10/2026: transport "reconnecting" rồi chỉ có e2ee "reconnected",
    # không có transport "connected"; tài khoản kẹt "retrying", container unhealthy.
    health = tmp_path / "health.json"
    monkeypatch.setattr(multi_main, "HEALTH_FILE", str(health))
    monkeypatch.setattr(multi_main, "_account_states", {"acc1": "running"})
    monkeypatch.setattr(multi_main, "_account_history", {})
    bot = multi_main.AccountBot(mock_dataFB, account="acc1", device_path="/d.json")
    bot._loop = asyncio.get_running_loop()

    bot._log_connection_status({"state": "reconnecting", "reason": "network"})
    await asyncio.sleep(0)
    assert json.loads(health.read_text()) == {"acc1": "retrying"}

    bot._record_lifecycle({"type": event_type})
    await asyncio.sleep(0)
    assert json.loads(health.read_text()) == {"acc1": "running"}

    # Đang chạy bình thường thì sự kiện E2EE không ghi thêm lịch sử "Đã kết nối".
    before = len(multi_main.account_history("acc1").items)
    bot._record_lifecycle({"type": "e2eeConnected"})
    await asyncio.sleep(0)
    assert len(multi_main.account_history("acc1").items) == before


def test_event_trace_only_for_listed_accounts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(multi_main, "TRACE_ACCOUNTS", {"acc2"})
    monkeypatch.setattr(multi_main, "TRACE_DIR", tmp_path / "trace")
    assert multi_main.open_trace("default") is None

    trace = multi_main.open_trace("acc2")
    assert trace is not None
    trace.write({"type": "raw", "data": {"type": "CallOffer"}})
    lines = trace.path.read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0])["event"]["data"]["type"] == "CallOffer"
    assert trace.path.stat().st_mode & 0o777 == 0o600


def test_event_trace_stops_at_size_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(multi_main, "TRACE_MAX_BYTES", 100)
    trace = multi_main.EventTrace(tmp_path / "t.jsonl")
    for _ in range(5):
        trace.write({"type": "message", "data": "x" * 30})
    assert len(trace.path.read_text(encoding="utf-8").splitlines()) == 1


@pytest.mark.asyncio
async def test_decrypt_failures_recorded_and_alerted_once(
    monkeypatch: pytest.MonkeyPatch,
    mock_dataFB: dict[str, Any],
    fake_listener: _FakeListener,
) -> None:
    monkeypatch.setattr(multi_main, "_account_history", {})
    alerts: list[str] = []

    class _Gateway:
        async def post_alert(self, text: str) -> None:
            alerts.append(text)

    monkeypatch.setattr(multi_main, "_gateway", _Gateway())
    bot = multi_main.AccountBot(mock_dataFB, account="acc1", device_path="/d.json")
    bot._loop = asyncio.get_running_loop()

    def error(message_id: str) -> dict[str, Any]:
        return {
            "type": "error",
            "data": {
                "message": "E2EE message could not be decrypted or was unavailable",
                "code": 2,
                "reason": "bad_mac",
                "messageId": message_id,
                "senderJid": "100012.0:3@msgr",
                "isGroup": True,
            },
        }

    for message_id in ["M1", "M1", "M2", "M3", "M4"]:
        await asyncio.to_thread(bot._record_lifecycle, error(message_id))
    await asyncio.sleep(0.05)

    items = multi_main.account_history("acc1").items
    assert [i["kind"] for i in items] == ["decrypt"]  # cùng thiết bị: gộp một mục
    assert items[0]["count"] == 5 and "MAC không khớp" in items[0]["message"]
    assert len(alerts) == 1
    assert "3 tin E2EE trong nhóm" in alerts[0] and "100012" not in alerts[0]


@pytest.mark.asyncio
async def test_undecryptable_placeholder_skipped_when_real_message_arrives(
    monkeypatch: pytest.MonkeyPatch,
    mock_dataFB: dict[str, Any],
    fake_listener: _FakeListener,
) -> None:
    # Nhóm 07/11/2026: lần gửi đầu thiếu khoá nhóm, tin thật tới sau 1 giây.
    forwarded: list[str] = []

    class _Gateway:
        async def forward(self, account: str, bot: Any, message: dict) -> None:
            forwarded.append(message["messageID"])

    monkeypatch.setattr(multi_main, "_gateway", _Gateway())
    monkeypatch.setattr(multi_main, "UNDECRYPTABLE_GRACE_SECONDS", 0.05)
    bot = multi_main.AccountBot(mock_dataFB, account="acc1", device_path="/d.json")

    late = asyncio.create_task(
        bot._forward_undecryptable({"messageID": "undecryptable-M1"})
    )
    lost = asyncio.create_task(
        bot._forward_undecryptable({"messageID": "undecryptable-M2"})
    )
    await bot._dispatch({"messageID": "M1", "userID": "200", "body": "hi"})
    await asyncio.gather(late, lost)

    assert forwarded == ["M1", "undecryptable-M2"]


def test_sender_key_events_logged_and_failures_recorded(
    monkeypatch: pytest.MonkeyPatch,
    mock_dataFB: dict[str, Any],
    fake_listener: _FakeListener,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(multi_main, "_account_history", {})
    bot = multi_main.AccountBot(mock_dataFB, account="acc1", device_path="/d.json")
    sender = "100012:3@msgr"

    bot._record_lifecycle(
        {
            "type": "e2eeSenderKey",
            "data": {"kind": "message", "sender": sender, "retryCount": 1},
        }
    )
    bot._record_lifecycle(
        {
            "type": "e2eeSenderKey",
            "data": {"kind": "failed", "sender": sender, "error": "other"},
        }
    )

    out = capsys.readouterr().out
    assert "[acc1] [e2ee-key]" in out and "gửi lại lần 1" in out
    assert "100012" not in out
    items = multi_main.account_history("acc1").items
    assert [item["kind"] for item in items] == ["decrypt"]
    assert "không lưu được khoá nhóm" in items[0]["message"]


@pytest.mark.asyncio
async def test_undecryptable_notes_pending_when_the_account_stops_are_dropped(
    monkeypatch: pytest.MonkeyPatch,
    mock_dataFB: dict[str, Any],
    fake_listener: _FakeListener,
) -> None:
    # Tài khoản bị gỡ trong 15 giây chờ: tin báo lỗi không được gửi vào gateway nữa.
    forwarded: list[str] = []

    class _Gateway:
        async def forward(self, account: str, bot: Any, message: dict) -> None:
            forwarded.append(message["messageID"])

    monkeypatch.setattr(multi_main, "_gateway", _Gateway())
    monkeypatch.setattr(multi_main, "UNDECRYPTABLE_GRACE_SECONDS", 0.05)
    bot = multi_main.AccountBot(mock_dataFB, account="acc1", device_path="/d.json")
    bot._spawn_undecryptable({"messageID": "undecryptable-M1"})
    bot._shutdown()
    bot._spawn_undecryptable({"messageID": "undecryptable-M2"})  # tới sau khi dừng
    await asyncio.sleep(0.1)
    assert forwarded == []
    assert not bot._lost_tasks


@pytest.mark.asyncio
async def test_remove_forgets_the_account_outside_its_folder(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _write_account(tmp_path, "acc2")
    trace_dir = tmp_path / "trace"
    trace_dir.mkdir()
    for name in (
        "acc2-20261115-090000.jsonl",
        "acc2-x-20261115-090000.jsonl",
        "shop1-20261115-090000.jsonl",
    ):
        (trace_dir / name).write_text("{}", encoding="utf-8")
    forgotten: list[str] = []

    class _Gateway:
        def forget_account(self, account: str) -> None:
            forgotten.append(account)

    monkeypatch.setattr(multi_main, "_gateway", _Gateway())
    monkeypatch.setattr(multi_main, "TRACE_DIR", trace_dir)
    monkeypatch.setattr(multi_main, "_account_states", {})
    manager = multi_main.AccountManager(tmp_path, object())  # type: ignore[arg-type]
    assert (await manager.handle("DELETE", "/accounts/acc2", b""))[0] == 204

    assert not (tmp_path / "acc2").exists()
    assert forgotten == ["acc2"]
    assert sorted(p.name for p in trace_dir.iterdir()) == [
        "acc2-x-20261115-090000.jsonl",
        "shop1-20261115-090000.jsonl",
    ]


def test_bot_account_finds_only_its_account(tmp_path: Path) -> None:
    _write_account(tmp_path, "uat.acc2")
    _write_account(tmp_path, "uat.shop2")
    assert [n for n, _ in multi_main.discover_accounts(tmp_path, "uat.acc2")] == [
        "uat.acc2"
    ]
    assert len(multi_main.discover_accounts(tmp_path, "")) == 2
    assert multi_main.only_account(" uat.acc2 ") == "uat.acc2"
    with pytest.raises(ValueError):
        multi_main.only_account("../etc")


@pytest.mark.asyncio
async def test_single_account_manager_ignores_other_accounts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _write_account(tmp_path, "uat.shop2")
    monkeypatch.setattr(multi_main, "_account_states", {})
    manager = multi_main.AccountManager(tmp_path, object(), only="uat.acc2")  # type: ignore[arg-type]

    status, listed = await manager.handle("GET", "/accounts", b"")
    # The container's account shows before it signs in; the other one never does.
    assert status == 200 and [a["name"] for a in listed] == ["uat.acc2"]
    assert listed[0]["state"] == "stopped"
    for method, path in (
        ("DELETE", "/accounts/uat.shop2"),
        ("POST", "/accounts/uat.shop2/restart"),
        ("POST", "/accounts/uat.shop2/cookie"),
    ):
        assert (await manager.handle(method, path, b"{}"))[0] == 404
    assert (tmp_path / "uat.shop2").exists()
