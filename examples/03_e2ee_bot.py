"""Bot /ping và /echo cho đúng một hội thoại E2EE có Go bridge."""

import asyncio

from fbchat_v2 import ReconnectPolicy, listeningE2EEEvent

from _common import login, required_env, run, stop_listener


async def main() -> None:
    chat_jid = required_env("FB_CHAT_JID")
    session = await login()
    listener = listeningE2EEEvent(
        session, reconnect_policy=ReconnectPolicy(max_attempts=5)
    )
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[dict[str, object]] = asyncio.Queue(maxsize=1000)
    dropped = 0

    def enqueue(event: dict[str, object]) -> None:
        nonlocal dropped
        if queue.full():
            dropped += 1
            if dropped & (dropped - 1) == 0:
                print(f"Queue E2EE đầy; đã bỏ {dropped} event, không log nội dung.")
            return
        queue.put_nowait(event)

    def receive(event: dict[str, object]) -> None:
        if event.get("type") == "e2eeMessage":
            loop.call_soon_threadsafe(enqueue, event)

    listener.on_message(receive)
    task = asyncio.create_task(listener.connect_mqtt())
    try:
        while not await asyncio.to_thread(
            listener.wait_until_connected, listener.startup_timeout, require_e2ee=True
        ):
            if task.done():
                await task
                raise RuntimeError("Listener dừng trước khi E2EE sẵn sàng.")
            if listener.connection_state != "reconnecting":
                raise RuntimeError("E2EE chưa sẵn sàng trước timeout.")
        print("E2EE READY; gửi /ping hoặc /echo <nội dung> vào hội thoại đã chọn.")
        while not task.done():
            try:
                event = await asyncio.wait_for(queue.get(), timeout=1)
            except asyncio.TimeoutError:
                continue
            data = event.get("data")
            if not isinstance(data, dict) or data.get("chatJid") != chat_jid:
                continue
            text = data.get("text")
            sender = str(data.get("senderId") or "")
            if (
                not sender
                or sender == str(session["FacebookID"])
                or not data.get("id")
                or not isinstance(text, str)
                or len(text) > 2000
            ):
                continue
            reply = "pong" if text == "/ping" else text.removeprefix("/echo ")
            if text != "/ping" and (not text.startswith("/echo ") or not reply.strip()):
                continue
            result = await listener.send_e2ee_message(
                chat_jid,
                reply,
                reply_to_id=str(data["id"]),
                reply_to_sender_jid=str(data.get("senderJid") or ""),
            )
            if result.get("deliveryStatus") == "unknown":
                print("Kết quả gửi unknown; không tự retry vì có thể gửi trùng.")
        await task
    finally:
        await stop_listener(task)


if __name__ == "__main__":
    run(main())
