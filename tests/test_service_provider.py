from __future__ import annotations

import json
from typing import Any

import pytest

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


@pytest.mark.asyncio
async def test_provider_operations_react_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fbchat_v2.service_provider import ProviderOperations
    import httpx

    async def mock_react(*args: Any, **kwargs: Any) -> httpx.Response:
        return httpx.Response(200, json={"data": {}})

    monkeypatch.setattr("fbchat_v2.service_provider.react_func", mock_react)
    ops = ProviderOperations()
    res = await ops.react_message(
        {"cookieFacebook": "c_user=1; xs=1", "FacebookID": "1"},
        message_id="msg-101",
        emoji="👍",
        action="add",
    )
    assert res == {
        "messageId": "msg-101",
        "emoji": "👍",
        "action": "add",
        "status": "confirmed",
    }


@pytest.mark.asyncio
async def test_provider_operations_unsend_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fbchat_v2.service_provider import ProviderOperations

    async def mock_unsend(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"success": 1, "messages": "Thu hồi thành công"}

    monkeypatch.setattr("fbchat_v2.service_provider.unsend_func", mock_unsend)
    ops = ProviderOperations()
    res = await ops.unsend_message(
        {"cookieFacebook": "c_user=1; xs=1", "FacebookID": "1"},
        message_id="msg-101",
    )
    assert res == {"messageId": "msg-101", "status": "revoked"}


@pytest.mark.asyncio
async def test_provider_operations_get_user_info(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fbchat_v2.service_provider import ProviderOperations

    async def mock_user_info(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {
            "idUser": "12345",
            "nameUser": "Alice Doe",
            "firstName": "Alice",
            "Username": "alicedoe",
            "genderUser": "Female",
            "chatWithUSerIsNonFriend": True,
            "private_raw_data": "secret",
        }

    monkeypatch.setattr("fbchat_v2.service_provider.get_user_info_func", mock_user_info)
    ops = ProviderOperations()
    res = await ops.get_user_info(
        {"cookieFacebook": "c_user=1; xs=1", "FacebookID": "1"},
        user_id="12345",
    )
    assert res == {
        "userId": "12345",
        "name": "Alice Doe",
        "firstName": "Alice",
        "username": "alicedoe",
        "gender": "Female",
        "isNonFriend": True,
    }
    assert "private_raw_data" not in res


@pytest.mark.asyncio
async def test_provider_operations_search_users(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fbchat_v2.service_provider import ProviderOperations

    async def mock_search(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {
            "success": 1,
            "searchResultsDict": [
                {"id": "555", "name": "Bob Smith", "url": "https://facebook.com/bob"}
            ],
        }

    monkeypatch.setattr("fbchat_v2.service_provider.search_func", mock_search)
    ops = ProviderOperations()
    items = await ops.search_users(
        {"cookieFacebook": "c_user=1; xs=1", "FacebookID": "1"}, query="Bob"
    )
    assert items == [
        {"userId": "555", "name": "Bob Smith", "url": "https://facebook.com/bob"}
    ]


@pytest.mark.asyncio
async def test_provider_operations_block_user(monkeypatch: pytest.MonkeyPatch) -> None:
    from fbchat_v2.service_provider import ProviderOperations

    async def mock_blocking(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"success": 1, "messages": "Blocked"}

    monkeypatch.setattr("fbchat_v2.service_provider.blocking_func", mock_blocking)
    ops = ProviderOperations()
    res = await ops.block_user(
        {"cookieFacebook": "c_user=1; xs=1", "FacebookID": "1"},
        user_id="555",
        action="block",
    )
    assert res == {"userId": "555", "action": "block", "status": "confirmed"}


@pytest.mark.asyncio
async def test_provider_operations_get_marketplace_item(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fbchat_v2.service_provider import ProviderOperations

    async def mock_marketplace(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {
            "success": 1,
            "payload": {
                "idProduct": "item-999",
                "nameProduct": "Bicycle",
                "priceProduct": "150",
                "currencyProduct": "USD",
                "decriptionProduct": "Used road bike",
                "urlProduct": "https://facebook.com/marketplace/item/item-999",
                "idSeller": "seller-123",
            },
        }

    monkeypatch.setattr(
        "fbchat_v2.service_provider.get_marketplace_item_func", mock_marketplace
    )
    ops = ProviderOperations()
    res = await ops.get_marketplace_item(
        {"cookieFacebook": "c_user=1; xs=1", "FacebookID": "1"}, item_id="item-999"
    )
    assert res == {
        "itemId": "item-999",
        "name": "Bicycle",
        "price": "150",
        "currency": "USD",
        "description": "Used road bike",
        "url": "https://facebook.com/marketplace/item/item-999",
        "sellerId": "seller-123",
        "status": "experimental",
    }
