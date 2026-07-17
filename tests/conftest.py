from typing import Any

import httpx
import pytest


@pytest.fixture
def mock_dataFB() -> dict[str, Any]:
    return {
        "fb_dtsg": "mock_dtsg",
        "fb_dtsg_ag": "mock_dtsg_ag",
        "jazoest": "22421",
        "hash": "mock_hash",
        "sessionID": "1234567890",
        "FacebookID": "10001234567890",
        "clientRevision": "123456",
        "cookieFacebook": "c_user=10001234567890; xs=mock_xs; fr=mock_fr; datr=mock_datr;",
    }


class HttpxResponseMock:
    def __init__(self, status_code, content):
        self.status_code = status_code
        self.content = content
        self.text = (
            content.decode("utf-8") if isinstance(content, bytes) else str(content)
        )

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://example.test")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError(
                "mock HTTP error", request=request, response=response
            )
