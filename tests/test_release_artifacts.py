from __future__ import annotations

import io
import tarfile
import zipfile
from pathlib import Path

import pytest
from scripts.release_artifacts import (
    CHECKSUM_MODULE_MEMBER,
    EXPECTED_BINARY_NAMES,
    bind_checksums,
    collect_binary_digests,
    render_checksum_module,
    validate_release_tag,
    verify_distributions,
    verify_manifest,
)


def test_public_namespace_exports_package_and_nested_feature() -> None:
    import fbchat_v2
    from fbchat_v2._features._facebook._get_user_info import func

    assert fbchat_v2.__version__ == "2.3.2"
    assert callable(fbchat_v2.dataGetHome)
    assert callable(fbchat_v2.listeningE2EEEvent)
    assert callable(func)


def _write_binaries(directory: Path) -> dict[str, str]:
    directory.mkdir()
    for index, name in enumerate(sorted(EXPECTED_BINARY_NAMES), start=1):
        (directory / name).write_bytes(f"binary-{index}".encode())
    return collect_binary_digests(directory)


def _write_distributions(dist_dir: Path, checksum_source: str) -> None:
    dist_dir.mkdir()
    with zipfile.ZipFile(dist_dir / "fbchat_v2-2.3.2-py3-none-any.whl", "w") as wheel:
        wheel.writestr(CHECKSUM_MODULE_MEMBER, checksum_source)

    payload = checksum_source.encode()
    with tarfile.open(dist_dir / "fbchat_v2-2.3.2.tar.gz", "w:gz") as sdist:
        info = tarfile.TarInfo(f"fbchat_v2-2.3.2/src/{CHECKSUM_MODULE_MEMBER}")
        info.size = len(payload)
        sdist.addfile(info, io.BytesIO(payload))


def test_bind_and_verify_final_distributions(tmp_path: Path) -> None:
    binaries = tmp_path / "binaries"
    expected = _write_binaries(binaries)
    module = tmp_path / "source" / "_bridge_checksums.py"
    manifest = binaries / "SHA256SUMS"

    assert bind_checksums(binaries, module, manifest, version="2.3.2") == expected
    assert manifest.read_text(encoding="ascii").splitlines() == [
        f"{digest}  {name}" for name, digest in sorted(expected.items())
    ]

    dist = tmp_path / "dist"
    _write_distributions(dist, module.read_text(encoding="utf-8"))
    wheel, sdist = verify_distributions(
        binaries, dist, version="2.3.2", manifest_path=manifest
    )
    assert wheel.suffix == ".whl"
    assert sdist.name.endswith(".tar.gz")


def test_verify_rejects_checksum_drift(tmp_path: Path) -> None:
    binaries = tmp_path / "binaries"
    digests = _write_binaries(binaries)
    module = tmp_path / "source" / "_bridge_checksums.py"
    manifest = binaries / "SHA256SUMS"
    bind_checksums(binaries, module, manifest, version="2.3.2")
    stale = dict(digests)
    stale[sorted(stale)[0]] = "0" * 64
    dist = tmp_path / "dist"
    _write_distributions(dist, render_checksum_module("2.3.2", stale))

    with pytest.raises(RuntimeError, match="checksum không khớp"):
        verify_distributions(binaries, dist, version="2.3.2", manifest_path=manifest)


def test_verify_manifest_rejects_tampering(tmp_path: Path) -> None:
    binaries = tmp_path / "binaries"
    digests = _write_binaries(binaries)
    manifest = binaries / "SHA256SUMS"
    manifest.write_text(
        "".join(f"{'0' * 64}  {name}\n" for name in sorted(digests)),
        encoding="ascii",
    )

    with pytest.raises(RuntimeError, match="manifest không khớp"):
        verify_manifest(manifest, digests)


def test_collect_binary_digests_requires_exact_platform_set(tmp_path: Path) -> None:
    binaries = tmp_path / "binaries"
    _write_binaries(binaries)
    (binaries / sorted(EXPECTED_BINARY_NAMES)[0]).unlink()
    (binaries / "fbchat-bridge-e2ee-plan9-amd64").write_bytes(b"nope")

    with pytest.raises(RuntimeError, match=r"thiếu:.*thừa:"):
        collect_binary_digests(binaries)


def test_validate_release_tag_requires_exact_project_version() -> None:
    validate_release_tag("v2.3.2", "2.3.2")
    with pytest.raises(RuntimeError, match="không khớp"):
        validate_release_tag("v2.2.1", "2.3.2")
