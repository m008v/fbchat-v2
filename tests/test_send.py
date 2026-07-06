import pytest
from unittest.mock import patch, Mock
from _messaging._send import api

def test_api_init():
    sender = api()
    assert sender.results == {}
    assert "is_unread" in sender.properties

def test_api_send(mock_dataFB):
    sender = api()
    with patch("httpx.Client.post") as mock_post:
        mock_resp = Mock()
        mock_resp.text = 'for (;;);{"payload": {"actions": [{"message_id": "123456", "timestamp": 123456789}], "success": 1}}'
        mock_post.return_value = mock_resp
        
        result = sender.send(mock_dataFB, "Hello", "123456")
        
        assert "payload" in result
        assert result["payload"]["messageID"] == "123456"
        assert result["payload"]["timestamp"] == 123456789
        mock_post.assert_called_once()
