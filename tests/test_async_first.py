import json
from unittest.mock import AsyncMock, patch

import pytest

from _core._facebookLogin import _get_token_2fa_local, loginFacebook
from _features._facebook import _createPost, _marketplace, _professional
from _features._thread import _addAdmin
from _messaging._listening import listeningEvent
from _messaging._message_requests import _parse_response as parse_message_requests
from _messaging._send import _build_form as build_send_form


@pytest.mark.asyncio
async def test_add_admin_async_uses_async_http_transport(mock_dataFB):
    transport = AsyncMock(return_value={})
    with patch.object(_addAdmin, "post_form_json_async", transport):
        result = await _addAdmin.func(
            mock_dataFB, "thread-1", "user-1", statusChoice=False
        )

    assert result == {
        "status": "success",
        "message": "Gỡ quản trị viên thành công.",
    }
    transport.assert_awaited_once()


@pytest.mark.asyncio
async def test_professional_accepts_boolean_status(mock_dataFB):
    transport = AsyncMock(return_value={"data": {"ok": True}})
    with patch.object(_professional, "post_form_json_async", transport):
        result = await _professional.func(mock_dataFB, True)

    assert result["success"] == 1
    assert result["messages"].startswith("Bật")


def test_create_post_rejects_silently_ignored_attachment(mock_dataFB):
    with pytest.raises(NotImplementedError, match="không còn âm thầm bỏ qua"):
        _createPost._build_form(mock_dataFB, "Bài viết", "attachment-1")


def test_marketplace_supports_all_declared_categories_and_escapes_brand(mock_dataFB):
    form = _marketplace._build_create_form(
        mock_dataFB,
        "Điện thoại",
        'Nhãn "xịn"',
        100,
        "vnd",
        "Mô tả",
        ["điện-thoại"],
        "Mobile phones",
        [123],
        {"latitude": 10.75, "longitude": 106.67},
    )
    variables = json.loads(form["variables"])
    common = variables["input"]["data"]["common"]
    attributes = json.loads(common["attribute_data_json"])

    assert common["category_id"] == _marketplace._CATEGORY_IDS["Mobile phones"]
    assert attributes["brand"] == 'Nhãn "xịn"'
    assert common["photo_ids"] == ["123"]


def test_login_requires_app_token_without_network(monkeypatch):
    monkeypatch.delenv("FBCHAT_APP_ACCESS_TOKEN", raising=False)
    login = loginFacebook("user@example.com", "secret")

    result = login.main_blocking()

    assert result["error"]["error_code"] == -4
    assert "FBCHAT_APP_ACCESS_TOKEN" in result["error"]["description"]


def test_totp_is_generated_locally_and_direct_otp_is_preserved():
    token = _get_token_2fa_local("JBSWY3DPEHPK3PXP")

    assert token.isdigit() and len(token) == 6
    assert _get_token_2fa_local("123456") == "123456"


class _LoginResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_login_uses_legacy_fb4a_requests_form(monkeypatch):
    monkeypatch.setenv("FBCHAT_APP_ACCESS_TOKEN", "app|token")
    calls = []

    def fake_post(url, data, headers, proxies=None, timeout=None):
        calls.append(
            {
                "url": url,
                "data": dict(data),
                "headers": dict(headers),
                "proxies": proxies,
                "timeout": timeout,
            }
        )
        return _LoginResponse(
            {
                "access_token": "access",
                "session_cookies": [{"name": "c_user", "value": "123"}],
            }
        )

    with patch("requests.post", side_effect=fake_post):
        result = loginFacebook("user@example.com", "secret").main_blocking()

    assert result["success"]["setCookies"] == "c_user=123; "
    assert calls[0]["url"] == "https://b-graph.facebook.com/auth/login"
    assert calls[0]["timeout"] == 20
    assert calls[0]["headers"]["User-Agent"].startswith("Dalvik/2.1.0")
    assert calls[0]["data"]["credentials_type"] == "password"
    assert calls[0]["data"]["password"] == "secret"
    assert calls[0]["data"]["access_token"] == "app|token"


def test_login_two_factor_prefers_legacy_otp_password(monkeypatch):
    monkeypatch.setenv("FBCHAT_APP_ACCESS_TOKEN", "app|token")
    calls = []

    two_factor_error = {
        "error": {
            "error_subcode": 1348162,
            "error_data": {
                "uid": "10001",
                "login_first_factor": "first-factor",
            },
        }
    }
    success = {
        "access_token": "access",
        "session_cookies": [{"name": "xs", "value": "abc"}],
    }

    def fake_post(url, data, headers, proxies=None, timeout=None):
        calls.append(dict(data))
        return _LoginResponse(two_factor_error if len(calls) == 1 else success)

    with patch("requests.post", side_effect=fake_post):
        result = loginFacebook("user@example.com", "secret", "123456").main_blocking()

    assert result["success"]["setCookies"] == "xs=abc; "
    assert calls[1]["credentials_type"] == "two_factor"
    assert calls[1]["password"] == "123456"
    assert calls[1]["twofactor_code"] == "123456"
    assert calls[1]["userid"] == "10001"
    assert calls[1]["first_factor"] == "first-factor"
    assert calls[1]["jazoest"] == "22327"


def test_listener_constructor_performs_no_network_io(mock_dataFB):
    with patch(
        "_messaging._listening._all_thread_data.func",
        side_effect=AssertionError("không được gọi mạng trong __init__"),
    ):
        listener = listeningEvent(mock_dataFB)

    assert listener.lastSeqID is None
    assert listener.fbt == {}


def test_send_form_validates_attachment_and_reuses_offline_id(mock_dataFB):
    with pytest.raises(ValueError, match="typeAttachment"):
        build_send_form(
            mock_dataFB,
            "Nội dung",
            "thread-1",
            "virus",
            "attachment-1",
            None,
            False,
            None,
        )

    form = build_send_form(
        mock_dataFB,
        "Nội dung",
        "thread-1",
        None,
        None,
        None,
        False,
        None,
    )
    assert form["offline_threading_id"] == form["message_id"]


def test_message_requests_accepts_facebook_json_prefix():
    response = (
        'for (;;);{"o0":{"data":{"viewer":{"message_threads":{"nodes":[]}}}}}'
        '\n{"successful_results":1}'
    )

    result = parse_message_requests(response)

    assert result["success"] == 1
    assert result["data"]["total_count"] == 0
