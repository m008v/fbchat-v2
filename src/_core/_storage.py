"""
Đường dẫn file:
  src/_core/_storage.py

Mục đích:
  - Cung cấp module cho thư viện fbchat-v2 (phiên bản async).
  - Comment đầu file giúp developer dễ dàng theo dõi vị trí, luồng xử lý và dữ liệu của tính năng.

Cách hoạt động:
  - Nạp dependency/guard cần thiết, thực hiện các async HTTP requests tới API nội bộ hoặc GraphQL của Facebook.
  - Các thao tác request đều phải thông qua httpx.AsyncClient và module _core._utils để bảo đảm an toàn kết nối.
  - Payload gửi đi/nhận về được xử lý JSON cẩn thận, bắt lỗi try-except đầy đủ để tránh crash hệ thống.

File liên quan:
  - src/main.py và các entrypoint khác.
  - Phụ thuộc vào _core._session, _core._utils để khởi tạo và thao tác HTTP.
"""

from __future__ import annotations

import json
import os
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class SessionStorage(ABC):
    @abstractmethod
    def load(self) -> str | None:
        """Đọc cookie hoặc trả về None."""

    @abstractmethod
    def save(self, cookies: str) -> None:
        """Lưu cookie."""

    @abstractmethod
    def clear(self) -> None:
        """Xóa cookie đã lưu."""


class FileSessionStorage(SessionStorage):
    """JSON storage ghi atomically để tránh file bị cắt khi tiến trình dừng đột ngột."""

    def __init__(self, filepath: str = "config.json", key: str = "cookies") -> None:
        self.filepath = Path(filepath)
        self.key = key

    def _read_data(self) -> dict[str, Any] | None:
        if not self.filepath.exists():
            return None
        try:
            with self.filepath.open("r", encoding="utf-8") as file_handle:
                data = json.load(file_handle)
        except (json.JSONDecodeError, OSError):
            return None
        return data if isinstance(data, dict) else None

    def _write_data(self, data: dict[str, Any]) -> None:
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.filepath.parent,
                prefix=f".{self.filepath.name}.",
                suffix=".tmp",
                delete=False,
            ) as file_handle:
                temporary_path = Path(file_handle.name)
                json.dump(data, file_handle, indent=2, ensure_ascii=False)
                file_handle.write("\n")
                file_handle.flush()
                os.fsync(file_handle.fileno())
            if os.name != "nt":
                temporary_path.chmod(0o600)
            os.replace(temporary_path, self.filepath)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink(missing_ok=True)

    def load(self) -> str | None:
        data = self._read_data()
        if data is None:
            return None
        value = data.get(self.key)
        return value if isinstance(value, str) and value else None

    def save(self, cookies: str) -> None:
        if not isinstance(cookies, str) or not cookies.strip():
            raise ValueError("Cookie lưu vào storage phải là chuỗi không rỗng.")
        data = self._read_data() or {}
        data[self.key] = cookies
        self._write_data(data)

    def clear(self) -> None:
        data = self._read_data()
        if data is None or self.key not in data:
            return
        del data[self.key]
        self._write_data(data)


class EnvSessionStorage(SessionStorage):
    """Storage dựa trên biến môi trường của tiến trình hiện tại."""

    def __init__(self, env_var: str = "FB_COOKIES") -> None:
        self.env_var = env_var

    def load(self) -> str | None:
        return os.environ.get(self.env_var)

    def save(self, cookies: str) -> None:
        if not isinstance(cookies, str) or not cookies.strip():
            raise ValueError("Cookie lưu vào storage phải là chuỗi không rỗng.")
        os.environ[self.env_var] = cookies

    def clear(self) -> None:
        os.environ.pop(self.env_var, None)
