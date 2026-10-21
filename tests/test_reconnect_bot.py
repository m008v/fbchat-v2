from __future__ import annotations

import asyncio
import threading
from typing import Any

import pytest

import main as sample_main


class _RetryingListener:
    startup_timeout = 0.01

    def __init__(self) -> None:
        self.connection_state = "reconnecting"
        self.calls = 0
        self.ready = threading.Event()
        self.stopped = threading.Event()

    def on_message(self, callback: Any) -> None:
        self.callback = callback

    async def connect_mqtt(self) -> None:
        while not self.stopped.is_set():
            await asyncio.sleep(0.001)

    def wait_until_connected(self, timeout: float, *, require_e2ee: bool) -> bool:
        assert timeout == self.startup_timeout
        assert require_e2ee
        self.calls += 1
        if self.calls == 1:
            return False
        self.connection_state = "connected"
        self.ready.set()
        return True

    def stop(self) -> None:
        self.connection_state = "stopped"
        self.stopped.set()


@pytest.mark.asyncio
async def test_sample_bot_keeps_waiting_while_startup_is_reconnecting(
    monkeypatch: pytest.MonkeyPatch, mock_dataFB: dict[str, Any]
) -> None:
    listener = _RetryingListener()
    monkeypatch.setattr(
        sample_main, "listeningE2EEEvent", lambda *args, **kwargs: listener
    )
    bot = sample_main.SimpleBot(mock_dataFB)
    task = asyncio.create_task(bot.run())
    try:
        assert await asyncio.to_thread(listener.ready.wait, 2.0)
        assert listener.calls == 2
        assert not task.done()
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert listener.stopped.is_set()
    assert not [
        item
        for item in asyncio.all_tasks()
        if item.get_name() == "fbchat-e2ee-listener" and not item.done()
    ]
