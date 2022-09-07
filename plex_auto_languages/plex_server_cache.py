from __future__ import annotations
import os
import json
import copy
from typing import TYPE_CHECKING
from datetime import datetime, timedelta
from dateutil.parser import isoparse

from plex_auto_languages.utils.logger import get_logger
from plex_auto_languages.utils.json_encoders import DateTimeEncoder

if TYPE_CHECKING:
    from plex_auto_languages.plex_server import PlexServer


logger = get_logger()


class PlexServerCache():

    def __init__(self, plex: PlexServer):
        self._is_refreshing = False
        self._encoder = DateTimeEncoder()
        self._plex = plex
        self._cache_file_path = self._get_cache_file_path()
        self._last_refresh = datetime.fromtimestamp(0)
        # Alerts cache
        self.session_states = {}     # session_key: session_state
        self.default_streams = {}    # item_key: (audio_stream_id, substitle_stream_id)
        self.user_clients = {}       # client_identifier: user_id
        self.newly_added = {}        # episode_id: added_at
        self.newly_updated = {}      # episode_id: updated_at
        self.recent_activities = {}  # (user_id, item_id): timestamp
        # Users cache
        self._instance_users = []
        self._instance_user_tokens = {}
        self._instance_users_valid_until = datetime.fromtimestamp(0)
        # Library cache
        self.episode_parts = {}
        # Initialization
        if not self._load():
            logger.info("Scanning all episodes from the Plex library, this action should only take a few seconds "
                        "but can take several minutes for larger libraries")
            self.refresh_library_cache()
            logger.info(f"Scanned {len(self.episode_parts)} episodes from the library")

    def should_process_recently_added(self, episode_id: str, added_at: datetime):
        if episode_id in self.newly_added and self.newly_added[episode_id] == added_at:
            return False
        self.newly_added[episode_id] = added_at
        return True

    def should_process_recently_updated(self, episode_id: str):
        if episode_id in self.newly_updated and self.newly_updated[episode_id] >= self._last_refresh:
            return False
        self.newly_updated[episode_id] = datetime.now()
        return True

    def refresh_library_cache(self):
        if self._is_refreshing:
            logger.debug("[Cache] The library cache is already being refreshed")
            return [], []
        self._is_refreshing = True
        logger.debug("[Cache] Refreshing library cache")
        added = []
        updated = []
        new_episode_parts = {}
        for episode in self._plex.episodes():
            part_list = new_episode_parts.setdefault(episode.key, [])
            for part in episode.iterParts():
                part_list.append(part.key)
            if episode.key in self.episode_parts and set(self.episode_parts[episode.key]) != set(part_list):
                updated.append(episode)
            elif episode.key not in self.episode_parts:
                added.append(episode)
        self.episode_parts = new_episode_parts
        logger.debug("[Cache] Done refreshing library cache")
        self._last_refresh = datetime.now()
        self.save()
        self._is_refreshing = False
        return added, updated

    def get_instance_users(self, check_validity=True):
        if check_validity and datetime.now() > self._instance_users_valid_until:
            return None
        return copy.deepcopy(self._instance_users)

    def set_instance_users(self, instance_users):
        self._instance_users = copy.deepcopy(instance_users)
        self._instance_users_valid_until = datetime.now() + timedelta(hours=12)
        for user in self._instance_users:
            if str(user.id) in self._instance_user_tokens:
                continue
            self._instance_user_tokens[str(user.id)] = user.get_token(self._plex.unique_id)

    def get_instance_user_token(self, user_id):
        return self._instance_user_tokens.get(str(user_id), None)

    def set_instance_user_token(self, user_id, token):
        self._instance_user_tokens[str(user_id)] = token

    def _get_cache_file_path(self):
        data_dir = self._plex.config.get("data_dir")
        cache_dir = os.path.join(data_dir, "cache")
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        return os.path.join(cache_dir, self._plex.unique_id)

    def _load(self):
        if not os.path.exists(self._cache_file_path):
            return False
        logger.debug("[Cache] Loading server cache from file")
        with open(self._cache_file_path, "r", encoding="utf-8") as stream:
            cache = json.load(stream)
        self.newly_updated = cache.get("newly_updated", self.newly_updated)
        self.newly_updated = {key: isoparse(value) for key, value in self.newly_updated.items()}
        self.newly_added = cache.get("newly_added", self.newly_added)
        self.newly_added = {key: isoparse(value) for key, value in self.newly_added.items()}
        self.episode_parts = cache.get("episode_parts", )
        self._last_refresh = isoparse(cache.get("last_refresh", self._last_refresh))
        return True

    def save(self):
        logger.debug("[Cache] Saving server cache to file")
        cache = {
            "newly_updated": self.newly_updated,
            "newly_added": self.newly_added,
            "episode_parts": self.episode_parts,
            "last_refresh": self._last_refresh
        }
        with open(self._cache_file_path, "w", encoding="utf-8") as stream:
            stream.write(self._encoder.encode(cache))
