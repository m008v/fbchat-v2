"""API mức cao cho các JSON-RPC action của bridge E2EE."""

from __future__ import annotations

import base64
from typing import Any

from _messaging._listening_e2ee import _BridgeProcess
from _messaging._send_e2ee import normalize_chat_jid


class BridgeActions:
    def __init__(self, bridge: _BridgeProcess) -> None:
        self._bridge = bridge

    def _call_sync(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        return self._bridge.call_sync(method, params)

    async def _call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        return await self._bridge.call(method, params)

    def edit_message_sync(self, message_id: str, new_text: str) -> dict[str, Any]:
        return self._call_sync("editMessage", {"messageId": message_id, "newText": new_text})

    async def edit_message(
        self, message_id: str, new_text: str
    ) -> dict[str, Any]:
        return await self._call(
            "editMessage", {"messageId": message_id, "newText": new_text}
        )

    def unsend_message_sync(self, message_id: str) -> dict[str, Any]:
        return self._call_sync("unsendMessage", {"messageId": message_id})

    async def unsend_message(self, message_id: str) -> dict[str, Any]:
        return await self._call("unsendMessage", {"messageId": message_id})

    @staticmethod
    def _e2ee_message_params(
        chat_jid: str, message_id: str, new_text: str | None = None
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "chatJid": normalize_chat_jid(chat_jid),
            "messageId": message_id,
        }
        if new_text is not None:
            params["newText"] = new_text
        return params

    def edit_e2ee_message_sync(
        self, chat_jid: str, message_id: str, new_text: str
    ) -> dict[str, Any]:
        return self._call_sync(
            "editE2EEMessage",
            self._e2ee_message_params(chat_jid, message_id, new_text),
        )

    async def edit_e2ee_message(
        self, chat_jid: str, message_id: str, new_text: str
    ) -> dict[str, Any]:
        return await self._call(
            "editE2EEMessage",
            self._e2ee_message_params(chat_jid, message_id, new_text),
        )

    def unsend_e2ee_message_sync(self, chat_jid: str, message_id: str) -> dict[str, Any]:
        return self._call_sync(
            "unsendE2EEMessage", self._e2ee_message_params(chat_jid, message_id)
        )

    async def unsend_e2ee_message(
        self, chat_jid: str, message_id: str
    ) -> dict[str, Any]:
        return await self._call(
            "unsendE2EEMessage", self._e2ee_message_params(chat_jid, message_id)
        )

    def send_typing_indicator_sync(
        self,
        thread_id: int,
        is_typing: bool,
        is_group: bool = False,
        thread_type: int = 1,
    ) -> dict[str, Any]:
        return self._call_sync(
            "sendTypingIndicator",
            {
                "threadId": thread_id,
                "isTyping": is_typing,
                "isGroup": is_group,
                "threadType": thread_type,
            },
        )

    async def send_typing_indicator(
        self,
        thread_id: int,
        is_typing: bool,
        is_group: bool = False,
        thread_type: int = 1,
    ) -> dict[str, Any]:
        return await self._call(
            "sendTypingIndicator",
            {
                "threadId": thread_id,
                "isTyping": is_typing,
                "isGroup": is_group,
                "threadType": thread_type,
            },
        )

    def mark_read_sync(self, thread_id: int, watermark_ts: int) -> dict[str, Any]:
        return self._call_sync(
            "markRead", {"threadId": thread_id, "watermarkTs": watermark_ts}
        )

    async def mark_read(
        self, thread_id: int, watermark_ts: int
    ) -> dict[str, Any]:
        return await self._call(
            "markRead", {"threadId": thread_id, "watermarkTs": watermark_ts}
        )

    def send_e2ee_typing_sync(self, chat_jid: str, is_typing: bool) -> dict[str, Any]:
        return self._call_sync(
            "sendE2EETyping",
            {"chatJid": normalize_chat_jid(chat_jid), "isTyping": is_typing},
        )

    async def send_e2ee_typing(
        self, chat_jid: str, is_typing: bool
    ) -> dict[str, Any]:
        return await self._call(
            "sendE2EETyping",
            {"chatJid": normalize_chat_jid(chat_jid), "isTyping": is_typing},
        )

    @staticmethod
    def _audio_params(
        chat_jid: str,
        data: bytes,
        mime_type: str,
        duration: int,
        ptt: bool,
        reply_to_id: str,
        reply_to_sender_jid: str,
    ) -> dict[str, Any]:
        return {
            "chatJid": normalize_chat_jid(chat_jid),
            "data": base64.b64encode(data).decode("ascii"),
            "mimeType": mime_type,
            "duration": duration,
            "ptt": ptt,
            "replyToId": reply_to_id,
            "replyToSenderJid": reply_to_sender_jid,
        }

    def send_e2ee_audio_sync(
        self,
        chat_jid: str,
        data: bytes,
        mime_type: str = "audio/ogg; codecs=opus",
        duration: int = 0,
        ptt: bool = True,
        reply_to_id: str = "",
        reply_to_sender_jid: str = "",
    ) -> dict[str, Any]:
        return self._call_sync(
            "sendE2EEAudio",
            self._audio_params(
                chat_jid,
                data,
                mime_type,
                duration,
                ptt,
                reply_to_id,
                reply_to_sender_jid,
            ),
        )

    async def send_e2ee_audio(
        self,
        chat_jid: str,
        data: bytes,
        mime_type: str = "audio/ogg; codecs=opus",
        duration: int = 0,
        ptt: bool = True,
        reply_to_id: str = "",
        reply_to_sender_jid: str = "",
    ) -> dict[str, Any]:
        return await self._call(
            "sendE2EEAudio",
            self._audio_params(
                chat_jid,
                data,
                mime_type,
                duration,
                ptt,
                reply_to_id,
                reply_to_sender_jid,
            ),
        )

    @staticmethod
    def _image_params(
        chat_jid: str,
        data: bytes,
        mime_type: str,
        caption: str,
        width: int,
        height: int,
        reply_to_id: str,
        reply_to_sender_jid: str,
    ) -> dict[str, Any]:
        return {
            "chatJid": normalize_chat_jid(chat_jid),
            "data": base64.b64encode(data).decode("ascii"),
            "mimeType": mime_type,
            "caption": caption,
            "width": width,
            "height": height,
            "replyToId": reply_to_id,
            "replyToSenderJid": reply_to_sender_jid,
        }

    def send_e2ee_image_sync(
        self,
        chat_jid: str,
        data: bytes,
        mime_type: str = "image/jpeg",
        caption: str = "",
        width: int = 0,
        height: int = 0,
        reply_to_id: str = "",
        reply_to_sender_jid: str = "",
    ) -> dict[str, Any]:
        return self._call_sync(
            "sendE2EEImage",
            self._image_params(
                chat_jid,
                data,
                mime_type,
                caption,
                width,
                height,
                reply_to_id,
                reply_to_sender_jid,
            ),
        )

    async def send_e2ee_image(
        self,
        chat_jid: str,
        data: bytes,
        mime_type: str = "image/jpeg",
        caption: str = "",
        width: int = 0,
        height: int = 0,
        reply_to_id: str = "",
        reply_to_sender_jid: str = "",
    ) -> dict[str, Any]:
        return await self._call(
            "sendE2EEImage",
            self._image_params(
                chat_jid,
                data,
                mime_type,
                caption,
                width,
                height,
                reply_to_id,
                reply_to_sender_jid,
            ),
        )

    def download_media_sync(self, url: str) -> bytes:
        result = self._call_sync("downloadMedia", {"url": url})
        return base64.b64decode(result["data"], validate=True)

    async def download_media(self, url: str) -> bytes:
        result = await self._call("downloadMedia", {"url": url})
        return base64.b64decode(result["data"], validate=True)

    @staticmethod
    def _download_e2ee_params(
        direct_path: str,
        media_key: str,
        media_sha256: str,
        media_enc_sha256: str,
        media_type: str,
        mime_type: str,
        file_size: int,
    ) -> dict[str, Any]:
        return {
            "directPath": direct_path,
            "mediaKey": media_key,
            "mediaSha256": media_sha256,
            "mediaEncSha256": media_enc_sha256,
            "mediaType": media_type,
            "mimeType": mime_type,
            "fileSize": file_size,
        }

    @staticmethod
    def _decode_media_result(result: dict[str, Any]) -> dict[str, Any]:
        if isinstance(result.get("data"), str):
            result = dict(result)
            result["data"] = base64.b64decode(result["data"], validate=True)
        return result

    def download_e2ee_media_sync(
        self,
        direct_path: str,
        media_key: str,
        media_sha256: str,
        media_enc_sha256: str,
        media_type: str,
        mime_type: str,
        file_size: int,
    ) -> dict[str, Any]:
        result = self._call_sync(
            "downloadE2EEMedia",
            self._download_e2ee_params(
                direct_path,
                media_key,
                media_sha256,
                media_enc_sha256,
                media_type,
                mime_type,
                file_size,
            ),
        )
        return self._decode_media_result(result)

    async def download_e2ee_media(
        self,
        direct_path: str,
        media_key: str,
        media_sha256: str,
        media_enc_sha256: str,
        media_type: str,
        mime_type: str,
        file_size: int,
    ) -> dict[str, Any]:
        result = await self._call(
            "downloadE2EEMedia",
            self._download_e2ee_params(
                direct_path,
                media_key,
                media_sha256,
                media_enc_sha256,
                media_type,
                mime_type,
                file_size,
            ),
        )
        return self._decode_media_result(result)

# Backwards-compatible aliases for the old `_async` API.
BridgeActions.edit_message_async = BridgeActions.edit_message
BridgeActions.unsend_message_async = BridgeActions.unsend_message
BridgeActions.edit_e2ee_message_async = BridgeActions.edit_e2ee_message
BridgeActions.unsend_e2ee_message_async = BridgeActions.unsend_e2ee_message
BridgeActions.send_typing_indicator_async = BridgeActions.send_typing_indicator
BridgeActions.mark_read_async = BridgeActions.mark_read
BridgeActions.send_e2ee_typing_async = BridgeActions.send_e2ee_typing
BridgeActions.send_e2ee_audio_async = BridgeActions.send_e2ee_audio
BridgeActions.send_e2ee_image_async = BridgeActions.send_e2ee_image
BridgeActions.download_media_async = BridgeActions.download_media
BridgeActions.download_e2ee_media_async = BridgeActions.download_e2ee_media
