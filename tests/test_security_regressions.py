import hashlib
import json
import os
import stat
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx
import pytest

import main as sample_main
from _core._permissions import _private_acl_environment
from _messaging import _listening_e2ee as e2ee


class _ReleaseResponse:
    def __init__(self, payload: dict[str, Any], url: str) -> None:
        self._payload = payload
        self.url = httpx.URL(url)
        self.history: list[Any] = []

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class _StreamResponse:
    def __init__(self, content: bytes, url: str) -> None:
        self._content = content
        self.url = httpx.URL(url)
        self.history: list[Any] = []
        self.headers = {"content-length": str(len(content))}

    def __enter__(self) -> "_StreamResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    def iter_bytes(self, chunk_size: int) -> list[bytes]:
        return [
            self._content[index : index + chunk_size]
            for index in range(0, len(self._content), chunk_size)
        ]


def _prepare_release(
    monkeypatch: pytest.MonkeyPatch,
    content: bytes,
    *,
    advertised_digest: str | None = None,
) -> str:
    version = "9.8.7"
    binary_name = "fbchat-bridge-e2ee-windows-amd64.exe"
    download_url = (
        "https://github.com/MinhHuyDev/fbchat-v2/releases/download/"
        f"v{version}/{binary_name}"
    )
    expected = hashlib.sha256(content).hexdigest()
    asset: dict[str, Any] = {
        "name": binary_name,
        "browser_download_url": download_url,
    }
    if advertised_digest is not None:
        asset["digest"] = advertised_digest

    monkeypatch.setattr(e2ee, "_PACKAGE_VERSION", version)
    monkeypatch.setattr(e2ee, "BRIDGE_RELEASE_VERSION", version)
    monkeypatch.setattr(e2ee, "BRIDGE_SHA256", {binary_name: expected})
    monkeypatch.delenv("FBCHAT_E2EE_SHA256", raising=False)
    monkeypatch.setattr("platform.system", lambda: "Windows")
    monkeypatch.setattr("platform.machine", lambda: "AMD64")

    def get_release(url: str, **kwargs: Any) -> _ReleaseResponse:
        assert url.endswith(f"/releases/tags/v{version}")
        assert kwargs["follow_redirects"] is True
        return _ReleaseResponse({"tag_name": f"v{version}", "assets": [asset]}, url)

    monkeypatch.setattr(
        e2ee.httpx,
        "get",
        get_release,
    )
    monkeypatch.setattr(
        e2ee.httpx,
        "stream",
        lambda *args, **kwargs: _StreamResponse(content, download_url),
    )
    return expected


def test_download_bridge_requires_independent_checksum(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(e2ee, "BRIDGE_RELEASE_VERSION", None)
    monkeypatch.setattr(e2ee, "BRIDGE_SHA256", {})
    monkeypatch.delenv("FBCHAT_E2EE_SHA256", raising=False)
    monkeypatch.setattr("platform.system", lambda: "Windows")
    monkeypatch.setattr("platform.machine", lambda: "AMD64")
    monkeypatch.setattr(
        e2ee.httpx,
        "get",
        lambda *args, **kwargs: pytest.fail("network must not run without checksum"),
    )

    with pytest.raises(RuntimeError, match="Thiếu checksum"):
        e2ee._download_bridge(tmp_path / "bridge.exe")


def test_download_bridge_is_version_pinned_and_verified(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    content = b"verified bridge payload"
    expected = _prepare_release(monkeypatch, content)
    target = tmp_path / "bridge.exe"

    e2ee._download_bridge(target)

    assert target.read_bytes() == content
    assert expected == hashlib.sha256(target.read_bytes()).hexdigest()
    assert not list(tmp_path.glob(".bridge.exe.*.download"))


def test_download_bridge_rejects_github_digest_disagreement(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _prepare_release(monkeypatch, b"payload", advertised_digest=f"sha256:{'0' * 64}")

    with pytest.raises(RuntimeError, match="không khớp checksum trong package"):
        e2ee._download_bridge(tmp_path / "bridge.exe")


def test_download_bridge_removes_partial_file_on_checksum_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    content = b"tampered payload"
    _prepare_release(monkeypatch, content)
    monkeypatch.setattr(
        e2ee,
        "BRIDGE_SHA256",
        {"fbchat-bridge-e2ee-windows-amd64.exe": "f" * 64},
    )
    target = tmp_path / "bridge.exe"

    with pytest.raises(RuntimeError, match="không khớp package"):
        e2ee._download_bridge(target)

    assert not target.exists()
    assert not list(tmp_path.glob(".bridge.exe.*.download"))


def test_resolve_binary_replaces_tampered_managed_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "bridge.exe"
    target.write_bytes(b"tampered")
    replacement = b"verified replacement"
    expected = hashlib.sha256(replacement).hexdigest()

    monkeypatch.delenv("FBCHAT_E2EE_BIN", raising=False)
    monkeypatch.setattr(e2ee, "_default_binary_path", lambda: target)
    monkeypatch.setattr(e2ee, "_is_source_checkout", lambda: False)
    monkeypatch.setattr(
        e2ee,
        "_verify_managed_binary",
        lambda path: (_ for _ in ()).throw(RuntimeError("tampered")),
    )

    def replace_cache(path: Path) -> None:
        assert not path.exists()
        path.write_bytes(replacement)

    monkeypatch.setattr(e2ee, "_download_bridge", replace_cache)

    assert e2ee._resolve_binary() == target
    assert target.read_bytes() == replacement
    assert expected == hashlib.sha256(target.read_bytes()).hexdigest()


def test_resolve_binary_rejects_stale_source_build(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "bridge.exe"
    target.write_bytes(b"old build")
    monkeypatch.delenv("FBCHAT_E2EE_BIN", raising=False)
    monkeypatch.setattr(e2ee, "_default_binary_path", lambda: target)
    monkeypatch.setattr(e2ee, "_is_source_checkout", lambda: True)
    monkeypatch.setattr(e2ee, "_source_bridge_is_stale", lambda path: True)

    with pytest.raises(RuntimeError, match="cũ hơn mã nguồn"):
        e2ee._resolve_binary()


def test_source_bridge_freshness_compares_real_mtimes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "bridge.exe"
    source = tmp_path / "events.go"
    target.write_bytes(b"build")
    source.write_text("package bridge", encoding="utf-8")
    timestamp = time.time_ns()
    os.utime(source, ns=(timestamp, timestamp))
    os.utime(target, ns=(timestamp + 1_000_000, timestamp + 1_000_000))
    monkeypatch.setattr(e2ee, "_source_bridge_inputs", lambda: [source])

    assert e2ee._source_bridge_is_stale(target) is False

    os.utime(source, ns=(timestamp + 2_000_000, timestamp + 2_000_000))
    assert e2ee._source_bridge_is_stale(target) is True


def test_source_bridge_freshness_fails_closed_without_inputs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "bridge.exe"
    target.write_bytes(b"build")
    monkeypatch.setattr(e2ee, "_source_bridge_inputs", lambda: [])

    assert e2ee._source_bridge_is_stale(target) is True


def test_resolve_binary_accepts_fresh_source_build(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "bridge.exe"
    target.write_bytes(b"fresh build")
    monkeypatch.delenv("FBCHAT_E2EE_BIN", raising=False)
    monkeypatch.setattr(e2ee, "_default_binary_path", lambda: target)
    monkeypatch.setattr(e2ee, "_is_source_checkout", lambda: True)
    monkeypatch.setattr(e2ee, "_source_bridge_is_stale", lambda path: False)

    assert e2ee._resolve_binary() == target


def test_resolve_binary_explicit_override_bypasses_source_freshness(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "custom-bridge.exe"
    target.write_bytes(b"operator-selected build")
    monkeypatch.setenv("FBCHAT_E2EE_BIN", str(target))
    monkeypatch.setattr(
        e2ee,
        "_source_bridge_is_stale",
        lambda path: (_ for _ in ()).throw(AssertionError("freshness check ran")),
    )

    assert e2ee._resolve_binary() == target


def test_create_private_config_is_exclusive_and_private(tmp_path: Path) -> None:
    target = tmp_path / "config.json"
    template = {
        "cookies": "secret",
        "prefix": "/",
        "admins": [],
        "log_message_content": False,
        "debug_errors": False,
    }

    assert sample_main._create_private_config(target, template) is True
    assert sample_main._create_private_config(target, {"cookies": "overwrite"}) is False
    assert json.loads(target.read_text(encoding="utf-8")) == template
    if os.name != "nt":
        assert stat.S_IMODE(target.stat().st_mode) == 0o600


@pytest.mark.skipif(os.name != "nt", reason="Windows ACL regression")
def test_private_config_removes_unrelated_explicit_windows_aces(tmp_path: Path) -> None:
    target = tmp_path / "config.json"
    target.write_text("{}", encoding="utf-8")
    subprocess.run(
        ["icacls.exe", str(target), "/grant", "*S-1-1-0:(R)"],
        check=True,
        capture_output=True,
        text=True,
    )

    sample_main._set_private_file_permissions(target)

    acl_env = _private_acl_environment(target)
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "(Get-Acl -LiteralPath $env:FBCHAT_PRIVATE_FILE).Access | "
            "ForEach-Object { $_.IdentityReference.Translate("
            "[System.Security.Principal.SecurityIdentifier]).Value }",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=acl_env,
    )
    assert "S-1-1-0" not in result.stdout


def test_load_config_defaults_to_redacted_logging(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "config.json"
    monkeypatch.setattr(sample_main, "CONFIG_PATH", target)

    with pytest.raises(RuntimeError, match="template riêng tư"):
        sample_main.load_config()

    config = sample_main.load_config()
    assert config["log_message_content"] is False
    assert config["debug_errors"] is False


@pytest.mark.asyncio
async def test_message_body_logging_is_redacted_by_default(
    monkeypatch: pytest.MonkeyPatch, mock_dataFB: dict[str, Any]
) -> None:
    monkeypatch.setattr(
        sample_main, "listeningE2EEEvent", lambda data, **kwargs: object()
    )
    output: list[str] = []
    monkeypatch.setattr(sample_main, "log", lambda tag, message: output.append(message))
    bot = sample_main.SimpleBot(mock_dataFB)

    await bot._dispatch(
        {
            "messageID": "mid.1",
            "body": "private message",
            "userID": "2000",
            "replyToID": "3000",
            "type": "thread",
        }
    )

    assert output
    assert "private message" not in "\n".join(output)
    assert "<redacted length=15>" in "\n".join(output)


@pytest.mark.asyncio
async def test_message_body_logging_can_be_explicitly_enabled(
    monkeypatch: pytest.MonkeyPatch, mock_dataFB: dict[str, Any]
) -> None:
    monkeypatch.setattr(
        sample_main, "listeningE2EEEvent", lambda data, **kwargs: object()
    )
    output: list[str] = []
    monkeypatch.setattr(sample_main, "log", lambda tag, message: output.append(message))
    bot = sample_main.SimpleBot(mock_dataFB, log_message_content=True)

    await bot._dispatch(
        {
            "messageID": "mid.2",
            "body": "opt-in body",
            "userID": "2000",
            "replyToID": "3000",
            "type": "thread",
        }
    )

    assert "opt-in body" in "\n".join(output)


@pytest.mark.asyncio
async def test_unknown_command_name_is_redacted_by_default(
    monkeypatch: pytest.MonkeyPatch, mock_dataFB: dict[str, Any]
) -> None:
    monkeypatch.setattr(
        sample_main, "listeningE2EEEvent", lambda data, **kwargs: object()
    )
    output: list[str] = []
    monkeypatch.setattr(sample_main, "log", lambda tag, message: output.append(message))
    bot = sample_main.SimpleBot(mock_dataFB)

    await bot._dispatch(
        {
            "messageID": "mid.3",
            "body": "/PRIVATE_TOKEN",
            "userID": "2000",
            "replyToID": "3000",
            "type": "thread",
        }
    )

    joined = "\n".join(output)
    assert "private_token" not in joined
    assert "<redacted>" in joined


def test_listener_hides_bridge_error_payload(
    capsys: pytest.CaptureFixture[str],
) -> None:
    listener = e2ee.listeningE2EEEvent.__new__(e2ee.listeningE2EEEvent)
    listener._on_message = None
    listener.debug_errors = False

    listener._dispatch({"type": "error", "data": {"cookie": "SECRET_COOKIE"}})

    output = capsys.readouterr().out
    assert "SECRET_COOKIE" not in output
    assert "payload hidden" in output


def test_listener_can_explicitly_log_bridge_error_payload(
    capsys: pytest.CaptureFixture[str],
) -> None:
    listener = e2ee.listeningE2EEEvent.__new__(e2ee.listeningE2EEEvent)
    listener._on_message = None
    listener.debug_errors = True

    listener._dispatch({"type": "error", "data": {"code": "diagnostic"}})

    assert "diagnostic" in capsys.readouterr().out
