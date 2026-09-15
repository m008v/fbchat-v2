"""Public namespace for the fbchat-v2 distribution."""

from __future__ import annotations

from ._core import __version__
from ._core._session import dataGetHome
from ._core._storage import EnvSessionStorage, FileSessionStorage
from ._messaging import _changeTheme as changeTheme
from ._messaging import _createNotes as createNotes
from ._messaging import _editMessage as editMessage
from ._messaging._bridge_actions import BridgeActions
from ._messaging._listening import listeningEvent
from ._messaging._listening_e2ee import listeningE2EEEvent
from ._messaging._send import api as SendAPI
from ._messaging._send_e2ee import api as E2EESendAPI

__author__ = "MinhHuyDev"
__license__ = "Apache-2.0"
sendingE2EEEvent = E2EESendAPI

__all__ = [
    "__version__",
    "__author__",
    "__license__",
    "dataGetHome",
    "EnvSessionStorage",
    "FileSessionStorage",
    "listeningEvent",
    "listeningE2EEEvent",
    "BridgeActions",
    "SendAPI",
    "E2EESendAPI",
    "sendingE2EEEvent",
    "editMessage",
    "changeTheme",
    "createNotes",
]
