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
        "3d5462238b62b75fdc5cddd43eb440af8127105350eb6b4b5a8c48713b90cd9d"
    ),
    "fbchat-bridge-e2ee-darwin-arm64": (
        "24559a362b3c7d17c0f57ed53e0f0f7da1bcf3d9afcf80d0049670798ef5fd5d"
    ),
    "fbchat-bridge-e2ee-linux-amd64": (
        "c0ef9d5f6a897bc983a0a2d4c3847f4f661b3151e7ad4debdb0a329387921e75"
    ),
    "fbchat-bridge-e2ee-linux-arm64": (
        "f3eab15ec258abd4046e21e940332577c6a3073682f20e1e7ed9bcf6855b8ef6"
    ),
    "fbchat-bridge-e2ee-windows-amd64.exe": (
        "80c2f09179a1cc431d996ff3615bd44c47373869357d92b33d406cdafedb7054"
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
    assert fbchat_v2.__version__ == version("fbchat-v2") == "2.3.3"
    assert callable(_unFriend.func)


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
    assert e2ee.BRIDGE_RELEASE_VERSION == "2.3.3"
    assert e2ee.BRIDGE_SHA256 == EXPECTED_BRIDGE_SHA256

    binary_name = "fbchat-bridge-e2ee-windows-amd64.exe"
    monkeypatch.setattr(e2ee, "_PACKAGE_VERSION", "2.3.3")
    assert e2ee._release_version_and_digest(binary_name) == (
        "2.3.3",
        EXPECTED_BRIDGE_SHA256[binary_name],
    )


def test_namespaced_checkout_resolves_source_and_installed_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module_path = tmp_path / "src" / "fbchat_v2" / "_messaging" / "_listening_e2ee.py"
    module_path.parent.mkdir(parents=True)
    module_path.touch()
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "fbchat-v2"\nversion = "2.3.3"\n', encoding="utf-8"
    )

    monkeypatch.setattr(e2ee, "__file__", str(module_path))
    monkeypatch.setattr(e2ee, "_PACKAGE_VERSION", "0.0.0")
    monkeypatch.setattr(e2ee.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "cache"))

    assert e2ee._is_source_checkout() is True
    assert e2ee._expected_package_version() == "2.3.3"
    assert e2ee._default_binary_path() == (
        tmp_path / "build" / "fbchat-bridge-e2ee.exe"
    )

    monkeypatch.setattr(e2ee, "_PACKAGE_VERSION", "2.3.3")
    assert e2ee._release_version_and_digest("fbchat-bridge-e2ee-windows-amd64.exe") == (
        "2.3.3",
        EXPECTED_BRIDGE_SHA256["fbchat-bridge-e2ee-windows-amd64.exe"],
    )

    (tmp_path / "pyproject.toml").unlink()
    assert e2ee._is_source_checkout() is False
    assert e2ee._expected_package_version() == "2.3.3"
    assert e2ee._default_binary_path() == (
        tmp_path
        / "cache"
        / "fbchat-v2"
        / "bridge"
        / "v2.3.3"
        / "fbchat-bridge-e2ee.exe"
    )


def test_download_bridge_accepts_canonical_release_owner(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    version_number = "2.3.3"
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
