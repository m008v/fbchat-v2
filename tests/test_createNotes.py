from _messaging._createNotes import _normalize_privacy, _error_response, _request_error

def test_normalize_privacy():
    assert _normalize_privacy("EVERYONE") == "FRIENDS"
    assert _normalize_privacy("PUBLIC") == "FRIENDS"
    assert _normalize_privacy("FRIENDS") == "FRIENDS"
    assert _normalize_privacy(None) == "FRIENDS"

def test_error_response():
    data = {"errors": [{"message": "Invalid note"}]}
    res = _error_response(data)
    assert res["error"] == 1
    assert res["messages"] == "Invalid note"

def test_request_error():
    res = _request_error("Timeout", Exception("fail"), "Friendly", 123)
    assert len(res["errors"]) == 1
    err = res["errors"][0]
    assert err["message"] == "Timeout"
    assert err["friendly_name"] == "Friendly"
    assert err["doc_id"] == "123"
    assert err["exception"] == "fail"
