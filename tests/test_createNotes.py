from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from _messaging import _createNotes as notes
from _messaging._createNotes import _error_response, _normalize_privacy, _request_error


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


def test_recreate_note_blocking_uses_only_blocking_operations(monkeypatch):
    delete_note = Mock(return_value={"success": 1, "data": {"id": "old-note"}})
    create_note = Mock(return_value={"success": 1, "data": {"id": "new-note"}})
    monkeypatch.setattr(notes, "_deleteNote_blocking", delete_note)
    monkeypatch.setattr(notes, "_createNote_blocking", create_note)

    result = notes.re_createNote_blocking(
        {"FacebookID": "bot"}, "old-note", "Nội dung mới", privacy="FRIENDS"
    )

    delete_note.assert_called_once_with({"FacebookID": "bot"}, "old-note")
    create_note.assert_called_once_with(
        {"FacebookID": "bot"}, "Nội dung mới", privacy="FRIENDS"
    )
    assert result == {
        "success": 1,
        "messages": "Tạo lại note thành công.",
        "data": {"deleted": {"id": "old-note"}, "created": {"id": "new-note"}},
    }


def test_recreate_note_blocking_stops_when_delete_fails(monkeypatch):
    error = {"error": 1, "messages": "Không thể xoá note."}
    create_note = Mock()
    monkeypatch.setattr(notes, "_deleteNote_blocking", Mock(return_value=error))
    monkeypatch.setattr(notes, "_createNote_blocking", create_note)

    assert notes.re_createNote_blocking({}, "old-note", "Nội dung mới") is error
    create_note.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        {},
        {"data": None},
        {"data": {"other": {}}},
        {"data": {"xfb_rich_status_create": {}}},
        {"data": {"xfb_rich_status_create": {"status": False}}},
        {"data": {"xfb_rich_status_create": {"status": "FAILED"}}},
        {"data": {"xfb_rich_status_create": {"status": {"__typename": "RichStatus"}}}},
    ],
)
async def test_create_note_rejects_missing_mutation_node(
    monkeypatch, mock_dataFB, response
):
    post = AsyncMock(return_value=response)
    monkeypatch.setattr(notes, "_post_graphql_async", post)

    result = await notes.createNote(mock_dataFB, "Nội dung note")

    assert result["error"] == 1
    assert result["raw"] == response
    assert post.await_args.kwargs["retries"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        {},
        {"data": None},
        {"data": {"other": {}}},
        {"data": {"xfb_rich_status_delete": {}}},
        {"data": {"xfb_rich_status_delete": {"success": False}}},
        {"data": {"xfb_rich_status_delete": {"status": "ERROR"}}},
        {"data": {"xfb_rich_status_delete": {"__typename": "RichStatusPayload"}}},
    ],
)
async def test_delete_note_rejects_missing_mutation_node(
    monkeypatch, mock_dataFB, response
):
    post = AsyncMock(return_value=response)
    monkeypatch.setattr(notes, "_post_graphql_async", post)

    result = await notes.deleteNote(mock_dataFB, "note-id")

    assert result["error"] == 1
    assert result["raw"] == response
    assert post.await_args.kwargs["retries"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operation", "response"),
    [
        pytest.param(
            "create",
            {
                "data": {"xfb_rich_status_create": {"status": {"id": "new-note"}}},
                "errors": [{"message": "Tạo note bị từ chối."}],
            },
            id="create",
        ),
        pytest.param(
            "delete",
            {
                "data": {"xfb_rich_status_delete": {"id": "old-note"}},
                "errors": [{"message": "Xoá note bị từ chối."}],
            },
            id="delete",
        ),
    ],
)
async def test_note_mutations_prioritize_graphql_errors(
    monkeypatch, mock_dataFB, operation, response
):
    monkeypatch.setattr(notes, "_post_graphql_async", AsyncMock(return_value=response))

    if operation == "create":
        result = await notes.createNote(mock_dataFB, "Nội dung note")
    else:
        result = await notes.deleteNote(mock_dataFB, "old-note")

    assert result["error"] == 1
    assert result["messages"] == response["errors"][0]["message"]


@pytest.mark.asyncio
async def test_note_mutations_preserve_success_shape_and_use_unique_ids(
    monkeypatch, mock_dataFB
):
    generated_ids = iter(["create-mutation", "create-session", "delete-mutation"])
    monkeypatch.setattr(notes, "generate_client_id", lambda: next(generated_ids))
    post = AsyncMock(
        side_effect=[
            {"data": {"xfb_rich_status_create": {"status": {"id": "new-note"}}}},
            {"data": {"xfb_rich_status_delete": {"id": "old-note"}}},
        ]
    )
    monkeypatch.setattr(notes, "_post_graphql_async", post)

    created = await notes.createNote(mock_dataFB, "Nội dung note")
    deleted = await notes.deleteNote(mock_dataFB, "old-note")

    assert created == {
        "success": 1,
        "messages": "Tạo note mới thành công.",
        "data": {"xfb_rich_status_create": {"status": {"id": "new-note"}}},
    }
    assert deleted == {
        "success": 1,
        "messages": "Xoá note thành công.",
        "data": {"xfb_rich_status_delete": {"id": "old-note"}},
    }
    create_input = post.await_args_list[0].args[3]["input"]
    delete_input = post.await_args_list[1].args[3]["input"]
    assert create_input["client_mutation_id"] == "create-mutation"
    assert create_input["session_id"] == "create-session"
    assert delete_input["client_mutation_id"] == "delete-mutation"
    assert create_input["client_mutation_id"] != delete_input["client_mutation_id"]
    assert all(call.kwargs["retries"] == 0 for call in post.await_args_list)


@pytest.mark.asyncio
async def test_create_note_transport_does_not_retry_ambiguous_timeout(
    monkeypatch, mock_dataFB
):
    transport = AsyncMock(side_effect=httpx.ReadTimeout("request timed out"))
    monkeypatch.setattr(notes, "send_request_async", transport)

    result = await notes.createNote(mock_dataFB, "Nội dung note")

    assert result["error"] == 1
    assert transport.await_count == 1


def test_blocking_note_mutations_disable_retry(monkeypatch, mock_dataFB):
    create_response = {
        "data": {"xfb_rich_status_create": {"status": {"id": "new-note"}}}
    }
    delete_response = {"data": {"xfb_rich_status_delete": {"id": "old-note"}}}
    generated_ids = iter(["create-mutation", "create-session", "delete-mutation"])
    monkeypatch.setattr(notes, "generate_client_id", lambda: next(generated_ids))
    post = Mock(side_effect=[create_response, delete_response])
    monkeypatch.setattr(notes, "_post_graphql", post)

    notes._createNote_blocking(mock_dataFB, "Nội dung note")
    notes._deleteNote_blocking(mock_dataFB, "old-note")

    assert all(call.kwargs["retries"] == 0 for call in post.call_args_list)
    variables = [call.args[3] for call in post.call_args_list]
    mutation_ids = [item["input"]["client_mutation_id"] for item in variables]
    assert mutation_ids == ["create-mutation", "delete-mutation"]
