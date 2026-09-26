from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from fbchat_v2.service import create_app, readiness_report


def test_health_endpoint_contains_no_runtime_configuration() -> None:
    response = TestClient(create_app()).get("/healthz")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert set(response.json()) == {"status", "service", "version"}


def test_readiness_allows_regular_only_mode(monkeypatch) -> None:
    monkeypatch.delenv("FBCHAT_E2EE_BIN", raising=False)
    monkeypatch.delenv("FBCHAT_E2EE_REQUIRED", raising=False)

    response = TestClient(create_app()).get("/readyz")

    assert response.status_code == 200
    assert response.json()["checks"]["e2ee_bridge"]["configured"] is False


def test_readiness_rejects_missing_required_bridge(monkeypatch, tmp_path: Path) -> None:
    missing = tmp_path / "missing-bridge"
    monkeypatch.setenv("FBCHAT_E2EE_BIN", str(missing))
    monkeypatch.setenv("FBCHAT_E2EE_REQUIRED", "true")

    report = readiness_report()

    assert report["status"] == "not_ready"
    assert report["checks"]["e2ee_bridge"]["executable"] is False


def test_readiness_accepts_executable_bridge(monkeypatch, tmp_path: Path) -> None:
    bridge = tmp_path / "bridge"
    bridge.write_text("bridge", encoding="utf-8")
    bridge.chmod(0o700)
    monkeypatch.setenv("FBCHAT_E2EE_BIN", str(bridge))
    monkeypatch.setenv("FBCHAT_E2EE_REQUIRED", "true")

    report = readiness_report()

    assert report["status"] == "ready"
    assert report["checks"]["e2ee_bridge"]["executable"] is True
