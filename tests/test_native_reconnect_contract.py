from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from scripts import smoke_bridge_rpc


def _responses(*, structured: bool) -> str:
    capabilities = sorted(smoke_bridge_rpc.REQUIRED_CAPABILITIES)
    if not structured:
        capabilities.remove("structuredConnectionStatus")
    replies = [
        {
            "id": 1,
            "ok": True,
            "data": {
                "protocolVersion": 1,
                "bridgeVersion": "2.3.4",
                "capabilities": capabilities,
            },
        },
        {
            "id": 2,
            "ok": True,
            "data": {
                "connected": False,
                "e2eeConnected": False,
                "nativeReconnecting": False,
            },
        },
        {"id": 3, "ok": False, "error": "unknown method"},
        {"id": 4, "ok": True, "data": {}},
    ]
    return "\n".join(json.dumps(reply) for reply in replies)


@pytest.mark.parametrize("structured", [True, False])
def test_native_smoke_requires_the_current_reconnect_contract(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, structured: bool
) -> None:
    binary = tmp_path / "offline-placeholder.exe"
    binary.touch()
    run = Mock(
        return_value=subprocess.CompletedProcess(
            args=[], returncode=0, stdout=_responses(structured=structured), stderr=""
        )
    )
    monkeypatch.setattr(smoke_bridge_rpc.subprocess, "run", run)
    if structured:
        smoke_bridge_rpc.smoke_bridge(binary, expected_version="2.3.4")
    else:
        with pytest.raises(RuntimeError, match="structuredConnectionStatus"):
            smoke_bridge_rpc.smoke_bridge(binary, expected_version="2.3.4")
    assert run.call_count == 1
