import pytest
import json
from unittest.mock import patch
from _messaging._reactions import _build_request, func, func_sync
from conftest import HttpxResponseMock


def test_build_request(mock_dataFB):
    req = _build_request(mock_dataFB, "add", "mid.123", "👍")
    assert req["url"] == "https://www.facebook.com/webgraphql/mutation/"
    assert req["data"]["doc_id"] == "1491398900900362"
    variables = json.loads(req["data"]["variables"])
    assert variables["data"]["action"] == "ADD_REACTION"
    assert variables["data"]["message_id"] == "mid.123"
    assert variables["data"]["reaction"] == "👍"

    req_remove = _build_request(mock_dataFB, "remove", "mid.123", "👍")
    variables_remove = json.loads(req_remove["data"]["variables"])
    assert variables_remove["data"]["action"] == "REMOVE_REACTION"


@patch("_messaging._reactions.send_request")
def test_reactions_func(mock_send, mock_dataFB):
    mock_resp = HttpxResponseMock(200, b'{"data": {"message_reaction_mutation": {}}}')
    mock_send.return_value = mock_resp

    resp = func_sync(mock_dataFB, "add", "mid.123", "👍")
    assert resp.status_code == 200
    mock_send.assert_called_once()


@pytest.mark.asyncio
@patch("_messaging._reactions.send_request_async")
async def test_reactions_func_awaitable(mock_send, mock_dataFB):
    mock_resp = HttpxResponseMock(200, b'{"data": {"message_reaction_mutation": {}}}')
    mock_send.return_value = mock_resp

    resp = await func(mock_dataFB, "add", "mid.123", "👍")
    assert resp.status_code == 200
    mock_send.assert_called_once()
