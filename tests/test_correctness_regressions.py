import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from _features._facebook import (
    _blocking,
    _professional,
    _reactionPost,
    _registerOnProfile,
)
from _features._facebook._archivePost import _parse_result as parse_archive_result
from _features._facebook._deletePost import _parse_result as parse_delete_result
from _features._facebook._unFriend import _parse_result as parse_unfriend_result
from _features._thread import _all_thread_data
from _messaging._listening import listeningEvent

PARSER_CASES = [
    pytest.param(
        parse_unfriend_result,
        {"data": {"friend_remove": {"success": True}}},
        {"data": {"friend_remove": {"success": False}}},
        "Xóa bạn bè thành công!",
        id="unfriend",
    ),
    pytest.param(
        parse_archive_result,
        {"data": {"archive_story": {"success": True}}},
        {"data": {"archive_story": {"success": False}}},
        "Lưu trữ bài viết thành công!",
        id="archive-post",
    ),
    pytest.param(
        parse_delete_result,
        {"data": {"move_to_trash_story": {"success": True}}},
        {"data": {"move_to_trash_story": {"success": False}}},
        "Xóa bài viết thành công!",
        id="delete-post",
    ),
]


@pytest.mark.parametrize(
    ("parser", "success_payload", "false_payload", "success_message"),
    PARSER_CASES,
)
def test_mutation_parser_preserves_success_shape(
    parser, success_payload, false_payload, success_message
):
    assert parser(success_payload) == {"success": 1, "messages": success_message}


@pytest.mark.parametrize(
    ("parser", "success_payload", "false_payload", "success_message"),
    PARSER_CASES,
)
def test_mutation_parser_rejects_null_data(
    parser, success_payload, false_payload, success_message
):
    assert parser({"data": None}) == {
        "error": 1,
        "messages": "Facebook không phản hồi hợp lệ.",
    }


@pytest.mark.parametrize(
    ("parser", "success_payload", "false_payload", "success_message"),
    PARSER_CASES,
)
def test_mutation_parser_rejects_false_success(
    parser, success_payload, false_payload, success_message
):
    assert parser(false_payload) == {
        "error": 1,
        "messages": "Facebook không phản hồi hợp lệ.",
    }


@pytest.mark.parametrize(
    ("parser", "success_payload", "false_payload", "success_message"),
    PARSER_CASES,
)
def test_mutation_parser_rejects_graphql_errors(
    parser, success_payload, false_payload, success_message
):
    payload = {**success_payload, "errors": [{"message": "Mutation failed"}]}

    assert parser(payload) == {"error": 1, "messages": "Mutation failed"}


SENSITIVE_MUTATION_CASES = [
    pytest.param(
        _blocking._parse_response,
        ("block",),
        {"profile_block_user": {"success": True}},
        id="block",
    ),
    pytest.param(
        _blocking._parse_response,
        ("unblock",),
        {"blocking_settings_block": {"success": True}},
        id="unblock",
    ),
    pytest.param(
        _professional._parse_response,
        (True,),
        {"profile_plus_onboarding_dialog_transition": {"success": True}},
        id="professional-on",
    ),
    pytest.param(
        _professional._parse_response,
        (False,),
        {"profile_plus_rollback": {"success": True}},
        id="professional-off",
    ),
    pytest.param(
        _registerOnProfile._parse_response,
        (),
        {"additional_profile_create": {"profile": {"id": "new-profile"}}},
        id="additional-profile",
    ),
]


@pytest.mark.parametrize(
    ("parser", "parser_args", "mutation_data"), SENSITIVE_MUTATION_CASES
)
def test_sensitive_mutation_parser_accepts_expected_nonempty_node(
    parser, parser_args, mutation_data
):
    result = parser({"data": mutation_data}, *parser_args)

    assert result["success"] == 1


@pytest.mark.parametrize(
    ("parser", "parser_args", "mutation_data"), SENSITIVE_MUTATION_CASES
)
def test_sensitive_mutation_parser_prioritizes_graphql_errors(
    parser, parser_args, mutation_data
):
    payload = {
        "data": mutation_data,
        "errors": [{"message": "Facebook từ chối mutation."}],
    }

    assert parser(payload, *parser_args) == {
        "error": 1,
        "messages": "Facebook từ chối mutation.",
    }


@pytest.mark.parametrize(
    ("parser", "parser_args", "mutation_data"), SENSITIVE_MUTATION_CASES
)
def test_sensitive_mutation_parser_rejects_unrelated_data(
    parser, parser_args, mutation_data
):
    result = parser({"data": {"unrelated": {"success": True}}}, *parser_args)

    assert result["error"] == 1


@pytest.mark.parametrize(
    ("parser", "parser_args", "mutation_data"), SENSITIVE_MUTATION_CASES
)
def test_sensitive_mutation_parser_rejects_empty_expected_node(
    parser, parser_args, mutation_data
):
    node_name = next(iter(mutation_data))
    result = parser({"data": {node_name: {}}}, *parser_args)

    assert result["error"] == 1


@pytest.mark.parametrize(
    ("parser", "parser_args", "node_name"),
    [
        pytest.param(
            _blocking._parse_response,
            ("block",),
            "profile_block_user",
            id="block",
        ),
        pytest.param(
            _professional._parse_response,
            (True,),
            "profile_plus_onboarding_dialog_transition",
            id="professional",
        ),
    ],
)
@pytest.mark.parametrize(
    "node",
    ["success", ["success"], {"__typename": "MutationPayload"}],
    ids=["scalar", "list", "metadata-only"],
)
def test_sensitive_mutation_parser_rejects_unconfirmed_expected_node(
    parser, parser_args, node_name, node
):
    result = parser({"data": {node_name: node}}, *parser_args)

    assert result["error"] == 1


@pytest.mark.parametrize(
    ("parser", "parser_args", "node_name"),
    [
        pytest.param(
            _blocking._parse_response,
            ("block",),
            "profile_block_user",
            id="block",
        ),
        pytest.param(
            _professional._parse_response,
            (True,),
            "profile_plus_onboarding_dialog_transition",
            id="professional",
        ),
        pytest.param(
            _registerOnProfile._parse_response,
            (),
            "additional_profile_create",
            id="additional-profile",
        ),
    ],
)
def test_sensitive_mutation_parser_rejects_explicit_failure_status(
    parser, parser_args, node_name
):
    result = parser(
        {"data": {node_name: {"success": False}}},
        *parser_args,
    )

    assert result["error"] == 1


def test_additional_profile_parser_rejects_failed_string_status():
    result = _registerOnProfile._parse_response(
        {
            "data": {
                "additional_profile_create": {
                    "status": "FAILED",
                    "profile": {"id": "not-created"},
                }
            }
        }
    )

    assert result["error"] == 1


def test_reaction_uses_fresh_client_mutation_id(
    monkeypatch: pytest.MonkeyPatch, mock_dataFB
):
    generated_ids = iter(("reaction-first", "reaction-second"))
    monkeypatch.setattr(
        _reactionPost, "generate_client_id", lambda: next(generated_ids)
    )

    first_form, _ = _reactionPost._build_form(mock_dataFB, "123", "LIKE")
    second_form, _ = _reactionPost._build_form(mock_dataFB, "123", "LOVE")

    first_input = json.loads(first_form["variables"])["input"]
    second_input = json.loads(second_form["variables"])["input"]
    assert first_input["client_mutation_id"] == "reaction-first"
    assert second_input["client_mutation_id"] == "reaction-second"


@pytest.mark.asyncio
async def test_disconnect_delegates_blocking_work_to_thread():
    listener = listeningEvent.__new__(listeningEvent)
    disconnect_blocking = Mock()
    listener.disconnect_blocking = disconnect_blocking

    with patch(
        "_messaging._listening.asyncio.to_thread", new_callable=AsyncMock
    ) as to_thread:
        await listener.disconnect()

    to_thread.assert_awaited_once_with(disconnect_blocking)
    disconnect_blocking.assert_not_called()


def test_pending_mqtt_queue_refreshes_sequence_synchronously():
    listener = listeningEvent({"FacebookID": "bot"})
    refresh = Mock(side_effect=lambda: setattr(listener, "lastSeqID", 42))
    listener.get_last_seq_id_blocking = refresh
    listener.get_last_seq_id = Mock()
    client = Mock()

    listener._publish_pending_queue(client)

    refresh.assert_called_once_with()
    listener.get_last_seq_id.assert_not_called()
    client.publish.assert_called_once()


def test_fresh_mqtt_sequence_uses_blocking_thread_data(mock_dataFB):
    listener = listeningEvent(mock_dataFB)
    thread_data = {"last_seq_id": 42, "dataAllThread": {"countThread": 0}}

    with (
        patch.object(
            _all_thread_data, "func_blocking", return_value=thread_data
        ) as blocking,
        patch.object(
            _all_thread_data,
            "func",
            side_effect=AssertionError("Không được gọi coroutine từ blocking path."),
        ) as async_func,
    ):
        result = listener.get_last_seq_id_blocking()

    assert result == 42
    assert listener.fbt is thread_data
    blocking.assert_called_once_with(mock_dataFB)
    async_func.assert_not_called()


def test_thread_data_blocking_entrypoint_reuses_response_parser(mock_dataFB):
    response = Mock(
        text=(
            '{"o0":{"data":{"viewer":{"message_threads":'
            '{"sync_sequence_id":"42","nodes":[]}}}}}'
        )
    )

    with patch.object(
        _all_thread_data, "_post_graphqlbatch", return_value=response
    ) as post:
        result = _all_thread_data.func_blocking(mock_dataFB)

    assert result["last_seq_id"] == 42
    assert result["dataAllThread"]["countThread"] == 0
    post.assert_called_once_with(mock_dataFB, None)


def test_mqtt_overflow_refreshes_sequence_synchronously():
    listener = listeningEvent({"FacebookID": "bot"})
    listener.syncToken = "stale-token"
    listener.lastSeqID = 12
    refresh = Mock(side_effect=lambda: setattr(listener, "lastSeqID", 42))
    listener.get_last_seq_id_blocking = refresh
    listener.get_last_seq_id = Mock()
    listener._publish_pending_queue = Mock()
    message = Mock(payload=b'{"errorCode":100}')
    client = Mock()

    listener._on_message(client, None, message)

    refresh.assert_called_once_with()
    listener.get_last_seq_id.assert_not_called()
    listener._publish_pending_queue.assert_called_once_with(client)
