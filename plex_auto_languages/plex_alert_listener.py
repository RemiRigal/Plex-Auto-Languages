from __future__ import annotations
from typing import Callable
from websocket import WebSocketApp
from plexapi.alert import AlertListener
from plexapi.server import PlexServer as BasePlexServer

from plex_auto_languages.utils.logger import get_logger


logger = get_logger()


class PlexAlertListener(AlertListener):

    def __init__(self, server: BasePlexServer, callback: Callable = None, callbackError: Callable = None):
        super().__init__(server, callback, callbackError)

    def run(self):
        url = self._server.url(self.key, includeToken=True).replace("http", "ws")
        self._ws = WebSocketApp(url, on_message=self._onMessage, on_error=self._onError)
        self._ws.run_forever(skip_utf8_validation=True)
