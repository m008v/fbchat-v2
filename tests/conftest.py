import pytest
from typing import Any

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
        "cookieFacebook": "c_user=10001234567890; xs=mock_xs; fr=mock_fr; datr=mock_datr;"
    }

class HttpxResponseMock:
    def __init__(self, status_code, content):
        self.status_code = status_code
        self.content = content
        self.text = content.decode("utf-8") if isinstance(content, bytes) else str(content)
