from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from _messaging._listening import listeningEvent


def _mqtt_message(payload: object) -> SimpleNamespace:
    return SimpleNamespace(payload=json.dumps(payload).encode("utf-8"))


@pytest.mark.parametrize(
    "payload",
    [
        [],
        "PRIVATE_SCALAR",
        {"deltas": {"PRIVATE": "OBJECT"}},
        {"deltas": "PRIVATE_LIST"},
        {"syncToken": [], "firstDeltaSeqId": 1},
    ],
)
def test_mqtt_callback_rejects_invalid_json_shapes_without_side_effects(
    payload: object,
    capsys: pytest.CaptureFixture[str],
) -> None:
    listener = listeningEvent({"FacebookID": "bot"})
    client = Mock()

    listener._on_message(client, None, _mqtt_message(payload))

    assert listener.messageQueue.empty()
    assert listener.syncToken is None
    client.disconnect.assert_not_called()
    assert "PRIVATE" not in capsys.readouterr().out


def test_mqtt_callback_skips_malformed_delta_and_keeps_valid_message() -> None:
    listener = listeningEvent({"FacebookID": "bot"})
    payload = {
        "deltas": [
            {"messageMetadata": {"threadKey": []}},
            {
                "body": "hello",
                "messageMetadata": {
                    "threadKey": {"threadFbId": "thread-1"},
                    "actorFbId": "sender-1",
                    "messageId": "mid-1",
                    "timestamp": 123,
                },
                "attachments": {"unexpected": "object"},
            },
        ]
    }

    listener._on_message(Mock(), None, _mqtt_message(payload))

    assert listener.get_message_blocking() == {
        "body": "hello",
        "timestamp": 123,
        "userID": "sender-1",
        "messageID": "mid-1",
        "replyToID": "thread-1",
        "type": "thread",
        "attachments": {"id": 0, "url": None},
    }
    assert listener.messageQueue.empty()
