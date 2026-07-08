import pytest
import json
from unittest.mock import patch, MagicMock
from _messaging._attachments import _build_request, _parse_response, func, func_async
from conftest import HttpxResponseMock

@patch("_messaging._attachments.get_files_from_paths")
def test_build_request(mock_get_files, mock_dataFB):
    mock_get_files.return_value = [("test.jpg", b"dummy_content", "image/jpeg")]
    req = _build_request("test.jpg", mock_dataFB)
    
    assert req["url"] == "https://upload.facebook.com/ajax/mercury/upload.php"
    assert req["headers"]["Cookie"] == mock_dataFB["cookieFacebook"]
    assert req["data"]["fb_dtsg"] == mock_dataFB["fb_dtsg"]
    assert "upload_0" in req["files"]
    assert req["files"]["upload_0"] == ("test.jpg", b"dummy_content", "image/jpeg")

def test_parse_response_success():
    resp_text = 'for (;;);{"payload": {"metadata": [{"attachmentID": 12345, "filename": "a", "videoDuration": null, "attachmentUrl": "http://img.com", "typeAttachment": "image/jpeg"}]}}'
    result = _parse_response(resp_text)
    assert result is not None
    assert result["attachmentID"] == 12345

def test_parse_response_failure():
    resp_text = 'for (;;);{"error": 1}'
    result = _parse_response(resp_text)
    assert result is None

@patch("_messaging._attachments.get_files_from_paths")
@patch("httpx.Client.post")
def test_attachments_func(mock_post, mock_get_files, mock_dataFB):
    mock_get_files.return_value = [("test.jpg", b"dummy_content", "image/jpeg")]
    mock_resp = HttpxResponseMock(200, b'for (;;);{"payload": {"metadata": [{"attachmentID": 123, "filename": "a", "videoDuration": null, "attachmentUrl": "http://url", "typeAttachment": "image/jpeg"}]}}')
    mock_post.return_value = mock_resp
    
    res = func("test.jpg", mock_dataFB)
    assert res is not None
    assert res["attachmentID"] == 123
    mock_post.assert_called_once()

@pytest.mark.asyncio
@patch("_messaging._attachments.get_files_from_paths")
@patch("httpx.AsyncClient.post")
async def test_attachments_func_async(mock_post_async, mock_get_files, mock_dataFB):
    mock_get_files.return_value = [("test.jpg", b"dummy_content", "image/jpeg")]
    mock_resp = HttpxResponseMock(200, b'for (;;);{"payload": {"metadata": [{"attachmentID": 123, "filename": "a", "videoDuration": null, "attachmentUrl": "http://url", "typeAttachment": "image/jpeg"}]}}')
    mock_post_async.return_value = mock_resp
    
    res = await func_async("test.jpg", mock_dataFB)
    assert res is not None
    assert res["attachmentID"] == 123
    mock_post_async.assert_called_once()
