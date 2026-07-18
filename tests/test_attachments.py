import pytest
from unittest.mock import patch
from _messaging._attachments import (
    _build_request,
    _parse_response,
    _to_send_attachment_type,
    func,
    func_async,
)
from conftest import HttpxResponseMock


def test_build_request(mock_dataFB, tmp_path):
    dummy_file = tmp_path / "test.jpg"
    dummy_file.write_bytes(b"dummy_content")

    req = _build_request(str(dummy_file), mock_dataFB)

    assert req["url"] == "https://upload.facebook.com/ajax/mercury/upload.php"
    assert req["headers"]["Cookie"] == mock_dataFB["cookieFacebook"]
    assert req["data"]["fb_dtsg"] == mock_dataFB["fb_dtsg"]
    assert "__req" in req["data"]
    assert "jazoest" not in req["data"]
    assert "__user" not in req["data"]
    assert "__rev" not in req["data"]
    assert "av" not in req["data"]
    assert req["data"]["voice_clip"] is False
    assert "upload_0" in req["files"]

    # Just check the file name and mime type in the tuple
    assert req["files"]["upload_0"][0] == "test.jpg"
    assert req["files"]["upload_0"][2] == "image/jpeg"
    req["files"]["upload_0"][1].close()


def test_parse_response_success():
    resp_text = 'for (;;);{"payload": {"metadata": [{"attachmentID": 12345, "filename": "a", "videoDuration": null, "attachmentUrl": "http://img.com", "attachmentType": "image/jpeg"}]}}'
    result = _parse_response(resp_text)
    assert result is not None
    assert result["attachmentID"] == 12345
    assert result["attachmentType"] == "image/jpeg"
    assert result["typeAttachment"] == "image"


def test_parse_response_supports_legacy_type_attachment_key():
    resp_text = 'for (;;);{"payload": {"metadata": {"0": {"attachmentID": 12345, "attachmentUrl": "http://file.com", "typeAttachment": "application/pdf"}}}}'
    result = _parse_response(resp_text)
    assert result is not None
    assert result["attachmentType"] == "application/pdf"
    assert result["typeAttachment"] == "file"


def test_parse_response_supports_legacy_fbchat_image_id():
    resp_text = 'for (;;);{"payload": {"metadata": [{"image_id": "12345"}]}}'
    result = _parse_response(resp_text)
    assert result is not None
    assert result["attachmentID"] == "12345"
    assert result["typeAttachment"] == "image"


def test_parse_response_supports_legacy_fbchat_gif_id():
    resp_text = 'for (;;);{"payload": {"metadata": [{"gif_id": "67890"}]}}'
    result = _parse_response(resp_text)
    assert result is not None
    assert result["attachmentID"] == "67890"
    assert result["typeAttachment"] == "gif"


def test_parse_response_supports_original_values_order_fallback():
    resp_text = (
        'for (;;);{"payload":{"metadata":{"0":{"id":999,'
        '"name":"sample.png","mime":"image/png","url":"https://example.test/a.png"}}}}'
    )
    result = _parse_response(resp_text)
    assert result is not None
    assert result["attachmentID"] == 999
    assert result["attachmentType"] == "image/png"
    assert result["attachmentUrl"] == "https://example.test/a.png"
    assert result["typeAttachment"] == "image"


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


def test_parse_response_can_return_upload_error_details():
    resp_text = (
        'for (;;);{"error":1357001,"errorSummary":"Upload blocked",'
        '"errorDescription":"Session checkpointed","payload":null}'
    )
    result = _parse_response(resp_text, include_error=True)
    assert result is not None
    assert result["error"] == 1
    assert result["payload"]["error-code"] == 1357001
    assert result["payload"]["error-summary"] == "Upload blocked"
    assert result["payload"]["error-description"] == "Session checkpointed"
    assert "raw-excerpt" in result["payload"]


def test_parse_response_can_return_non_json_upload_error_excerpt():
    result = _parse_response("<html>checkpoint</html>", include_error=True)
    assert result is not None
    assert result["error"] == 1
    assert result["payload"]["raw-excerpt"] == "<html>checkpoint</html>"


def test_parse_response_marks_null_metadata_as_file_rejected():
    resp_text = (
        'for (;;);{"__ar":1,"payload":{"uploadID":null,'
        '"metadata":{"0":null}}}'
    )
    result = _parse_response(resp_text, include_error=True)
    assert result is not None
    assert result["error"] == 1
    assert result["payload"]["upload-id"] is None
    assert result["payload"]["metadata"] == {"0": None}
    assert result["payload"]["file-rejected"] is True


@pytest.mark.parametrize(
    ("mime_type", "send_type"),
    [
        ("image/jpeg", "image"),
        ("image/gif", "gif"),
        ("video/mp4", "video"),
        ("audio/mpeg", "audio"),
        ("application/pdf", "file"),
        (None, "file"),
    ],
)
def test_to_send_attachment_type(mime_type, send_type):
    assert _to_send_attachment_type(mime_type) == send_type


@patch("requests.post")
def test_attachments_func(mock_post, mock_dataFB, tmp_path):
    dummy_file = tmp_path / "test.jpg"
    dummy_file.write_bytes(b"dummy_content")
    mock_resp = HttpxResponseMock(
        200,
        b'for (;;);{"payload": {"metadata": [{"attachmentID": 123, "filename": "a", "videoDuration": null, "attachmentUrl": "http://url", "attachmentType": "image/jpeg"}]}}',
    )
    mock_post.return_value = mock_resp

    res = func(str(dummy_file), mock_dataFB)
    assert res is not None
    assert res["attachmentID"] == 123
    assert res["typeAttachment"] == "image"
    mock_post.assert_called_once()


@pytest.mark.asyncio
@patch("requests.post")
async def test_attachments_func_async(mock_post_async, mock_dataFB, tmp_path):
    dummy_file = tmp_path / "test.jpg"
    dummy_file.write_bytes(b"dummy_content")
    mock_resp = HttpxResponseMock(
        200,
        b'for (;;);{"payload": {"metadata": [{"attachmentID": 123, "filename": "a", "videoDuration": null, "attachmentUrl": "http://url", "attachmentType": "image/jpeg"}]}}',
    )
    mock_post_async.return_value = mock_resp

    res = await func_async(str(dummy_file), mock_dataFB)
    assert res is not None
    assert res["attachmentID"] == 123
    assert res["typeAttachment"] == "image"
    mock_post_async.assert_called_once()
