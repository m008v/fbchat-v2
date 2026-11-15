from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path
from typing import Any

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "login_control", Path(__file__).resolve().parents[1] / "login" / "control.py"
)
assert _SPEC and _SPEC.loader
control: Any = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(control)


@pytest.fixture
def fake_login(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """extract_cookie.py giả: thoát 0 khi có file "done", chạy tiếp nếu chưa."""
    script = tmp_path / "fake_extract.py"
    done = tmp_path / "done"
    script.write_text(
        "import os, pathlib, sys, time\n"
        f"done = pathlib.Path({str(done)!r})\n"
        "assert os.environ['FORCE_LOGIN'] == '1'\n"
        f"pathlib.Path({str(tmp_path / 'config_path')!r}).write_text("
        "os.environ.get('CONFIG_PATH', ''))\n"
        "while not done.exists():\n"
        "    time.sleep(0.05)\n"
        "print('[login] Đã phát hiện đăng nhập, đóng Chromium...', flush=True)\n"
        "time.sleep(0.3)\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )
    profile = tmp_path / "profile"
    profile.mkdir()
    monkeypatch.setattr(control, "SCRIPT", script)
    monkeypatch.setattr(control, "PROFILE_DIR", profile)
    monkeypatch.setattr(control, "_proc", None)
    monkeypatch.setattr(
        control,
        "_state",
        {
            "account": "",
            "target": "facebook",
            "status": "idle",
            "message": "",
            "at": 0.0,
        },
    )
    monkeypatch.setattr(control.sys, "executable", sys.executable)
    return done


def _wait(pred: Any, timeout: float = 5.0) -> None:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return
        time.sleep(0.05)
    raise AssertionError("timeout")


def test_session_lifecycle(fake_login: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vnc = {"up": False}
    monkeypatch.setattr(control, "_vnc_ready", lambda: vnc["up"])

    status, state = control.start("shop1")
    assert status == 202 and state["status"] == "starting"
    assert not control.PROFILE_DIR.exists()  # hồ sơ cũ bị xoá trước phiên

    assert control.start("other")[0] == 409
    assert control.start("shop1")[0] == 200  # cùng tài khoản: trả phiên đang chạy

    vnc["up"] = True
    assert control.snapshot()["status"] == "running"

    fake_login.write_text("1")
    _wait(lambda: control.snapshot()["status"] == "saving")
    _wait(lambda: control.snapshot()["status"] == "success")
    assert control.snapshot()["account"] == "shop1"


def test_cancel_stops_browser(
    fake_login: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(control, "_vnc_ready", lambda: True)
    control.start("shop1")
    proc = control._proc
    state = control.stop()
    assert state["status"] == "cancelled"
    assert proc.poll() is not None
    time.sleep(0.2)  # watcher không ghi đè trạng thái đã huỷ
    assert control.snapshot()["status"] == "cancelled"


def test_fbweb_target_writes_to_its_own_volume(
    fake_login: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(control, "_vnc_ready", lambda: True)
    monkeypatch.setattr(control, "FBWEB_LOGINS_DIR", tmp_path / "missing")
    assert control.start("owner", "fbweb")[0] == 501  # chưa gắn volume

    logins = tmp_path / "fbweb"
    logins.mkdir()
    monkeypatch.setattr(control, "FBWEB_LOGINS_DIR", logins)
    status, state = control.start("owner", "fbweb")
    assert status == 202 and state["target"] == "fbweb"
    # Cùng tên nhưng là phiên Facebook cá nhân: phiên khác.
    assert control.start("owner", "facebook")[0] == 409
    assert control.start("owner", "fbweb")[0] == 200
    _wait(lambda: (tmp_path / "config_path").exists())
    assert (tmp_path / "config_path").read_text() == str(
        logins / "owner" / "config.json"
    )
    fake_login.write_text("1")
    _wait(lambda: control.snapshot()["status"] == "success")
    assert control.snapshot()["target"] == "fbweb"


def test_handoff_keeps_the_cookie_off_the_bot_volume_and_gives_it_once(
    fake_login: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # omi (D27): the bot runs in its own pod, so the cookie waits in tmpfs for the gateway.
    handoff = tmp_path / "handoff"
    monkeypatch.setattr(control, "HANDOFF_DIR", handoff)
    monkeypatch.setattr(control, "_vnc_ready", lambda: True)
    assert control.start("uat.shop2", "facebook")[0] == 202
    _wait(lambda: (tmp_path / "config_path").exists())
    assert (tmp_path / "config_path").read_text() == str(
        handoff / "uat.shop2" / "config.json"
    )
    fake_login.write_text("1")
    _wait(lambda: control.snapshot()["status"] == "success")

    (handoff / "uat.shop2").mkdir(parents=True, exist_ok=True)
    (handoff / "uat.shop2" / "config.json").write_text(
        '{"cookies": "c_user=1; xs=x;"}', encoding="utf-8"
    )
    assert control.take_cookie("uat.other") is None
    assert control.take_cookie("uat.shop2") == "c_user=1; xs=x;"
    assert control.take_cookie("uat.shop2") is None  # once
    assert not (handoff / "uat.shop2").exists()


def test_handoff_also_takes_fanpage_web_logins(
    fake_login: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # omi: Fanpage Web runs in the clinic's pod, so its login goes through the gateway too,
    # and no fbweb volume is needed.
    handoff = tmp_path / "handoff"
    monkeypatch.setattr(control, "HANDOFF_DIR", handoff)
    monkeypatch.setattr(control, "FBWEB_LOGINS_DIR", tmp_path / "missing")
    monkeypatch.setattr(control, "_vnc_ready", lambda: True)
    status, state = control.start("uat.owner", "fbweb")
    assert status == 202 and state["target"] == "fbweb"
    _wait(lambda: (tmp_path / "config_path").exists())
    assert (tmp_path / "config_path").read_text() == str(
        handoff / "uat.owner" / "config.json"
    )
    fake_login.write_text("1")
    _wait(lambda: control.snapshot()["status"] == "success")


def test_no_handoff_dir_gives_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(control, "HANDOFF_DIR", None)
    assert control.take_cookie("uat.shop2") is None
