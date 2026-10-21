from __future__ import annotations

import hashlib
from importlib.metadata import version
from pathlib import Path
from typing import Any

import fbchat_v2
import httpx
import pytest
from fbchat_v2._features._facebook import _unFriend
from fbchat_v2._features._thread import _all_thread_data
from fbchat_v2._messaging._listening import listeningEvent
from fbchat_v2._messaging import _listening_e2ee as e2ee

EXPECTED_BRIDGE_SHA256 = {
    "fbchat-bridge-e2ee-darwin-amd64": (
        "f0d7a95eddf21cf0fc96bed33275d8f25e430626f0caba736eed40ff34b98f3b"
    ),
    "fbchat-bridge-e2ee-darwin-arm64": (
        "8eec475a33cbe3b836717e793a5d09827dd331e9b08c14b56c500ca7a4a31d10"
    ),
    "fbchat-bridge-e2ee-linux-amd64": (
        "6de0ce8db4986da2fd471385d63b61a5334084edb78bc6de2f53ecea6500189d"
    ),
    "fbchat-bridge-e2ee-linux-arm64": (
        "4d61087632c2c157294502265cb1e8807c0c5ac9c3d8addca2c109dd1eec1544"
    ),
    "fbchat-bridge-e2ee-windows-amd64.exe": (
        "dd304ef952eccfabae8c7c1f6dce71decc1ed0bf275f5aec59e155460fe235e3"
    ),
}


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


def test_public_namespace_and_version_are_stable() -> None:
    assert fbchat_v2.__version__ == version("fbchat-v2") == "2.3.4"
    assert callable(_unFriend.func)


def test_public_reconnect_exports_and_listener_status_are_offline() -> None:
    policy = fbchat_v2.ReconnectPolicy(max_attempts=2, jitter=0.0)
    assert policy.allows(1) is True
    assert policy.allows(3) is False

    failure = fbchat_v2.ConnectionFailure("auth_required")
    assert failure.failure_code == "auth_required"
    assert failure.retryable is False

    listeners = (
        fbchat_v2.listeningEvent({}, reconnect_policy=policy),
        fbchat_v2.listeningE2EEEvent({}, reconnect_policy=policy),
    )
    for listener in listeners:
        assert listener.reconnect_policy is policy
        assert listener.connection_state == "stopped"
        status = listener.connection_status
        assert status == {
            "state": "stopped",
            "reason": "",
            "attempt": 0,
            "next_retry_in": 0.0,
        }
        status["state"] = "connected"
        assert listener.connection_state == "stopped"


def test_explicit_reconnect_policy_requires_structured_bridge_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bridge = object.__new__(e2ee._BridgeProcess)
    bridge._reconnect_policy = fbchat_v2.ReconnectPolicy()
    hello = {
        "protocolVersion": 1,
        "bridgeVersion": "2.3.4",
        "capabilities": sorted(e2ee._BRIDGE_REQUIRED_CAPABILITIES),
    }
    monkeypatch.setattr(e2ee, "BRIDGE_RELEASE_VERSION", "2.3.4")
    monkeypatch.setattr(bridge, "call_blocking", lambda *args, **kwargs: hello)

    with pytest.raises(e2ee.BridgeError, match="structuredConnectionStatus"):
        bridge._validate_contract()

    hello["capabilities"].append("structuredConnectionStatus")
    assert bridge._validate_contract() == hello


def test_blocking_sequence_refresh_never_calls_async_transport(monkeypatch) -> None:
    listener = listeningEvent({"cookieFacebook": "test"})

    def fail_async(*args, **kwargs):
        raise AssertionError("blocking API called the async transport")

    monkeypatch.setattr(_all_thread_data, "func", fail_async)
    monkeypatch.setattr(
        _all_thread_data,
        "func_blocking",
        lambda data_fb: {"last_seq_id": 42},
    )

    assert listener.get_last_seq_id_blocking() == 42
    assert listener.fbt == {"last_seq_id": 42}


def test_release_bridge_checksums_are_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    assert e2ee._BRIDGE_RELEASE_REPOSITORY == "m008v/fbchat-v2"
    assert e2ee.BRIDGE_RELEASE_VERSION == "2.3.4"
    assert e2ee.BRIDGE_SHA256 == EXPECTED_BRIDGE_SHA256

    binary_name = "fbchat-bridge-e2ee-windows-amd64.exe"
    monkeypatch.setattr(e2ee, "_PACKAGE_VERSION", "2.3.4")
    assert e2ee._release_version_and_digest(binary_name) == (
        "2.3.4",
        EXPECTED_BRIDGE_SHA256[binary_name],
    )


def test_namespaced_checkout_resolves_source_and_installed_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module_path = tmp_path / "src" / "fbchat_v2" / "_messaging" / "_listening_e2ee.py"
    module_path.parent.mkdir(parents=True)
    module_path.touch()
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "fbchat-v2"\nversion = "2.3.4"\n', encoding="utf-8"
    )

    monkeypatch.setattr(e2ee, "__file__", str(module_path))
    monkeypatch.setattr(e2ee, "_PACKAGE_VERSION", "0.0.0")
    monkeypatch.setattr(e2ee.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "cache"))

    assert e2ee._is_source_checkout() is True
    assert e2ee._expected_package_version() == "2.3.4"
    assert e2ee._default_binary_path() == (
        tmp_path / "build" / "fbchat-bridge-e2ee.exe"
    )

    monkeypatch.setattr(e2ee, "_PACKAGE_VERSION", "2.3.4")
    assert e2ee._release_version_and_digest("fbchat-bridge-e2ee-windows-amd64.exe") == (
        "2.3.4",
        EXPECTED_BRIDGE_SHA256["fbchat-bridge-e2ee-windows-amd64.exe"],
    )

    (tmp_path / "pyproject.toml").unlink()
    assert e2ee._is_source_checkout() is False
    assert e2ee._expected_package_version() == "2.3.4"
    assert e2ee._default_binary_path() == (
        tmp_path
        / "cache"
        / "fbchat-v2"
        / "bridge"
        / "v2.3.4"
        / "fbchat-bridge-e2ee.exe"
    )


def test_download_bridge_accepts_canonical_release_owner(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    version_number = "2.3.4"
    binary_name = "fbchat-bridge-e2ee-windows-amd64.exe"
    content = b"verified bridge payload"
    expected_digest = hashlib.sha256(content).hexdigest()
    download_url = (
        "https://github.com/m008v/fbchat-v2/releases/download/"
        f"v{version_number}/{binary_name}"
    )
    api_url = (
        "https://api.github.com/repos/m008v/fbchat-v2/releases/tags/"
        f"v{version_number}"
    )
    payload = {
        "tag_name": f"v{version_number}",
        "assets": [
            {
                "name": binary_name,
                "browser_download_url": download_url,
                "digest": f"sha256:{expected_digest}",
            }
        ],
    }

    monkeypatch.setattr(e2ee, "_PACKAGE_VERSION", version_number)
    monkeypatch.setattr(e2ee, "BRIDGE_RELEASE_VERSION", version_number)
    monkeypatch.setattr(e2ee, "BRIDGE_SHA256", {binary_name: expected_digest})
    monkeypatch.setattr("platform.system", lambda: "Windows")
    monkeypatch.setattr("platform.machine", lambda: "AMD64")
    monkeypatch.delenv("FBCHAT_E2EE_SHA256", raising=False)

    def get_release(url: str, **kwargs: Any) -> _ReleaseResponse:
        assert url == api_url
        assert kwargs["follow_redirects"] is True
        return _ReleaseResponse(payload, url)

    monkeypatch.setattr(e2ee.httpx, "get", get_release)
    monkeypatch.setattr(
        e2ee.httpx,
        "stream",
        lambda *args, **kwargs: _StreamResponse(content, download_url),
    )

    target = tmp_path / "bridge.exe"
    e2ee._download_bridge(target)

    assert target.read_bytes() == content
    assert hashlib.sha256(target.read_bytes()).hexdigest() == expected_digest
    assert not list(tmp_path.glob(".bridge.exe.*.download"))
