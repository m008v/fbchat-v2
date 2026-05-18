"""
fbchat-v2 — modern, account-based Python library for the unofficial Facebook
Messenger API (with E2EE support via Go bridge).

Public re-exports:
    listeningEvent       — group-message MQTT listener
    listeningE2EEEvent   — 1-on-1 E2EE listener (requires Go bridge binary)
    sendingE2EEEvent     — 1-on-1 E2EE sender (requires Go bridge binary)
    editMessage          — Edit sent Messenger messages via MQTT LS task
    changeTheme          — List/change Messenger thread themes/backgrounds
    createNotes          — Messenger Notes (24h status): check / create / delete / recreate
    dataGetHome          — bootstrap dataFB session dict from cookies

Xem README để biết chi tiết.
"""

from __future__ import annotations

__version__ = "2.1.5"
__author__ = "MinhHuyDev"
__license__ = "MIT"

from ._core._session import dataGetHome
from ._messaging._listening import listeningEvent
from ._messaging._listening_e2ee import listeningE2EEEvent
from ._messaging._send_e2ee import sendingE2EEEvent
from ._messaging import _editMessage as editMessage
from ._messaging import _changeTheme as changeTheme
from ._messaging import _createNotes as createNotes

__all__ = [
    "__version__",
    "__author__",
    "__license__",
    "dataGetHome",
    "listeningEvent",
    "listeningE2EEEvent",
    "sendingE2EEEvent",
    "editMessage",
    "changeTheme",
    "createNotes",
]
