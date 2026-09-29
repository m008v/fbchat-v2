"""Sanitized provider operations exposed by the REST boundary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from ._features._facebook._blocking import func as blocking_func
from ._features._facebook._get_user_info import func as get_user_info_func
from ._features._facebook._marketplace import (
    getInformationProductItemMarketPlace as get_marketplace_item_func,
)
from ._features._facebook._search import func as search_func
from ._features._thread._all_thread_data import func as fetch_thread_data
from ._messaging._attachments import func as upload_attachment_func
from ._messaging._reactions import func as react_func
from ._messaging._send import api as SendAPI
from ._messaging._unsend import func as unsend_func


class ProviderOperationError(RuntimeError):
    """Raised when Facebook cannot complete a REST provider operation."""


def _thread_id(node: dict[str, Any]) -> str:
    key = node.get("thread_key") or {}
    return str(key.get("thread_fbid") or key.get("other_user_id") or "").strip()


def _sanitize_threads(result: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(result["dataGet"])
        nodes = parsed["o0"]["data"]["viewer"]["message_threads"]["nodes"]
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise ProviderOperationError(
            "Facebook returned invalid thread data."
        ) from error

    threads: list[dict[str, Any]] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        thread_id = _thread_id(node)
        if not thread_id:
            continue
        threads.append(
            {
                "threadId": thread_id,
                "type": str(node.get("thread_type") or "unknown").lower(),
                "name": node.get("name"),
                "unreadCount": int(node.get("unread_count") or 0),
                "updatedAt": node.get("updated_time_precise"),
                "archived": bool(node.get("has_viewer_archived", False)),
                "marketplace": bool(node.get("marketplace_thread_data")),
            }
        )
    return threads


class ProviderOperations:
    """Async adapter over the fbchat-v2 feature modules."""

    async def list_threads(self, provider_data: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            result = await fetch_thread_data(provider_data)
            return _sanitize_threads(result)
        except ProviderOperationError:
            raise
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise ProviderOperationError("Facebook thread listing failed.") from error

    async def send_text(
        self,
        provider_data: dict[str, Any],
        *,
        thread_id: str,
        text: str,
        thread_type: str = "user",
        reply_to_message_id: str | None = None,
    ) -> dict[str, Any]:
        try:
            result = await SendAPI().send(
                provider_data,
                text,
                thread_id,
                typeChat="user" if thread_type == "user" else None,
                replyMessage=bool(reply_to_message_id),
                messageID=reply_to_message_id,
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise ProviderOperationError("Facebook message delivery failed.") from error

        if result.get("success") != 1:
            raise ProviderOperationError("Facebook did not confirm message delivery.")
        payload = result.get("payload") or {}
        message_id = str(payload.get("messageID") or "").strip()
        if not message_id:
            raise ProviderOperationError("Facebook did not return a message ID.")
        return {
            "messageId": message_id,
            "threadId": thread_id,
            "status": "sent",
            "timestamp": payload.get("timestamp"),
        }

    async def react_message(
        self,
        provider_data: dict[str, Any],
        *,
        message_id: str,
        emoji: str,
        action: str = "add",
    ) -> dict[str, Any]:
        try:
            act = (
                "ADD_REACTION"
                if action.lower() in {"add", "add_reaction"}
                else "REMOVE_REACTION"
            )
            response = await react_func(provider_data, act, message_id, emoji)
            if hasattr(response, "status_code") and response.status_code >= 400:
                raise ProviderOperationError(
                    f"Facebook reaction failed with status {response.status_code}."
                )
            return {
                "messageId": message_id,
                "emoji": emoji,
                "action": "add" if act == "ADD_REACTION" else "remove",
                "status": "confirmed",
            }
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise ProviderOperationError("Facebook reaction failed.") from error

    async def unsend_message(
        self, provider_data: dict[str, Any], *, message_id: str
    ) -> dict[str, Any]:
        try:
            result = await unsend_func(message_id, provider_data)
            if result.get("error"):
                raise ProviderOperationError(
                    str(result.get("messages") or "Facebook rejected unsend.")
                )
            return {"messageId": message_id, "status": "revoked"}
        except ProviderOperationError:
            raise
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise ProviderOperationError("Facebook message revoke failed.") from error

    async def get_user_info(
        self, provider_data: dict[str, Any], *, user_id: str
    ) -> dict[str, Any]:
        try:
            result = await get_user_info_func(provider_data, user_id)
            if result.get("error"):
                raise ProviderOperationError(
                    str(result.get("messages") or "User not found.")
                )
            return {
                "userId": str(result.get("idUser") or user_id),
                "name": result.get("nameUser"),
                "firstName": result.get("firstName"),
                "username": result.get("Username"),
                "gender": result.get("genderUser"),
                "isNonFriend": bool(result.get("chatWithUSerIsNonFriend")),
            }
        except ProviderOperationError:
            raise
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise ProviderOperationError("Facebook user lookup failed.") from error

    async def search_users(
        self, provider_data: dict[str, Any], *, query: str
    ) -> list[dict[str, Any]]:
        try:
            result = await search_func(provider_data, query)
            if result.get("error"):
                raise ProviderOperationError(
                    str(result.get("messages") or "Search failed.")
                )
            items = result.get("searchResultsDict") or []
            return [
                {
                    "userId": str(item.get("id") or ""),
                    "name": item.get("name"),
                    "url": item.get("url"),
                }
                for item in items
                if str(item.get("id") or "").strip()
            ]
        except ProviderOperationError:
            raise
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise ProviderOperationError("Facebook user search failed.") from error

    async def block_user(
        self, provider_data: dict[str, Any], *, user_id: str, action: str = "block"
    ) -> dict[str, Any]:
        try:
            clean_action = "block" if action.lower() == "block" else "unblock"
            result = await blocking_func(provider_data, user_id, clean_action)
            if result.get("error"):
                raise ProviderOperationError(
                    str(result.get("messages") or "Block operation failed.")
                )
            return {"userId": user_id, "action": clean_action, "status": "confirmed"}
        except ProviderOperationError:
            raise
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise ProviderOperationError("Facebook block operation failed.") from error

    async def get_marketplace_item(
        self, provider_data: dict[str, Any], *, item_id: str
    ) -> dict[str, Any]:
        try:
            result = await get_marketplace_item_func(provider_data, item_id)
            if result.get("error"):
                raise ProviderOperationError(
                    str(result.get("messages") or "Item not found.")
                )
            payload = result.get("payload") or {}
            return {
                "itemId": str(payload.get("idProduct") or item_id),
                "name": payload.get("nameProduct"),
                "price": payload.get("priceProduct"),
                "currency": payload.get("currencyProduct"),
                "description": payload.get("decriptionProduct"),
                "url": payload.get("urlProduct"),
                "sellerId": payload.get("idSeller"),
                "status": "experimental",
            }
        except ProviderOperationError:
            raise
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise ProviderOperationError(
                "Facebook marketplace lookup failed."
            ) from error

    async def send_attachment(
        self,
        provider_data: dict[str, Any],
        *,
        thread_id: str,
        file_path: str,
        thread_type: str = "user",
        text: str = "",
    ) -> dict[str, Any]:
        path = Path(file_path)
        if not path.is_file():
            raise ProviderOperationError("Attachment file does not exist.")

        try:
            uploaded = await upload_attachment_func(str(path), provider_data)
            if not uploaded or not uploaded.get("attachmentID"):
                raise ProviderOperationError("Facebook attachment upload failed.")

            att_id = uploaded["attachmentID"]
            att_type = uploaded.get("typeAttachment") or "file"

            result = await SendAPI().send(
                provider_data,
                text,
                thread_id,
                typeAttachment=att_type,
                attachmentID=att_id,
                typeChat="user" if thread_type == "user" else None,
            )
        except ProviderOperationError:
            raise
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise ProviderOperationError(
                "Facebook attachment delivery failed."
            ) from error

        if result.get("success") != 1:
            raise ProviderOperationError("Facebook did not confirm message delivery.")
        payload = result.get("payload") or {}
        message_id = str(payload.get("messageID") or "").strip()
        return {
            "messageId": message_id,
            "threadId": thread_id,
            "status": "sent",
            "attachmentType": att_type,
            "timestamp": payload.get("timestamp"),
        }
