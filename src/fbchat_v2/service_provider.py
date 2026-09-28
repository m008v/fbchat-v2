"""Sanitized provider operations exposed by the REST boundary."""

from __future__ import annotations

import json
from typing import Any

import httpx

from ._features._thread._all_thread_data import func as fetch_thread_data
from ._messaging._send import api as SendAPI


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
    """Small async adapter over the existing fbchat-v2 feature modules."""

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
        thread_type: str,
        reply_to_message_id: str | None,
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
