from __future__ import annotations

import json

from fbchat_v2.service_provider import _sanitize_threads


def test_thread_dto_excludes_provider_media_and_raw_metadata() -> None:
    raw = {
        "o0": {
            "data": {
                "viewer": {
                    "message_threads": {
                        "nodes": [
                            {
                                "thread_key": {"other_user_id": "42"},
                                "thread_type": "ONE_TO_ONE",
                                "name": "Test user",
                                "unread_count": 3,
                                "updated_time_precise": "123456",
                                "image": {"uri": "https://provider.invalid/avatar"},
                                "marketplace_thread_data": None,
                            }
                        ]
                    }
                }
            }
        }
    }

    threads = _sanitize_threads({"dataGet": json.dumps(raw)})

    assert threads == [
        {
            "threadId": "42",
            "type": "one_to_one",
            "name": "Test user",
            "unreadCount": 3,
            "updatedAt": "123456",
            "archived": False,
            "marketplace": False,
        }
    ]
    assert "provider.invalid" not in json.dumps(threads)
