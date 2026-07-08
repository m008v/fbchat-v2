from _messaging._changeTheme import _request_error, _graphql_error_response, _normalize_theme

def test_request_error():
    res = _request_error("Timeout", Exception("fail"), "Friendly", 123)
    assert len(res["errors"]) == 1
    err = res["errors"][0]
    assert err["message"] == "Timeout"
    assert err["friendly_name"] == "Friendly"
    assert err["doc_id"] == "123"
    assert err["exception"] == "fail"

def test_graphql_error_response():
    data = {"errors": [{"message": "Invalid query"}]}
    res = _graphql_error_response(data)
    assert res["error"] == 1
    assert res["messages"] == "Invalid query"

def test_normalize_theme():
    raw_data = {
        "id": "999",
        "accessibility_label": "Dark Mode",
        "app_color_mode": "DARK"
    }
    normalized = _normalize_theme(raw_data)
    assert normalized is not None
    assert normalized["id"] == "999"
    assert normalized["name"] == "Dark Mode"
    assert normalized["appColorMode"] == "DARK"

def test_normalize_theme_empty():
    assert _normalize_theme({}) is None
    assert _normalize_theme({"no_id": 1}) is None
