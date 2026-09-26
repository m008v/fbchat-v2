"""Minimal HTTP process boundary for containerized fbchat-v2 deployments.

Only liveness and readiness are exposed here. Provider operations belong behind
an authenticated application contract and must never expose session material.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from ._core import __version__

SERVICE_NAME = "fbchat-provider"
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in _TRUE_VALUES


def _bridge_check() -> dict[str, Any]:
    configured_path = os.environ.get("FBCHAT_E2EE_BIN", "").strip()
    required = _env_flag("FBCHAT_E2EE_REQUIRED")
    configured = bool(configured_path)
    executable = False

    if configured:
        path = Path(configured_path)
        executable = path.is_file() and os.access(path, os.X_OK)

    ready = executable if required or configured else True
    return {
        "ready": ready,
        "required": required,
        "configured": configured,
        "executable": executable,
    }


def readiness_report() -> dict[str, Any]:
    bridge = _bridge_check()
    return {
        "status": "ready" if bridge["ready"] else "not_ready",
        "service": SERVICE_NAME,
        "version": __version__,
        "checks": {"e2ee_bridge": bridge},
    }


def create_app() -> FastAPI:
    application = FastAPI(
        title="fbchat-v2 provider service",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @application.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        return {
            "status": "ok",
            "service": SERVICE_NAME,
            "version": __version__,
        }

    @application.get("/readyz", include_in_schema=False)
    async def readyz() -> JSONResponse:
        report = readiness_report()
        status_code = 200 if report["status"] == "ready" else 503
        return JSONResponse(report, status_code=status_code)

    return application


app = create_app()
