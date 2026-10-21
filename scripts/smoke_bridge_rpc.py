"""Run a credential-free smoke test against the native bridge JSON-RPC process."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REQUIRED_CAPABILITIES = frozenset(
    {
        "newClient",
        "connect",
        "connectE2EE",
        "isConnected",
        "events",
        "structuredConnectionStatus",
    }
)


def _configure_console_encoding() -> None:
    """Keep Vietnamese diagnostics printable in legacy Windows terminals."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="backslashreplace")


def _decode_responses(stdout: str) -> dict[int, dict[str, Any]]:
    responses: dict[int, dict[str, Any]] = {}
    for line_number, raw_line in enumerate(stdout.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Bridge trả về JSON không hợp lệ ở dòng {line_number}"
            ) from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("id"), int):
            raise RuntimeError(
                f"Bridge trả về response không có request id ở dòng {line_number}"
            )
        request_id = payload["id"]
        if request_id in responses:
            raise RuntimeError(f"Bridge trả về request id trùng: {request_id}")
        responses[request_id] = payload
    return responses


def smoke_bridge(
    binary: Path,
    *,
    expected_version: str,
    timeout: float = 15.0,
) -> None:
    """Exercise process startup, success/error responses, and graceful EOF exit."""
    binary = binary.resolve()
    if not binary.is_file():
        raise FileNotFoundError(f"Không tìm thấy bridge binary: {binary}")

    requests = (
        {"id": 1, "method": "hello", "params": {}},
        {"id": 2, "method": "isConnected", "params": {}},
        {"id": 3, "method": "__ci_unknown_method__", "params": {}},
        {"id": 4, "method": "disconnect", "params": {}},
    )
    stdin = "".join(json.dumps(item, separators=(",", ":")) + "\n" for item in requests)

    try:
        completed = subprocess.run(
            [str(binary)],
            input=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"Bridge không thoát sau {timeout:.1f} giây khi stdin đã đóng"
        ) from exc

    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        detail = f": {stderr}" if stderr else ""
        raise RuntimeError(f"Bridge thoát với mã {completed.returncode}{detail}")

    responses = _decode_responses(completed.stdout)
    if set(responses) != {1, 2, 3, 4}:
        raise RuntimeError(
            "Bridge phải trả về đủ request id 1, 2, 3, 4; "
            f"nhận được {sorted(responses)}"
        )

    hello = responses[1]
    hello_data = hello.get("data")
    if hello.get("ok") is not True or not isinstance(hello_data, dict):
        raise RuntimeError(f"Response hello không đúng contract: {hello!r}")
    if hello_data.get("protocolVersion") != 1:
        raise RuntimeError(f"Bridge protocol version không tương thích: {hello_data!r}")
    if hello_data.get("bridgeVersion") != expected_version:
        raise RuntimeError(
            "Bridge version không khớp package: "
            f"{hello_data.get('bridgeVersion')!r} != {expected_version!r}"
        )
    capabilities = hello_data.get("capabilities")
    if not isinstance(capabilities, list) or not all(
        isinstance(item, str) for item in capabilities
    ):
        raise RuntimeError(f"Bridge capabilities không hợp lệ: {capabilities!r}")
    missing = REQUIRED_CAPABILITIES.difference(capabilities)
    if missing:
        raise RuntimeError(f"Bridge thiếu capabilities: {sorted(missing)}")

    status = responses[2]
    if status.get("ok") is not True or status.get("data") != {
        "connected": False,
        "e2eeConnected": False,
        "nativeReconnecting": False,
    }:
        raise RuntimeError(f"Response isConnected không đúng contract: {status!r}")

    unknown = responses[3]
    if (
        unknown.get("ok") is not False
        or "unknown method" not in str(unknown.get("error", "")).lower()
    ):
        raise RuntimeError(f"Response unknown-method không đúng contract: {unknown!r}")

    disconnected = responses[4]
    if disconnected.get("ok") is not True or disconnected.get("data") != {}:
        raise RuntimeError(f"Response disconnect không đúng contract: {disconnected!r}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "binary", type=Path, help="Đường dẫn tới bridge binary cần test"
    )
    parser.add_argument(
        "--expected-version",
        required=True,
        help="Package version mà RPC hello phải trả về",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="Số giây tối đa chờ bridge xử lý và thoát (mặc định: 15)",
    )
    return parser.parse_args()


def main() -> int:
    _configure_console_encoding()
    args = parse_args()
    smoke_bridge(
        args.binary,
        expected_version=args.expected_version,
        timeout=args.timeout,
    )
    print("Native bridge JSON-RPC smoke test: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
