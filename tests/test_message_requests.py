import pytest
import json
from unittest.mock import patch
from _messaging._message_requests import _build_request, _parse_response, func, func_async
from conftest import HttpxResponseMock

def test_build_request(mock_dataFB):
    req = _build_request(mock_dataFB)
    assert req["url"] == "https://www.facebook.com/api/graphqlbatch/"
    queries = json.loads(req["data"]["queries"])
    assert "o0" in queries
    assert queries["o0"]["doc_id"] == "3336396659757871"
    assert queries["o0"]["query_params"]["tags"] == ["PENDING"]

def test_parse_response():
    resp_text = '{"o0": {"data": {"viewer": {"message_threads": {"nodes": [{"last_message": {"nodes": [{"snippet": "Hello", "message_sender": {"messaging_actor": {"id": "123"}}, "timestamp_precise": "1600000000"}]}}]}}}}} {"successful_results"}'
    result = _parse_response(resp_text)
    
    assert result["success"] == 1
    assert result["data"]["total_count"] == 1
    assert result["data"][0]["snippet"] == "Hello"
    assert result["data"][0]["senderID"] == "123"

@patch("_messaging._message_requests.send_request")
def test_message_requests_func(mock_send, mock_dataFB):
    mock_send.return_value = HttpxResponseMock(200, b'{"o0": {"data": {"viewer": {"message_threads": {"nodes": []}}}}} {"successful_results"}')
    res = func(mock_dataFB)
    assert res["success"] == 1
    assert res["data"]["total_count"] == 0
    mock_send.assert_called_once()

@pytest.mark.asyncio
@patch("_messaging._message_requests.send_request_async")
async def test_message_requests_func_async(mock_send_async, mock_dataFB):
    mock_send_async.return_value = HttpxResponseMock(200, b'{"o0": {"data": {"viewer": {"message_threads": {"nodes": []}}}}} {"successful_results"}')
    res = await func_async(mock_dataFB)
    assert res["success"] == 1
    assert res["data"]["total_count"] == 0
    mock_send_async.assert_called_once()
