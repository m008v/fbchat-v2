import pytest
from _messaging._editMessage import _build_ls_context, _rc_success, _error_response

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
