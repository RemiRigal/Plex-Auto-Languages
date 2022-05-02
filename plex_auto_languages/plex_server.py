import sys
import itertools
from typing import List, Union
from datetime import datetime, timedelta
from plexapi.media import MediaPart
from plexapi.library import ShowSection
from plexapi.video import Episode, Show
from plexapi.exceptions import NotFound
from plexapi.server import PlexServer as BasePlexServer

from plex_auto_languages.utils.logger import get_logger
from plex_auto_languages.utils.configuration import Configuration
from plex_auto_languages.plex_alert_handler import PlexAlertHandler
from plex_auto_languages.track_changes import TrackChanges
from plex_auto_languages.utils.notifier import Notifier
from plex_auto_languages.plex_server_cache import PlexServerCache


logger = get_logger()


class UnprivilegedPlexServer():

    def __init__(self, url: str, token: str):
        self._plex_url = url
        self._plex = BasePlexServer(url, token)

    @property
    def unique_id(self):
        return self._plex.machineIdentifier

    def fetch_item(self, item_id: Union[str, int]):
        try:
            return self._plex.fetchItem(item_id)
        except NotFound:
            return None

    def episodes(self):
        return self._plex.library.all(libtype="episode")

    def get_recently_added_episodes(self, minutes: int):
        episodes = []
        for section in self.get_show_sections():
            recent = section.searchEpisodes(filters={"addedAt>>": f"{minutes}m"})
            episodes.extend(recent)
        return episodes

    def get_show_sections(self):
        return [s for s in self._plex.library.sections() if isinstance(s, ShowSection)]

    @staticmethod
    def get_last_watched_or_first_episode(show: Show):
        watched_episodes = show.watched()
        if len(watched_episodes) == 0:
            all_episodes = show.episodes()
            if len(all_episodes) == 0:
                return None
            return all_episodes[0]
        return watched_episodes[-1]

    @staticmethod
    def get_selected_streams(episode: Union[Episode, MediaPart]):
        audio_stream = ([a for a in episode.audioStreams() if a.selected] + [None])[0]
        subtitle_stream = ([s for s in episode.subtitleStreams() if s.selected] + [None])[0]
        return audio_stream, subtitle_stream

    @staticmethod
    def get_episode_short_name(episode: Episode, include_show: bool = True):
        if include_show:
            return f"'{episode.show().title}' (S{episode.seasonNumber:02}E{episode.episodeNumber:02})"
        return f"S{episode.seasonNumber:02}E{episode.episodeNumber:02}"


class PlexServer(UnprivilegedPlexServer):

    def __init__(self, url: str, token: str, notifier: Notifier, config: Configuration):
        super().__init__(url, token)
        self.notifier = notifier
        self.config = config
        self.user_id, self.username = self._get_user_id()
        if self.user_id is None:
            logger.error("Unable to find the user associated with the provided Plex Token")
            sys.exit(0)
        else:
            logger.info(f"Successfully connected as user '{self.username}' (id: {self.user_id})")
        self._alert_handler = None
        self._alert_listener = None
        self.cache = PlexServerCache(self)

    @property
    def is_alive(self):
        return self._alert_listener is not None and self._alert_listener.is_alive()

    def _get_user_id(self):
        plex_username = self._plex.myPlexAccount().username
        for account in self._plex.systemAccounts():
            if account.name == plex_username:
                return account.id, account.name
        return None, None

    def start_alert_listener(self):
        trigger_on_play = self.config.get("trigger_on_play")
        trigger_on_scan = self.config.get("trigger_on_scan")
        trigger_on_activity = self.config.get("trigger_on_activity")
        self._alert_handler = PlexAlertHandler(self, trigger_on_play, trigger_on_scan, trigger_on_activity)
        self._alert_listener = self._plex.startAlertListener(self._alert_handler)

    def get_all_user_ids(self):
        return [self.user_id] + [user.id for user in self._plex.myPlexAccount().users()]

    def get_plex_instance_of_user(self, user_id: Union[int, str]):
        if str(self.user_id) == str(user_id):
            return self
        matching_users = [u for u in self._plex.myPlexAccount().users() if str(u.id) == str(user_id)]
        if len(matching_users) == 0:
            logger.error(f"Unable to find user with id '{user_id}'")
            return None
        user_token = matching_users[0].get_token(self._plex.machineIdentifier)
        return UnprivilegedPlexServer(self._plex_url, user_token)

    def get_user_from_client_identifier(self, client_identifier: str):
        plex_sessions = self._plex.sessions()
        current_players = list(itertools.chain.from_iterable([s.players for s in plex_sessions]))
        matching_players = [p for p in current_players if p.machineIdentifier == client_identifier]
        if len(matching_players) == 0:
            return (None, None)
        player = matching_players[0]
        user = self.get_user_by_id(player.userID)
        if user is None:
            return (None, None)
        return (user.id, user.name)

    def get_user_by_id(self, user_id: Union[int, str]):
        matching_users = [u for u in self._plex.systemAccounts() if str(u.id) == str(user_id)]
        if len(matching_users) == 0:
            return None
        return matching_users[0]

    def process_new_or_updated_episode(self, item_id: Union[int, str]):
        for user_id in self.get_all_user_ids():
            # Switch to the user's Plex instance
            user_plex = self.get_plex_instance_of_user(user_id)
            if user_plex is None:
                continue

            # Get the most recently watched episode or the first one of the show
            user_item = user_plex.fetch_item(item_id)
            if user_item is None:
                continue
            reference = user_plex.get_last_watched_or_first_episode(user_item.show())
            if reference is None:
                continue

            # Change tracks
            reference.reload()
            user_item.reload()
            user = self.get_user_by_id(user_id)
            if user is None:
                return
            self.change_default_tracks_if_needed(user.name, reference, episodes=[user_item], notify=False)
        self.notify_new_episode(self.fetch_item(item_id))

    def change_default_tracks_if_needed(self, username: str, episode: Episode, episodes: List[Episode] = None,
                                        notify: bool = True):
        track_changes = TrackChanges(username, episode)
        logger.debug(f"[Language Update] "
                     f"Checking language update for show {episode.show()} and user '{username}' based on episode {episode}")
        if episodes is None:
            # Get episodes to update
            episodes = track_changes.get_episodes_to_update(
                self.config.get("update_level"), self.config.get("update_strategy"))

        # Get changes to perform
        track_changes.compute(episodes)
        if not track_changes.has_changes:
            logger.debug(f"[Language Update] No changes to perform for show {episode.show()} and user '{username}'")
            return False

        # Perform changes
        track_changes.apply()

        # Notify changes
        if notify:
            self.notify_changes(track_changes)
        return True

    def notify_changes(self, track_changes: TrackChanges):
        logger.info(f"Language update: {track_changes.inline_description}")
        if self.notifier is None:
            return
        title = f"PlexAutoLanguages - {track_changes.reference_name}"
        self.notifier.notify_user(title, track_changes.description, track_changes.username)

    def notify_new_episode(self, episode: Episode):
        title = "PlexAutoLanguages - New episode"
        message = (
            f"Episode: {self.get_episode_short_name(episode)}\n"
            f"Updated language for all users"
        )
        inline_message = message.replace("\n", " | ")
        logger.info(f"Language update for new episode: {inline_message}")
        if self.notifier is None:
            return
        self.notifier.notify(title, message)

    def start_deep_analysis(self):
        min_date = datetime.now() - timedelta(days=1)
        history = self._plex.history(mindate=min_date)
        for episode in [media for media in history if isinstance(media, Episode)]:
            user = self.get_user_by_id(episode.accountID)
            if user is None:
                continue
            episode.reload()
            self.change_default_tracks_if_needed(user.name, episode)
