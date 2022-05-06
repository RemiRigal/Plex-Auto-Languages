from __future__ import annotations
from typing import TYPE_CHECKING

from plex_auto_languages.alerts.base import PlexAlert
from plex_auto_languages.utils.logger import get_logger
from plex_auto_languages.constants import EventType

if TYPE_CHECKING:
    from plex_auto_languages.plex_server import PlexServer


logger = get_logger()


class PlexStatus(PlexAlert):

    TYPE = "status"

    @property
    def title(self):
        return self._message.get("title", None)

    def process(self, plex: PlexServer):
        if self.title != "Library scan complete":
            return
        logger.info("[Status] The Plex server scanned the library")

        if plex.config.get("refresh_library_on_scan"):
            added, updated = plex.cache.refresh_library_cache()
        else:
            added = plex.get_recently_added_episodes(minutes=5)
            updated = []

        # Process recently added episodes
        if len(added) > 0:
            logger.debug(f"[Status] Found {len(added)} newly added episode(s)")
            for item in added:
                # Check if the item has already been processed
                if not plex.cache.should_process_recently_added(item.key, item.addedAt):
                    continue

                # Change tracks for all users
                logger.info(f"[Status] Processing newly added episode {plex.get_episode_short_name(item)}")
                plex.process_new_or_updated_episode(item.key, EventType.NEW_EPISODE)

        # Process updated episodes
        if len(updated) > 0:
            logger.debug(f"[Status] Found {len(updated)} updated episode(s)")
            for item in updated:
                # Check if the item has already been processed
                if not plex.cache.should_process_recently_updated(item.key):
                    continue

                # Change tracks for all users
                logger.info(f"[Status] Processing updated episode {plex.get_episode_short_name(item)}")
                plex.process_new_or_updated_episode(item.key, EventType.UPDATED_EPISODE)
