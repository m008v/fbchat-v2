"""
Media storage and staging module for fbchat-v2 provider.

Enforces SocialManager media boundary:
- Stable, opaque mediaId (never internal Facebook CDN or disk paths).
- MIME-type whitelisting and payload size limits.
- Local secure staging in FBCHAT_STATE_DIR/media.
- Sanitized public DTOs.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB

ALLOWED_MIME_TYPES = {
    # Images
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    # Audio
    "audio/mpeg",
    "audio/ogg",
    "audio/mp4",
    "audio/wav",
    "audio/aac",
    # Video
    "video/mp4",
    "video/webm",
    "video/quicktime",
    # Documents
    "application/pdf",
    "text/plain",
    "application/zip",
}

_SAFE_FILENAME_RE = re.compile(r"[^a-zA-Z0-9_.-]")


class MediaError(Exception):
    """Base error for media storage operations."""


class MediaNotFoundError(MediaError):
    """Requested mediaId does not exist."""


class MediaValidationError(MediaError):
    """Media exceeds size limits or has disallowed MIME type."""


@dataclass(frozen=True)
class MediaRecord:
    media_id: str
    file_name: str
    mime_type: str
    size_bytes: int
    sha256: str
    created_at: str

    def public(self) -> dict[str, Any]:
        return {
            "mediaId": self.media_id,
            "fileName": self.file_name,
            "mimeType": self.mime_type,
            "sizeBytes": self.size_bytes,
            "sha256": self.sha256,
            "createdAt": self.created_at,
        }


class MediaStorage:
    """Manages local media staging with size limits and MIME validation."""

    def __init__(
        self,
        state_dir: Path | None = None,
        max_file_size: int = DEFAULT_MAX_FILE_SIZE_BYTES,
        allowed_types: set[str] | None = None,
    ) -> None:
        base = state_dir or Path(
            os.environ.get("FBCHAT_STATE_DIR", "/tmp/fbchat-state")
        )
        self._media_dir = Path(base) / "media"
        self._media_dir.mkdir(parents=True, exist_ok=True)
        self._max_file_size = max_file_size
        self._allowed_types = set(allowed_types or ALLOWED_MIME_TYPES)

    @property
    def media_dir(self) -> Path:
        return self._media_dir

    def _sanitize_filename(self, filename: str) -> str:
        clean = Path(filename).name
        clean = _SAFE_FILENAME_RE.sub("_", clean)
        return clean or "unnamed_media.bin"

    def store(
        self,
        content: bytes,
        filename: str,
        mime_type: str | None = None,
    ) -> MediaRecord:
        if len(content) > self._max_file_size:
            raise MediaValidationError(
                f"File size ({len(content)} bytes) exceeds limit of {self._max_file_size} bytes."
            )
        if len(content) == 0:
            raise MediaValidationError("Empty file is not permitted.")

        inferred_mime = mime_type
        if not inferred_mime or inferred_mime == "application/octet-stream":
            guessed, _ = mimetypes.guess_type(filename)
            inferred_mime = guessed or "application/octet-stream"

        if inferred_mime.lower() not in self._allowed_types:
            raise MediaValidationError(
                f"MIME type '{inferred_mime}' is not permitted. Allowed: {sorted(self._allowed_types)}"
            )

        media_id = f"med_{uuid.uuid4().hex[:16]}"
        safe_name = self._sanitize_filename(filename)
        sha256 = hashlib.sha256(content).hexdigest()
        now = datetime.now(timezone.utc).isoformat()

        record = MediaRecord(
            media_id=media_id,
            file_name=safe_name,
            mime_type=inferred_mime.lower(),
            size_bytes=len(content),
            sha256=sha256,
            created_at=now,
        )

        item_dir = self._media_dir / media_id
        item_dir.mkdir(parents=True, exist_ok=True)

        meta_path = item_dir / "meta.json"
        data_path = item_dir / safe_name

        data_path.write_bytes(content)
        meta_path.write_text(json.dumps(asdict(record)), encoding="utf-8")

        return record

    def get(self, media_id: str) -> tuple[MediaRecord, Path]:
        record = self.get_info(media_id)
        item_dir = self._media_dir / media_id
        data_path = item_dir / record.file_name
        if not data_path.exists():
            raise MediaNotFoundError(f"Media payload file for '{media_id}' is missing.")
        return record, data_path

    def get_info(self, media_id: str) -> MediaRecord:
        # Prevent traversal
        clean_id = Path(media_id).name
        item_dir = self._media_dir / clean_id
        meta_path = item_dir / "meta.json"
        if not meta_path.exists():
            raise MediaNotFoundError(f"Media item '{media_id}' not found.")
        try:
            raw = json.loads(meta_path.read_text(encoding="utf-8"))
            return MediaRecord(
                media_id=raw["media_id"],
                file_name=raw["file_name"],
                mime_type=raw["mime_type"],
                size_bytes=int(raw["size_bytes"]),
                sha256=raw["sha256"],
                created_at=raw["created_at"],
            )
        except Exception as exc:
            raise MediaError(
                f"Failed to read metadata for '{media_id}': {exc}"
            ) from exc

    def list_all(self, limit: int = 50) -> list[MediaRecord]:
        results: list[MediaRecord] = []
        if not self._media_dir.exists():
            return results
        for child in sorted(self._media_dir.iterdir(), reverse=True):
            if child.is_dir() and (child / "meta.json").exists():
                try:
                    record = self.get_info(child.name)
                    results.append(record)
                    if len(results) >= limit:
                        break
                except Exception:
                    continue
        return results

    def delete(self, media_id: str) -> bool:
        clean_id = Path(media_id).name
        item_dir = self._media_dir / clean_id
        if not item_dir.exists():
            return False
        meta_path = item_dir / "meta.json"
        if meta_path.exists():
            try:
                record = self.get_info(clean_id)
                data_path = item_dir / record.file_name
                if data_path.exists():
                    data_path.unlink()
            except Exception:
                pass
            meta_path.unlink(missing_ok=True)
        try:
            item_dir.rmdir()
        except OSError:
            pass
        return True
