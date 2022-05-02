from __future__ import annotations
from typing import TYPE_CHECKING

from plex_auto_languages.alerts.base import PlexAlert
from plex_auto_languages.utils.logger import get_logger

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
        logger.info("[Status] Library scan complete")

        added, updated = plex.cache.refresh_library_cache()

        # Process recently added episodes
        if len(added) > 0:
            logger.debug(f"[Status] Found {len(added)} newly added episode(s)")
            for item in added:
                # Check if the item has already been processed
                if item.key in plex.cache.newly_added and plex.cache.newly_added[item.key] == item.addedAt:
                    continue
                plex.cache.newly_added[item.key] = item.addedAt

                # Change tracks for all users
                logger.info(f"[Status] Processing newly added episode {plex.get_episode_short_name(item)}")
                plex.process_new_or_updated_episode(item.key)

        # Process updated episodes
        if len(updated) > 0:
            logger.debug(f"[Status] Found {len(updated)} updated episode(s)")
            for item in updated:
                # Change tracks for all users
                logger.info(f"[Status] Processing updated episode {plex.get_episode_short_name(item)}")
                plex.process_new_or_updated_episode(item.key)
