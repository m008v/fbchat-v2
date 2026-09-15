import os
import json
import stat
import subprocess
from pathlib import Path

import pytest

from _core import _storage as storage_module
from _core._permissions import _private_acl_environment
from _core._storage import FileSessionStorage, EnvSessionStorage


def test_file_session_storage(tmp_path):
    filepath = tmp_path / "config.json"
    storage = FileSessionStorage(filepath=str(filepath), key="cookies")

    # Test load when file doesn't exist
    assert storage.load() is None

    # Test save
    storage.save("c_user=123; xs=abc;")
    assert storage.load() == "c_user=123; xs=abc;"

    # Test clear
    storage.clear()
    assert storage.load() is None

    # Test save when file has other data
    with open(filepath, "w") as f:
        json.dump({"other_key": "value"}, f)
    storage.save("c_user=456; xs=def;")
    assert storage.load() == "c_user=456; xs=def;"

    with open(filepath, "r") as f:
        data = json.load(f)
    assert data["other_key"] == "value"
    assert data["cookies"] == "c_user=456; xs=def;"


def test_env_session_storage(monkeypatch):
    storage = EnvSessionStorage(env_var="TEST_FB_COOKIES")

    # Test load when env var doesn't exist
    monkeypatch.delenv("TEST_FB_COOKIES", raising=False)
    assert storage.load() is None

    # Test save
    storage.save("c_user=789; xs=ghi;")
    assert storage.load() == "c_user=789; xs=ghi;"
    assert os.environ["TEST_FB_COOKIES"] == "c_user=789; xs=ghi;"

    # Test clear
    storage.clear()
    assert storage.load() is None
    assert "TEST_FB_COOKIES" not in os.environ


def test_private_acl_environment_drops_parent_powershell_module_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "config.json"
    monkeypatch.setenv("PSModulePath", "pwsh-only-module-path")

    acl_env = _private_acl_environment(target)

    assert not any(key.casefold() == "psmodulepath" for key in acl_env)
    assert acl_env["FBCHAT_PRIVATE_FILE"] == str(target.resolve())


def test_file_storage_secures_temporary_file_before_atomic_replace(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "config.json"
    secured_paths: list[Path] = []

    def secure(path: Path) -> None:
        assert path.exists()
        assert path != target
        secured_paths.append(path)
        if os.name != "nt":
            path.chmod(0o600)

    monkeypatch.setattr(storage_module, "set_private_file_permissions", secure)

    FileSessionStorage(str(target)).save("c_user=123; xs=secret;")

    assert len(secured_paths) == 1
    assert target.exists()
    if os.name != "nt":
        assert stat.S_IMODE(target.stat().st_mode) == 0o600


@pytest.mark.skipif(os.name != "nt", reason="Windows ACL regression")
def test_file_storage_replacement_keeps_private_windows_acl(tmp_path: Path) -> None:
    target = tmp_path / "config.json"
    target.write_text("{}", encoding="utf-8")
    subprocess.run(
        ["icacls.exe", str(target), "/grant", "*S-1-1-0:(R)"],
        check=True,
        capture_output=True,
        text=True,
    )

    FileSessionStorage(str(target)).save("c_user=123; xs=secret;")

    acl_env = _private_acl_environment(target)
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
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
