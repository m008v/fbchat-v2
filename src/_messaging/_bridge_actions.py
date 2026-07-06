"""
fbchat-v2 :: _bridge_actions.py
===============================

Python wrapper for all bridge RPC methods introduced in Track 6.
"""

from __future__ import annotations

from typing import Any, Optional
from _messaging._listening_e2ee import _BridgeProcess, BridgeError
from _messaging._send_e2ee import normalize_chat_jid

class BridgeActions:
    """High-level Python API for all bridge RPC methods."""
    
    def __init__(self, bridge: _BridgeProcess):
        self._bridge = bridge

    def edit_message(self, message_id: str, new_text: str) -> dict[str, Any]:
        return self._bridge.call("editMessage", {
            "messageId": message_id,
            "newText": new_text
        })

    def unsend_message(self, message_id: str) -> dict[str, Any]:
        return self._bridge.call("unsendMessage", {
            "messageId": message_id
        })

    def edit_e2ee_message(self, chat_jid: str, message_id: str, new_text: str) -> dict[str, Any]:
        return self._bridge.call("editE2EEMessage", {
            "chatJid": normalize_chat_jid(chat_jid),
            "messageId": message_id,
            "newText": new_text
        })

    def unsend_e2ee_message(self, chat_jid: str, message_id: str) -> dict[str, Any]:
        return self._bridge.call("unsendE2EEMessage", {
            "chatJid": normalize_chat_jid(chat_jid),
            "messageId": message_id
        })

    def send_typing_indicator(self, thread_id: int, is_typing: bool, is_group: bool = False, thread_type: int = 1) -> dict[str, Any]:
        return self._bridge.call("sendTypingIndicator", {
            "threadId": thread_id,
            "isTyping": is_typing,
            "isGroup": is_group,
            "threadType": thread_type
        })

    def mark_read(self, thread_id: int, watermark_ts: int) -> dict[str, Any]:
        return self._bridge.call("markRead", {
            "threadId": thread_id,
            "watermarkTs": watermark_ts
        })

    def send_e2ee_typing(self, chat_jid: str, is_typing: bool) -> dict[str, Any]:
        return self._bridge.call("sendE2EETyping", {
            "chatJid": normalize_chat_jid(chat_jid),
            "isTyping": is_typing
        })

    def send_e2ee_audio(self, chat_jid: str, data: bytes, mime_type: str = "audio/ogg; codecs=opus", duration: int = 0, ptt: bool = True, reply_to_id: str = "", reply_to_sender_jid: str = "") -> dict[str, Any]:
        import base64
        return self._bridge.call("sendE2EEAudio", {
            "chatJid": normalize_chat_jid(chat_jid),
            "data": base64.b64encode(data).decode('ascii'),
            "mimeType": mime_type,
            "duration": duration,
            "ptt": ptt,
            "replyToId": reply_to_id,
            "replyToSenderJid": reply_to_sender_jid
        })

    def send_e2ee_image(self, chat_jid: str, data: bytes, mime_type: str = "image/jpeg", caption: str = "", width: int = 0, height: int = 0, reply_to_id: str = "", reply_to_sender_jid: str = "") -> dict[str, Any]:
        import base64
        return self._bridge.call("sendE2EEImage", {
            "chatJid": normalize_chat_jid(chat_jid),
            "data": base64.b64encode(data).decode('ascii'),
            "mimeType": mime_type,
            "caption": caption,
            "width": width,
            "height": height,
            "replyToId": reply_to_id,
            "replyToSenderJid": reply_to_sender_jid
        })

    def download_media(self, url: str) -> bytes:
        import base64
        res = self._bridge.call("downloadMedia", {
            "url": url
        })
        return base64.b64decode(res["data"])

    def download_e2ee_media(self, direct_path: str, media_key: str, media_sha256: str, media_enc_sha256: str, media_type: str, mime_type: str, file_size: int) -> dict[str, Any]:
        # media_key, media_sha256, media_enc_sha256 should be base64 strings
        res = self._bridge.call("downloadE2EEMedia", {
            "directPath": direct_path,
            "mediaKey": media_key,
            "mediaSha256": media_sha256,
            "mediaEncSha256": media_enc_sha256,
            "mediaType": media_type,
            "mimeType": mime_type,
            "fileSize": file_size
        })
        import base64
        # Decode the actual data back to bytes for python consumption, although we can just return the dict
        if "data" in res and isinstance(res["data"], str):
            res["data"] = base64.b64decode(res["data"])
        return res
