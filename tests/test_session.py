from unittest.mock import Mock, patch

import httpx

from _core._session import _dataGetHome_blocking


def test_dataGetHome_success():
    with patch("_core._session.send_get_request") as mock_get:
        mock_resp = Mock()
        mock_resp.text = (
            'DTSGInitialData",[],{"token":"mock_dtsg"}'
            ' async_get_token":"mock_dtsg_ag"'
            ' jazoest=22421"'
            ' hash":"mock_hash"'
            ' sessionId":"1234567890"'
            ' "actorID":"10001234567890"'
            ' client_revision":123456,'
        )
        mock_get.return_value = mock_resp

        cookie = "c_user=10001234567890; xs=mock_xs; fr=mock_fr; datr=mock_datr;"
        result = _dataGetHome_blocking(cookie)

        assert result == {
            "fb_dtsg": "mock_dtsg",
            "fb_dtsg_ag": "mock_dtsg_ag",
            "jazoest": "22421",
            "hash": "mock_hash",
            "sessionID": "1234567890",
            "FacebookID": "10001234567890",
            "clientRevision": "123456",
            "cookieFacebook": cookie,
        }
        mock_resp.raise_for_status.assert_called_once()


def test_dataGetHome_network_error():
    with patch(
        "_core._session.send_get_request",
        side_effect=httpx.RequestError("Network error", request=Mock()),
    ):
        result = _dataGetHome_blocking("cookie")
        assert result is None
