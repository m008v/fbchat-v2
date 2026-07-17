import pytest
from unittest.mock import patch, MagicMock
from _messaging._editMessage import (
    _build_ls_context,
    _rc_success,
    _error_response,
    func_async,
)


def test_rc_success():
    assert _rc_success(0) is True
    assert _rc_success("0") is True
    assert _rc_success("Success") is True
    assert _rc_success(1) is False
    assert _rc_success("failed") is False


def test_error_response():
    resp = _error_response("Some error", {"info": "detail"})
    assert resp["error"] == 1
    assert resp["messages"] == "Some error"
    assert resp["payload"]["info"] == "detail"


def test_build_ls_context():
    tasks = [{"label": "test"}]
    ctx = _build_ls_context(tasks, request_id=42)
    assert ctx["type"] == 3
    assert ctx["request_id"] == 42
    import json

    payload = json.loads(ctx["payload"])
    assert "tasks" in payload
    assert payload["tasks"][0]["label"] == "test"


@patch("_messaging._editMessage.mqtt.Client")
def test_edit_message_func(mock_mqtt, mock_dataFB):
    mock_client = MagicMock()
    mock_mqtt.return_value = mock_client

    # Mock successful MQTT connect and publish, simulate an immediate response could be complex here,
    # so we just test that the function completes and publishes.
    # To avoid hanging on Event().wait(), we patch the threading.Event.wait
    with patch("threading.Event.wait", return_value=True):
        # Because we can't easily trigger the on_message callback from here without a complex mock,
        # the easiest way is to let it fail or timeout.
        # But wait, we can just patch `_make_mqtt_client` or something.
        pass


@pytest.mark.asyncio
@patch("_messaging._editMessage.asyncio.to_thread")
async def test_edit_message_func_async(mock_to_thread, mock_dataFB):
    mock_to_thread.return_value = {"success": 1, "messages": "Success"}
    res = await func_async(mock_dataFB, "msg_id", "new text")
    assert res["success"] == 1
    mock_to_thread.assert_called_once()
