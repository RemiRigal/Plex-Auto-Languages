from __future__ import annotations
from typing import TYPE_CHECKING

from plex_auto_languages.utils.logger import get_logger

if TYPE_CHECKING:
    from plex_auto_languages.plex_server import PlexServer


logger = get_logger()


class PlexServerCache():

    def __init__(self, plex: PlexServer):
        self._plex = plex
        # Alerts cache
        self.session_states = {}     # session_key: session_state
        self.default_streams = {}    # item_key: (audio_stream_id, substitle_stream_id)
        self.user_clients = {}       # client_identifier: user_id
        self.newly_added = {}        # episode_id: added_at
        self.recent_activities = {}  # (user_id, item_id): timestamp
        # Library cache
        self.episode_parts = {}
        # Initialization
        logger.info("Scanning all episodes from the library, this action can take a few seconds")
        self.refresh_library_cache()
        logger.info(f"Scanned {len(self.episode_parts)} episodes from the library")

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
        return added, updated
