import pytest
from unittest.mock import patch
from _messaging._attachments import _build_request, _parse_response, func, func_async
from conftest import HttpxResponseMock


def test_build_request(mock_dataFB, tmp_path):
    dummy_file = tmp_path / "test.jpg"
    dummy_file.write_bytes(b"dummy_content")

    req = _build_request(str(dummy_file), mock_dataFB)

    assert req["url"] == "https://upload.facebook.com/ajax/mercury/upload.php"
    assert req["headers"]["Cookie"] == mock_dataFB["cookieFacebook"]
    assert req["data"]["fb_dtsg"] == mock_dataFB["fb_dtsg"]
    assert "upload_0" in req["files"]

    # Just check the file name and mime type in the tuple
    assert req["files"]["upload_0"][0] == "test.jpg"
    assert req["files"]["upload_0"][2] == "image/jpeg"
    req["files"]["upload_0"][1].close()


def test_parse_response_success():
    resp_text = 'for (;;);{"payload": {"metadata": [{"attachmentID": 12345, "filename": "a", "videoDuration": null, "attachmentUrl": "http://img.com", "typeAttachment": "image/jpeg"}]}}'
    result = _parse_response(resp_text)
    assert result is not None
    assert result["attachmentID"] == 12345


def test_parse_response_failure():
    resp_text = 'for (;;);{"error": 1}'
    result = _parse_response(resp_text)
    assert result is None


@pytest.mark.parametrize(
    "resp_text",
    [
        "for (;;);null",
        'for (;;);{"payload": null}',
        'for (;;);{"payload": []}',
        'for (;;);{"payload": {"metadata": null}}',
    ],
)
def test_parse_response_ignores_empty_or_malformed_payload(resp_text):
    assert _parse_response(resp_text) is None


@patch("httpx.Client.post")
def test_attachments_func(mock_post, mock_dataFB, tmp_path):
    dummy_file = tmp_path / "test.jpg"
    dummy_file.write_bytes(b"dummy_content")
    mock_resp = HttpxResponseMock(
        200,
        b'for (;;);{"payload": {"metadata": [{"attachmentID": 123, "filename": "a", "videoDuration": null, "attachmentUrl": "http://url", "typeAttachment": "image/jpeg"}]}}',
    )
    mock_post.return_value = mock_resp

    res = func(str(dummy_file), mock_dataFB)
    assert res is not None
    assert res["attachmentID"] == 123
    mock_post.assert_called_once()


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_attachments_func_async(mock_post_async, mock_dataFB, tmp_path):
    dummy_file = tmp_path / "test.jpg"
    dummy_file.write_bytes(b"dummy_content")
    mock_resp = HttpxResponseMock(
        200,
        b'for (;;);{"payload": {"metadata": [{"attachmentID": 123, "filename": "a", "videoDuration": null, "attachmentUrl": "http://url", "typeAttachment": "image/jpeg"}]}}',
    )
    mock_post_async.return_value = mock_resp

    res = await func_async(str(dummy_file), mock_dataFB)
    assert res is not None
    assert res["attachmentID"] == 123
    mock_post_async.assert_called_once()
