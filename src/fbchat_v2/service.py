"""Authenticated REST boundary and administration portal for fbchat-v2."""

from __future__ import annotations

import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Annotated, AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from ._core import __version__
from .service_sessions import (
    SessionAuthenticationError,
    SessionNotFoundError,
    SessionRegistry,
)

SERVICE_NAME = "fbchat-provider"
API_VERSION = "v1"
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_PORTAL_PATH = Path(__file__).with_name("portal.html")
_basic_security = HTTPBasic(auto_error=False)


class CookieInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    value: SecretStr


class SessionCreateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(default="Facebook account", min_length=1, max_length=80)
    cookies: list[CookieInput] = Field(min_length=2, max_length=64)


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in _TRUE_VALUES


def _api_auth_report() -> dict[str, Any]:
    required = _env_flag("FBCHAT_API_AUTH_REQUIRED", default=True)
    username_set = bool(os.environ.get("FBCHAT_API_USERNAME", "").strip())
    password_set = bool(os.environ.get("FBCHAT_API_PASSWORD", "").strip())
    configured = username_set and password_set
    return {
        "ready": configured if required else True,
        "required": required,
        "configured": configured,
    }


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
    api_auth = _api_auth_report()
    ready = bridge["ready"] and api_auth["ready"] and _PORTAL_PATH.is_file()
    return {
        "status": "ready" if ready else "not_ready",
        "service": SERVICE_NAME,
        "version": __version__,
        "checks": {
            "e2ee_bridge": bridge,
            "api_auth": api_auth,
            "portal": {"ready": _PORTAL_PATH.is_file()},
        },
    }


def _success(message: str, results: Any = None, status_code: int = 200) -> JSONResponse:
    payload: dict[str, Any] = {"code": "SUCCESS", "message": message}
    if results is not None:
        payload["results"] = results
    return JSONResponse(payload, status_code=status_code)


def _error(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse({"code": code, "message": message}, status_code=status_code)


def create_app(registry: SessionRegistry | None = None) -> FastAPI:
    session_registry = registry or SessionRegistry()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await session_registry.close()

    application = FastAPI(
        title="fbchat-v2 Provider REST API",
        description=(
            "Authenticated provider boundary for Facebook Messenger. Cookies and "
            "provider identifiers are private and never returned by public DTOs."
        ),
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    application.state.session_registry = session_registry

    async def require_auth(
        credentials: Annotated[HTTPBasicCredentials | None, Depends(_basic_security)],
    ) -> None:
        report = _api_auth_report()
        if not report["required"]:
            return
        if not report["configured"]:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="API authentication is required but not configured.",
            )

        expected_username = os.environ["FBCHAT_API_USERNAME"].encode("utf-8")
        expected_password = os.environ["FBCHAT_API_PASSWORD"].encode("utf-8")
        supplied_username = (credentials.username if credentials else "").encode(
            "utf-8"
        )
        supplied_password = (credentials.password if credentials else "").encode(
            "utf-8"
        )
        valid = secrets.compare_digest(supplied_username, expected_username)
        valid = secrets.compare_digest(supplied_password, expected_password) and valid
        if not valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API credentials.",
                headers={"WWW-Authenticate": "Basic"},
            )

    protected = [Depends(require_auth)]

    @application.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, error: HTTPException) -> JSONResponse:
        code = "UNAUTHORIZED" if error.status_code == 401 else "REQUEST_FAILED"
        response = _error(code, str(error.detail), error.status_code)
        if error.headers:
            response.headers.update(error.headers)
        return response

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _: Request, error: RequestValidationError
    ) -> JSONResponse:
        # FastAPI's default error body includes rejected input. That can leak a
        # cookie value, so only field locations and generic messages are returned.
        details = [
            {
                "field": ".".join(str(part) for part in item["loc"] if part != "body"),
                "message": item["msg"],
            }
            for item in error.errors()
        ]
        return JSONResponse(
            {
                "code": "INVALID_REQUEST",
                "message": "The request payload is invalid.",
                "details": details,
            },
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    @application.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "service": SERVICE_NAME, "version": __version__}

    @application.get("/readyz", include_in_schema=False)
    async def readyz() -> JSONResponse:
        report = readiness_report()
        status_code = 200 if report["status"] == "ready" else 503
        return JSONResponse(report, status_code=status_code)

    @application.get("/", dependencies=protected, include_in_schema=False)
    async def portal() -> FileResponse:
        return FileResponse(_PORTAL_PATH, media_type="text/html")

    @application.get("/openapi.json", dependencies=protected, include_in_schema=False)
    async def openapi_schema() -> JSONResponse:
        return JSONResponse(application.openapi())

    @application.get("/docs", dependencies=protected, include_in_schema=False)
    async def swagger_docs() -> Any:
        return get_swagger_ui_html(
            openapi_url="/openapi.json", title="fbchat-v2 Provider API"
        )

    @application.get("/api/v1/app/info", dependencies=protected, tags=["app"])
    async def app_info() -> JSONResponse:
        return _success(
            "Provider service information.",
            {
                "service": SERVICE_NAME,
                "version": __version__,
                "apiVersion": API_VERSION,
                "sessionStorage": "memory",
                "capabilities": ["sessions", "session-validation"],
            },
        )

    @application.get("/api/v1/sessions", dependencies=protected, tags=["sessions"])
    async def list_sessions() -> JSONResponse:
        return _success("Provider sessions.", await session_registry.list_public())

    @application.post(
        "/api/v1/sessions",
        dependencies=protected,
        tags=["sessions"],
        status_code=status.HTTP_201_CREATED,
    )
    async def create_session(payload: SessionCreateInput) -> JSONResponse:
        cookies = [
            (cookie.name, cookie.value.get_secret_value()) for cookie in payload.cookies
        ]
        try:
            public_session = await session_registry.create(
                label=payload.label, cookies=cookies
            )
        except ValueError as error:
            return _error("INVALID_REQUEST", str(error), 400)
        except SessionAuthenticationError:
            return _error(
                "AUTHENTICATION_FAILED",
                "Facebook did not accept the supplied session cookies.",
                401,
            )
        return _success("Facebook session connected.", public_session, 201)

    @application.post(
        "/api/v1/sessions/{session_id}/validate",
        dependencies=protected,
        tags=["sessions"],
    )
    async def validate_session(session_id: str) -> JSONResponse:
        try:
            public_session = await session_registry.validate(session_id)
        except SessionNotFoundError:
            return _error("NOT_FOUND", "Provider session not found.", 404)
        except SessionAuthenticationError:
            return _error(
                "AUTHENTICATION_FAILED", "The Facebook session is no longer valid.", 401
            )
        return _success("Facebook session is valid.", public_session)

    @application.delete(
        "/api/v1/sessions/{session_id}",
        dependencies=protected,
        tags=["sessions"],
    )
    async def delete_session(session_id: str) -> JSONResponse:
        try:
            await session_registry.delete(session_id)
        except SessionNotFoundError:
            return _error("NOT_FOUND", "Provider session not found.", 404)
        return _success("Provider session disconnected.")

    return application


app = create_app()
