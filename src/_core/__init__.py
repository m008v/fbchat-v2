"""
Đường dẫn file:
  src/_core/__init__.py

Mục đích:
  - Export các component cốt lõi của module _core.

Cách hoạt động:
  - Nạp dependency/guard cần thiết, thực hiện các async HTTP requests tới API nội bộ hoặc GraphQL của Facebook.
  - Các thao tác request đều phải thông qua httpx.AsyncClient và module _core._utils để bảo đảm an toàn kết nối.
  - Payload gửi đi/nhận về được xử lý JSON cẩn thận, bắt lỗi try-except đầy đủ để tránh crash hệ thống.

File liên quan:
  - src/main.py và các entrypoint khác.
  - Phụ thuộc vào _core._session, _core._utils để khởi tạo và thao tác HTTP.

Author: @m008v (MinhHuyDev)
"""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("fbchat-v2")
except PackageNotFoundError:
    __version__ = "2.2.0"

__all__ = ["_session", "_utils", "_facebookLogin", "__version__"]
