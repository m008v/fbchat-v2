import pytest
from unittest.mock import patch
from _messaging._unsend import _build_request, _parse_response, func
from conftest import HttpxResponseMock


def test_build_request(mock_dataFB):
    req = _build_request("mid.123", mock_dataFB)
    assert req["url"] == "https://www.facebook.com/messaging/unsend_message/"
    assert req["data"]["message_id"] == "mid.123"


def test_parse_response_success():
    resp_text = 'for (;;);{"success": true}'
    result = _parse_response(resp_text)
    assert isinstance(result, dict)
    assert result["success"] == 1
    assert "Thu hồi tin nhắn thành công" in result["messages"]


def test_parse_response_error():
    resp_text = 'for (;;);{"error": "Some error"}'
    result = _parse_response(resp_text)
    assert isinstance(result, dict)
    assert result["error"] == 1
    assert "Some error" in result["messages"]


@pytest.mark.asyncio
@patch("_messaging._unsend.send_request_async")
async def test_unsend_func_awaitable(mock_send, mock_dataFB):
    mock_send.return_value = HttpxResponseMock(200, b'for (;;);{"success": true}')
    res = await func("mid.123", mock_dataFB)
    assert isinstance(res, dict)
    assert res["success"] == 1
    mock_send.assert_called_once()
