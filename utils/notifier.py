from typing import List, Union
from apprise import Apprise

from utils.logger import get_logger


logger = get_logger()


class Notifier(object):

    def __init__(self, configs: List[Union[str, dict]]):
        self._global_apprise = Apprise()
        self._user_apprise = {}

        for config in configs:
            if isinstance(config, str):
                self._add_urls([config], None)
            if isinstance(config, dict) and "urls" in config:
                targets = config.get("urls")
                targets = [targets] if isinstance(targets, str) else targets
                usernames = config.get("users", None)
                self._add_urls(targets, usernames)

    def _add_urls(self, urls: List[str], usernames: List[str] = None):
        if usernames is None or len(usernames) == 0:
            for url in urls:
                self._global_apprise.add(url)
            return
        for username in usernames:
            user_apprise = self._user_apprise.setdefault(username, Apprise())
            for url in urls:
                user_apprise.add(url)

    def notify(self, username: str, title: str, message: str):
        self._global_apprise.notify(title=title, body=message)
        if username is None or username not in self._user_apprise:
            return
        for user_apprise in self._user_apprise[username]:
            user_apprise.notify(title=title, body=message)
