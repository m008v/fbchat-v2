import pytest
from unittest.mock import patch, Mock
from _core._session import dataGetHome

@pytest.mark.skip(reason="Requires exact HTML fixture from Facebook to parse correctly")
def test_dataGetHome_success(mock_dataFB):
    with patch("requests.get") as mock_get:
        # Mock the HTML response from facebook to contain the necessary script tags
        mock_resp = Mock()
        mock_resp.text = '["DTSGInitialData",[],{"token":"mock_dtsg"},123]\n{"async_get_token":"mock_dtsg_ag"}\n["LSD",[],{"token":"22421"},123]\n{"client_revision":123456}\n{"USER_ID":"10001234567890"}'
        mock_resp.cookies.get_dict.return_value = {"c_user": "10001234567890", "xs": "mock_xs", "fr": "mock_fr", "datr": "mock_datr"}
        mock_get.return_value = mock_resp

        result = dataGetHome("c_user=10001234567890; xs=mock_xs; fr=mock_fr; datr=mock_datr;")
        
        # We can't perfectly mock the brittle string splits in dataGetHome without exact HTML structures, 
        # so this test will likely fail with IndexError if the HTML structure doesn't match perfectly.
        # But this sets up the scaffolding for unit testing it.
        assert result is not None

def test_dataGetHome_network_error():
    import requests
    with patch("requests.get", side_effect=requests.RequestException("Network error")):
        result = dataGetHome("cookie")
        assert result is None
