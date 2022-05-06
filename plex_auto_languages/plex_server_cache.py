from __future__ import annotations
import os
import json
from datetime import datetime
from typing import TYPE_CHECKING
from dateutil.parser import isoparse

from plex_auto_languages.utils.logger import get_logger

if TYPE_CHECKING:
    from plex_auto_languages.plex_server import PlexServer


logger = get_logger()


class PlexServerCache():

    def __init__(self, plex: PlexServer):
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
        # Library cache
        self.episode_parts = {}
        # Initialization
        if not self._load():
            logger.info("Scanning all episodes from the library, this action can take a few seconds")
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
        return added, updated

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
        self.newly_added = cache.get("newly_added", self.newly_added)
        self.episode_parts = cache.get("episode_parts", )
        self._last_refresh = isoparse(cache.get("last_refresh", self._last_refresh))
        return True

    def save(self):
        logger.debug("[Cache] Saving server cache to file")
        cache = {
            "newly_updated": self.newly_updated,
            "newly_added": self.newly_added,
            "episode_parts": self.episode_parts,
            "last_refresh": self._last_refresh.isoformat()
        }
        with open(self._cache_file_path, "w", encoding="utf-8") as stream:
            json.dump(cache, stream)
