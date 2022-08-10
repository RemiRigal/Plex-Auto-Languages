import time
import requests
import itertools
from typing import Union, Callable
from datetime import datetime, timedelta
from requests import ConnectionError as RequestsConnectionError
from plexapi.media import MediaPart
from plexapi.library import ShowSection
from plexapi.video import Episode, Show
from plexapi.exceptions import NotFound, Unauthorized, BadRequest
from plexapi.server import PlexServer as BasePlexServer

from plex_auto_languages.utils.logger import get_logger
from plex_auto_languages.utils.configuration import Configuration
from plex_auto_languages.plex_alert_handler import PlexAlertHandler
from plex_auto_languages.plex_alert_listener import PlexAlertListener
from plex_auto_languages.track_changes import TrackChanges, NewOrUpdatedTrackChanges
from plex_auto_languages.utils.notifier import Notifier
from plex_auto_languages.plex_server_cache import PlexServerCache
from plex_auto_languages.constants import EventType
from plex_auto_languages.exceptions import UserNotFound


logger = get_logger()


class UnprivilegedPlexServer():

    def __init__(self, url: str, token: str, session: requests.Session = requests.Session()):
        self._session = session
        self._plex_url = url
        self._plex = self._get_server(url, token, self._session)

    @property
    def connected(self):
        if self._plex is None:
            return False
        try:
            _ = self._plex.library.sections()
            return True
        except (BadRequest, RequestsConnectionError):
            return False

    @property
    def unique_id(self):
        return self._plex.machineIdentifier

    @staticmethod
    def _get_server(url: str, token: str, session: requests.Session):
        try:
            return BasePlexServer(url, token, session=session)
        except (RequestsConnectionError, Unauthorized):
            return None

    def fetch_item(self, item_id: Union[str, int]):
        try:
            return self._plex.fetchItem(item_id)
        except NotFound:
            return None

    def episodes(self):
        return self._plex.library.all(libtype="episode", container_size=1024)

    def get_recently_added_episodes(self, minutes: int):
        episodes = []
        for section in self.get_show_sections():
            recent = section.searchEpisodes(sort="addedAt:desc", filters={"addedAt>>": f"{minutes}m"})
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
        self._user = self._get_logged_user()
        if self._user is None:
            logger.error("Unable to find the user associated with the provided Plex Token")
            raise UserNotFound
        logger.info(f"Successfully connected as user '{self.username}' (id: {self.user_id})")
        self._alert_handler = None
        self._alert_listener = None
        self.cache = PlexServerCache(self)

    @property
    def user_id(self):
        return self._user.id if self._user is not None else None

    @property
    def username(self):
        return self._user.name if self._user is not None else None

    @property
    def is_alive(self):
        return self.connected and self._alert_listener is not None and self._alert_listener.is_alive()

    @staticmethod
    def _get_server(url: str, token: str, session: requests.Session, max_tries: int = 5000):
        for _ in range(max_tries):
            try:
                return BasePlexServer(url, token, session=session)
            except RequestsConnectionError:
                logger.warning("ConnectionError: Unable to connect to Plex server, retrying...")
            except Unauthorized:
                logger.warning("Unauthorized: make sure your credentials are correct. Retrying to connect to Plex server...")
            time.sleep(5)
        return None

    def _get_logged_user(self):
        plex_username = self._plex.myPlexAccount().username
        for account in self._plex.systemAccounts():
            if account.name == plex_username:
                return account
        return None

    def save_cache(self):
        self.cache.save()

    def start_alert_listener(self, error_callback: Callable):
        trigger_on_play = self.config.get("trigger_on_play")
        trigger_on_scan = self.config.get("trigger_on_scan")
        trigger_on_activity = self.config.get("trigger_on_activity")
        self._alert_handler = PlexAlertHandler(self, trigger_on_play, trigger_on_scan, trigger_on_activity)
        self._alert_listener = PlexAlertListener(self._plex, self._alert_handler, error_callback)
        logger.info("Starting alert listener")
        self._alert_listener.start()

    def get_instance_users(self):
        users = self.cache.get_instance_users()
        if users is not None:
            return users
        users = []
        try:
            for user in self._plex.myPlexAccount().users():
                server_identifiers = [share.machineIdentifier for share in user.servers]
                if self.unique_id in server_identifiers:
                    user.name = user.title
                    users.append(user)
            self.cache.set_instance_users(users)
            return users
        except BadRequest:
            logger.warning("Unable to retrieve the users of the account, falling back to cache")
            return self.cache.get_instance_users(check_validity=False)

    def get_all_user_ids(self):
        return [self.user_id] + [user.id for user in self.get_instance_users()]

    def get_plex_instance_of_user(self, user_id: Union[int, str]):
        if str(self.user_id) == str(user_id):
            return self
        matching_users = [u for u in self.get_instance_users() if str(u.id) == str(user_id)]
        if len(matching_users) == 0:
            logger.error(f"Unable to find user with id '{user_id}'")
            return None
        user = matching_users[0]
        user_token = self.cache.get_instance_user_token(user.id)
        if user_token is None:
            user_token = user.get_token(self.unique_id)
            self.cache.set_instance_user_token(user.id, user_token)
        user_plex = UnprivilegedPlexServer(self._plex_url, user_token, session=self._session)
        if not user_plex.connected:
            logger.error(f"Connection to the Plex server failed for user '{matching_users[0].name}'")
            return None
        return user_plex

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
        matching_users = [u for u in [self._user] + self.get_instance_users() if str(u.id) == str(user_id)]
        if len(matching_users) == 0:
            return None
        return matching_users[0]

    def process_new_or_updated_episode(self, item_id: Union[int, str], event_type: EventType, new: bool):
        track_changes = NewOrUpdatedTrackChanges(event_type, new)
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
            track_changes.change_track_for_user(user.name, reference, user_item)

        # Notify changes
        if track_changes.has_changes:
            self.notify_changes(track_changes)

    def change_tracks(self, username: str, episode: Episode, event_type: EventType):
        track_changes = TrackChanges(username, episode, event_type)
        # Get episodes to update
        episodes = track_changes.get_episodes_to_update(self.config.get("update_level"), self.config.get("update_strategy"))

        # Get changes to perform
        track_changes.compute(episodes)

        # Perform changes
        track_changes.apply()

        # Notify changes
        if track_changes.has_changes:
            self.notify_changes(track_changes)

    def notify_changes(self, track_changes: Union[TrackChanges, NewOrUpdatedTrackChanges]):
        logger.info(f"Language update: {track_changes.inline_description}")
        if self.notifier is None:
            return
        title = f"PlexAutoLanguages - {track_changes.title}"
        if isinstance(track_changes, TrackChanges):
            self.notifier.notify_user(title, track_changes.description, track_changes.username, track_changes.event_type)
        else:
            self.notifier.notify(title, track_changes.description, track_changes.event_type)

    def start_deep_analysis(self):
        # History
        min_date = datetime.now() - timedelta(days=1)
        history = self._plex.history(mindate=min_date)
        for episode in [media for media in history if isinstance(media, Episode)]:
            user = self.get_user_by_id(episode.accountID)
            if user is None:
                continue
            episode.reload()
            self.change_tracks(user.name, episode, EventType.SCHEDULER)

        # Scan library
        added, updated = self.cache.refresh_library_cache()
        for item in added:
            if not self.cache.should_process_recently_added(item.key, item.addedAt):
                continue
            logger.info(f"[Scheduler] Processing newly added episode {self.get_episode_short_name(item)}")
            self.process_new_or_updated_episode(item.key, EventType.SCHEDULER, True)
        for item in updated:
            if not self.cache.should_process_recently_updated(item.key):
                continue
            logger.info(f"[Scheduler] Processing updated episode {self.get_episode_short_name(item)}")
            self.process_new_or_updated_episode(item.key, EventType.SCHEDULER, False)

    def stop(self):
        if self._alert_handler:
            self._alert_handler.stop()
