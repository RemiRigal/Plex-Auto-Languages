from typing import List, Union
from apprise import Apprise

from plex_auto_languages.constants import EventType


class Notifier():

    def __init__(self, configs: List[Union[str, dict]]):
        self._global_apprise = ConditionalApprise()
        self._user_apprise = {}

        for config in configs:
            if isinstance(config, str):
                self._add_urls([config])
            if isinstance(config, dict) and "urls" in config:
                urls = config.get("urls")
                urls = [urls] if isinstance(urls, str) else urls
                usernames = config.get("users", None)
                if usernames is None:
                    usernames = []
                elif isinstance(usernames, str):
                    usernames = [usernames]
                event_types = config.get("events", None)
                if event_types is None:
                    event_types = []
                elif isinstance(event_types, str):
                    event_types = [EventType[event_types.upper()]]
                elif isinstance(event_types, list):
                    event_types = [EventType[et.upper()] for et in event_types]
                self._add_urls(urls, usernames, event_types)

    def _add_urls(self, urls: List[str], usernames: List[str] = None, event_types: List[EventType] = None):
        if usernames is None or len(usernames) == 0:
            for url in urls:
                self._global_apprise.add(url)
            if event_types is not None:
                self._global_apprise.add_event_types(event_types)
            return
        for username in usernames:
            user_apprise = self._user_apprise.setdefault(username, ConditionalApprise())
            for url in urls:
                user_apprise.add(url)
            if event_types is not None:
                user_apprise.add_event_types(event_types)

    def notify(self, title: str, message: str, event_type: EventType):
        self._global_apprise.notifiy_if_needed(title, message, event_type)

    def notify_user(self, title: str, message: str, username: str, event_type: EventType):
        self._global_apprise.notifiy_if_needed(title, message, event_type)
        if username is None or username not in self._user_apprise:
            return
        user_apprise = self._user_apprise[username]
        user_apprise.notifiy_if_needed(title, message, event_type)


class ConditionalApprise(Apprise):

    def __init__(self):
        super().__init__()
        self._event_types = set()

    def add_event_type(self, event_type: EventType):
        self._event_types.add(event_type)

    def add_event_types(self, event_types: List[EventType]):
        for event_type in event_types:
            self.add_event_type(event_type)

    def notifiy_if_needed(self, title: str, body: str, event_type: EventType):
        if len(self._event_types) != 0 and event_type not in self._event_types:
            return
        self.notify(title=title, body=body)
