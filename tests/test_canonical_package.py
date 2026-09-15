from __future__ import annotations

import ast
import base64
import csv
import hashlib
import importlib
import io
import stat
import tarfile
import zipfile
from pathlib import Path

import pytest

from scripts.verify_distribution import (
    ALLOWED_WHEEL_MEMBERS,
    EXPECTED_SDIST_ROOT,
    REQUIRED_SDIST_MEMBERS,
    WHEEL_DIST_INFO_ROOT,
    verify_sdist,
    verify_wheel,
)
from scripts.sync_canonical_package import (
    PROJECT_ROOT,
    SOURCE_PACKAGES,
    TARGET_ROOT,
    expected_snapshot,
    is_link_like_stat,
    rewrite_documentation,
    rewrite_imports,
    snapshot_differences,
    sync_snapshot,
)


def _legacy_runtime_imports(source: str) -> list[str]:
    imports: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.partition(".")[0] in SOURCE_PACKAGES:
                imports.append(node.module)
        elif isinstance(node, ast.Import):
            imports.extend(
                alias.name
                for alias in node.names
                if alias.name.partition(".")[0] in SOURCE_PACKAGES
            )
    return imports


def test_canonical_snapshot_is_current() -> None:
    assert snapshot_differences() == []


@pytest.mark.parametrize("relative_name", [".env", "_core/config.json"])
def test_snapshot_rejects_unknown_package_files(
    tmp_path: Path, relative_name: str
) -> None:
    target_root = tmp_path / "fbchat_v2"
    generated = target_root / "_core" / "module.py"
    generated.parent.mkdir(parents=True)
    generated.write_text("generated\n", encoding="utf-8")
    manual_files = {
        target_root / "__init__.py",
        target_root / "py.typed",
    }
    for path in manual_files:
        path.write_text("manual\n", encoding="utf-8")
    leaked = target_root / relative_name
    leaked.parent.mkdir(parents=True, exist_ok=True)
    leaked.write_text("not-a-secret\n", encoding="utf-8")

    differences = snapshot_differences(
        {generated: "generated\n"},
        target_root=target_root,
        manual_target_files=manual_files,
    )

    assert len(differences) == 1
    assert differences[0].startswith("unexpected file: ")
    assert differences[0].endswith(leaked.relative_to(target_root).as_posix())


def test_snapshot_ignores_only_python_bytecode_cache(tmp_path: Path) -> None:
    target_root = tmp_path / "fbchat_v2"
    generated = target_root / "_core" / "module.py"
    generated.parent.mkdir(parents=True)
    generated.write_text("generated\n", encoding="utf-8")
    manual_files = {
        target_root / "__init__.py",
        target_root / "py.typed",
    }
    for path in manual_files:
        path.write_text("manual\n", encoding="utf-8")
    cache_file = target_root / "_core" / "__pycache__" / "module.pyc"
    cache_file.parent.mkdir()
    cache_file.write_bytes(b"bytecode")

    assert (
        snapshot_differences(
            {generated: "generated\n"},
            target_root=target_root,
            manual_target_files=manual_files,
        )
        == []
    )


def test_source_scanner_recognizes_symlink_and_windows_reparse_point() -> None:
    assert is_link_like_stat(stat.S_IFLNK | 0o777)
    assert is_link_like_stat(stat.S_IFREG | 0o644, 0x400)
    assert not is_link_like_stat(stat.S_IFREG | 0o644)


def test_sync_refuses_to_delete_unknown_file(tmp_path: Path) -> None:
    target_root = tmp_path / "fbchat_v2"
    target_root.mkdir()
    leaked = target_root / "keep-me.json"
    leaked.write_text("preserve me\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Refusing to overwrite or delete"):
        sync_snapshot(
            {},
            target_root=target_root,
            manual_target_files=set(),
        )

    assert leaked.read_text(encoding="utf-8") == "preserve me\n"


def test_rewrite_imports_handles_supported_absolute_forms() -> None:
    source = (
        "from _core._utils import formAll\n"
        "from _features import _facebook\n"
        "import os, _messaging._send as sender\n"
    )

    rewritten = rewrite_imports(source, Path("module.py"))

    assert "from fbchat_v2._core._utils import formAll" in rewritten
    assert "from fbchat_v2._features import _facebook" in rewritten
    assert "import os, fbchat_v2._messaging._send as sender" in rewritten
    assert _legacy_runtime_imports(rewritten) == []


def test_generated_modules_have_no_legacy_runtime_imports() -> None:
    for path, source in expected_snapshot().items():
        if path.suffix != ".py":
            continue
        assert _legacy_runtime_imports(source) == [], path.relative_to(PROJECT_ROOT)


def test_rewrite_documentation_changes_only_paths_and_import_examples() -> None:
    source = (
        "`_core` remains a historical architecture label.\n"
        "See `src/_core/_session.py`.\n"
        "from _core._session import dataGetHome\n"
    )

    rewritten = rewrite_documentation(source)

    assert "`_core` remains a historical architecture label." in rewritten
    assert "`src/fbchat_v2/_core/_session.py`" in rewritten
    assert "from fbchat_v2._core._session import dataGetHome" in rewritten


def test_public_exports_come_from_canonical_snapshot() -> None:
    package = importlib.import_module("fbchat_v2")
    nested = importlib.import_module("fbchat_v2._features._facebook._get_user_info")

    assert package.dataGetHome.__module__ == "fbchat_v2._core._session"
    assert package.listeningEvent.__module__ == "fbchat_v2._messaging._listening"
    assert package.__license__ == "Apache-2.0"
    assert nested.func.__module__ == nested.__name__
    for module in (package, nested):
        module_path = Path(module.__file__).resolve()
        assert module_path.is_relative_to(TARGET_ROOT.resolve())


def test_canonical_e2ee_paths_resolve_source_checkout() -> None:
    module = importlib.import_module("fbchat_v2._messaging._listening_e2ee")

    assert module._is_source_checkout() is True
    assert module._default_binary_path().parent == PROJECT_ROOT / "build"
    assert module._source_bridge_inputs()


def test_canonical_e2ee_install_uses_versioned_cache(
    tmp_path: Path, monkeypatch
) -> None:
    module = importlib.import_module("fbchat_v2._messaging._listening_e2ee")
    installed_module = (
        tmp_path / "site-packages" / "fbchat_v2" / "_messaging" / "_listening_e2ee.py"
    )
    cache_root = tmp_path / "cache"
    monkeypatch.setattr(module, "__file__", str(installed_module))
    monkeypatch.setenv("LOCALAPPDATA", str(cache_root))
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache_root))

    assert module._is_source_checkout() is False
    assert module._default_binary_path() == (
        cache_root
        / "fbchat-v2"
        / "bridge"
        / f"v{module._PACKAGE_VERSION}"
        / module._binary_name()
    )


def _write_test_sdist(
    path: Path,
    extra_members: set[str] | None = None,
    *,
    symlink_member: str | None = None,
    pkg_info_name: str = "fbchat-v2",
    pkg_info_version: str = "2.3.2",
) -> None:
    members = REQUIRED_SDIST_MEMBERS | (extra_members or set())
    with tarfile.open(path, mode="w:gz") as archive:
        for member_name in sorted(members):
            if member_name == "PKG-INFO":
                payload = (
                    "Metadata-Version: 2.4\n"
                    f"Name: {pkg_info_name}\n"
                    f"Version: {pkg_info_version}\n\n"
                ).encode("utf-8")
            else:
                payload = b"test\n"
            info = tarfile.TarInfo(f"{EXPECTED_SDIST_ROOT}/{member_name}")
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
        if symlink_member is not None:
            info = tarfile.TarInfo(f"{EXPECTED_SDIST_ROOT}/{symlink_member}")
            info.type = tarfile.SYMTYPE
            info.linkname = "../../outside"
            archive.addfile(info)


def _write_test_wheel(
    path: Path,
    extra_members: set[str] | None = None,
    *,
    record_fault: str | None = None,
) -> None:
    members = ALLOWED_WHEEL_MEMBERS | (extra_members or set())
    record_path = f"{WHEEL_DIST_INFO_ROOT}/RECORD"
    payloads: dict[str, bytes] = {}
    for member_name in sorted(members - {record_path}):
        if member_name == f"{WHEEL_DIST_INFO_ROOT}/METADATA":
            payload = (
                "Metadata-Version: 2.4\nName: fbchat-v2\nVersion: 2.3.2\n\n"
            ).encode("utf-8")
        else:
            payload = b"test\n"
        payloads[member_name] = payload

    record_buffer = io.StringIO(newline="")
    record_writer = csv.writer(record_buffer, lineterminator="\n")
    fault_target = "fbchat_v2/__init__.py"
    for member_name, payload in sorted(payloads.items()):
        digest = base64.urlsafe_b64encode(hashlib.sha256(payload).digest())
        record_hash = "sha256=" + digest.rstrip(b"=").decode("ascii")
        record_size = str(len(payload))
        if member_name == fault_target and record_fault == "hash":
            record_hash = "sha256=invalid"
        if member_name == fault_target and record_fault == "size":
            record_size = str(len(payload) + 1)
        record_writer.writerow((member_name, record_hash, record_size))
    record_writer.writerow((record_path, "", ""))
    payloads[record_path] = record_buffer.getvalue().encode("utf-8")

    with zipfile.ZipFile(path, mode="w") as archive:
        for member_name, payload in sorted(payloads.items()):
            archive.writestr(member_name, payload)


def test_sdist_allowlist_accepts_only_canonical_sources(tmp_path: Path) -> None:
    sdist = tmp_path / "fbchat_v2-test.tar.gz"
    _write_test_sdist(sdist)

    verify_sdist(sdist)


def test_sdist_allowlist_rejects_legacy_source(tmp_path: Path) -> None:
    sdist = tmp_path / "fbchat_v2-test.tar.gz"
    _write_test_sdist(sdist, {"src/_core/__init__.py"})

    with pytest.raises(RuntimeError, match="ngoài allowlist"):
        verify_sdist(sdist)


@pytest.mark.parametrize(
    "extra_member",
    ["src/fbchat_v2/.env", "src/fbchat_v2/config.json"],
)
def test_sdist_allowlist_rejects_unknown_canonical_file(
    tmp_path: Path, extra_member: str
) -> None:
    sdist = tmp_path / "fbchat_v2-test.tar.gz"
    _write_test_sdist(sdist, {extra_member})

    with pytest.raises(RuntimeError, match="ngoài allowlist"):
        verify_sdist(sdist)


def test_sdist_allowlist_rejects_symlink(tmp_path: Path) -> None:
    sdist = tmp_path / "fbchat_v2-test.tar.gz"
    _write_test_sdist(sdist, symlink_member="src/fbchat_v2/escape")

    with pytest.raises(RuntimeError, match="không phải file thường"):
        verify_sdist(sdist)


@pytest.mark.parametrize(
    ("name", "version", "message"),
    [
        ("wrong-name", "2.3.2", "Tên distribution"),
        ("fbchat-v2", "9.9.9", "Version trong sdist"),
    ],
)
def test_sdist_rejects_wrong_pkg_info(
    tmp_path: Path, name: str, version: str, message: str
) -> None:
    sdist = tmp_path / "fbchat_v2-test.tar.gz"
    _write_test_sdist(
        sdist,
        pkg_info_name=name,
        pkg_info_version=version,
    )

    with pytest.raises(RuntimeError, match=message):
        verify_sdist(sdist)


def test_sdist_rejects_unicode_path_collision(tmp_path: Path) -> None:
    sdist = tmp_path / "fbchat_v2-test.tar.gz"
    _write_test_sdist(
        sdist,
        {
            "src/fbchat_v2/café.py",
            "src/fbchat_v2/cafe\u0301.py",
        },
    )

    with pytest.raises(RuntimeError, match="trùng Unicode/case"):
        verify_sdist(sdist)


def test_wheel_allowlist_accepts_exact_canonical_files(tmp_path: Path) -> None:
    wheel = tmp_path / "fbchat_v2-test.whl"
    _write_test_wheel(wheel)

    verify_wheel(wheel)


@pytest.mark.parametrize("extra_member", ["fbchat_v2/.env", "fbchat_v2/config.json"])
def test_wheel_allowlist_rejects_unknown_canonical_file(
    tmp_path: Path, extra_member: str
) -> None:
    wheel = tmp_path / "fbchat_v2-test.whl"
    _write_test_wheel(wheel, {extra_member})

    with pytest.raises(RuntimeError, match="ngoài allowlist"):
        verify_wheel(wheel)


def test_wheel_allowlist_rejects_symlink(tmp_path: Path) -> None:
    wheel = tmp_path / "fbchat_v2-test.whl"
    _write_test_wheel(wheel)
    with zipfile.ZipFile(wheel, mode="a") as archive:
        info = zipfile.ZipInfo("fbchat_v2/escape")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(info, "../../outside")

    with pytest.raises(RuntimeError, match="symbolic link"):
        verify_wheel(wheel)


@pytest.mark.parametrize(
    ("fault", "message"),
    [("hash", "SHA-256"), ("size", "size")],
)
def test_wheel_rejects_invalid_record(tmp_path: Path, fault: str, message: str) -> None:
    wheel = tmp_path / "fbchat_v2-test.whl"
    _write_test_wheel(wheel, record_fault=fault)

    with pytest.raises(RuntimeError, match=message):
        verify_wheel(wheel)


def test_wheel_rejects_non_regular_entry(tmp_path: Path) -> None:
    wheel = tmp_path / "fbchat_v2-test.whl"
    _write_test_wheel(wheel)
    with zipfile.ZipFile(wheel, mode="a") as archive:
        info = zipfile.ZipInfo("fbchat_v2/fifo")
        info.create_system = 3
        info.external_attr = (stat.S_IFIFO | 0o644) << 16
        archive.writestr(info, b"")

    with pytest.raises(RuntimeError, match="không phải file thường"):
        verify_wheel(wheel)


def test_wheel_rejects_casefold_path_collision(tmp_path: Path) -> None:
    wheel = tmp_path / "fbchat_v2-test.whl"
    _write_test_wheel(wheel, {"fbchat_v2/Leak.py", "fbchat_v2/leak.py"})

    with pytest.raises(RuntimeError, match="trùng Unicode/case"):
        verify_wheel(wheel)
