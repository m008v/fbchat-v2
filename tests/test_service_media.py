from __future__ import annotations

from pathlib import Path

import pytest

from fbchat_v2.service_media import (
    MediaNotFoundError,
    MediaStorage,
    MediaValidationError,
)


def test_media_storage_stores_valid_file(tmp_path: Path) -> None:
    storage = MediaStorage(state_dir=tmp_path)
    sample_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    record = storage.store(sample_png, filename="avatar.png", mime_type="image/png")

    assert record.media_id.startswith("med_")
    assert record.file_name == "avatar.png"
    assert record.mime_type == "image/png"
    assert record.size_bytes == len(sample_png)
    assert len(record.sha256) == 64

    public_dto = record.public()
    assert set(public_dto.keys()) == {
        "mediaId",
        "fileName",
        "mimeType",
        "sizeBytes",
        "sha256",
        "createdAt",
    }
    # Security: No internal path leaked
    assert "path" not in public_dto
    assert str(tmp_path) not in str(public_dto)


def test_media_storage_rejects_disallowed_mime_type(tmp_path: Path) -> None:
    storage = MediaStorage(state_dir=tmp_path)
    with pytest.raises(MediaValidationError, match="MIME type"):
        storage.store(
            b"MZ\x90\x00", filename="malware.exe", mime_type="application/x-msdownload"
        )


def test_media_storage_rejects_empty_file(tmp_path: Path) -> None:
    storage = MediaStorage(state_dir=tmp_path)
    with pytest.raises(MediaValidationError, match="Empty file"):
        storage.store(b"", filename="empty.txt", mime_type="text/plain")


def test_media_storage_enforces_size_limit(tmp_path: Path) -> None:
    storage = MediaStorage(state_dir=tmp_path, max_file_size=100)
    with pytest.raises(MediaValidationError, match="exceeds limit"):
        storage.store(b"a" * 150, filename="large.txt", mime_type="text/plain")


def test_media_storage_retrieves_and_deletes(tmp_path: Path) -> None:
    storage = MediaStorage(state_dir=tmp_path)
    content = b"PDF dummy content"
    record = storage.store(content, filename="doc.pdf", mime_type="application/pdf")

    retrieved, path = storage.get(record.media_id)
    assert retrieved.media_id == record.media_id
    assert path.read_bytes() == content

    info = storage.get_info(record.media_id)
    assert info.media_id == record.media_id

    listed = storage.list_all()
    assert any(m.media_id == record.media_id for m in listed)

    deleted = storage.delete(record.media_id)
    assert deleted is True

    with pytest.raises(MediaNotFoundError):
        storage.get(record.media_id)


def test_media_storage_prevents_traversal(tmp_path: Path) -> None:
    storage = MediaStorage(state_dir=tmp_path)
    with pytest.raises(MediaNotFoundError):
        storage.get("../../../something")
