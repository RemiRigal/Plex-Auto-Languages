from typing import List, Union
from apprise import Apprise
from plexapi.video import Episode
from plexapi.media import AudioStream, SubtitleStream

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
                usernames = [usernames] if isinstance(usernames, str) else usernames
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


class NotificationBuilder(object):

    def __init__(self):
        self._message = ""
        self._username = None
        self._audio_stream = None
        self._subtitle_stream = None
        self._episode = None
        self._episodes = None
        self._nb_updated = None
        self._nb_total = None

    def build(self, inline: bool = False):
        separator = " | " if inline else "\n"
        season_numbers = [e.seasonNumber for e in self._episodes]
        min_season_number, max_season_number = min(season_numbers), max(season_numbers)
        min_episode_number = min([e.episodeNumber for e in self._episodes if e.seasonNumber == min_season_number])
        max_episode_number = max([e.episodeNumber for e in self._episodes if e.seasonNumber == max_season_number])
        from_str = f"S{min_season_number:02}E{min_episode_number:02}"
        to_str = f"S{max_season_number:02}E{max_episode_number:02}"
        range_str = f"{from_str} - {to_str}" if from_str != to_str else from_str
        title = f"PlexAutoLanguages - {self._episode.show().title}"
        message = (
            f"Show: {self._episode.show().title}{separator}"
            f"User: {self._username}{separator}"
            f"Audio: {self._audio_stream.displayTitle if self._audio_stream is not None else 'None'}{separator}"
            f"Subtitles: {self._subtitle_stream.displayTitle if self._subtitle_stream is not None else 'None'}{separator}"
            f"Updated episodes: {self._nb_updated}/{self._nb_total} ({range_str})"
        )
        return title, message

    def username(self, username: str):
        self._username = username

    def audio_stream(self, audio_stream: AudioStream):
        self._audio_stream = audio_stream

    def subtitle_stream(self, subtitle_stream: SubtitleStream):
        self._subtitle_stream = subtitle_stream

    def episode(self, episode: Episode):
        self._episode = episode

    def episodes(self, episodes: List[Episode]):
        self._episodes = episodes

    def nb_updated(self, nb_updated: int):
        self._nb_updated = nb_updated

    def nb_total(self, nb_total: int):
        self._nb_total = nb_total
