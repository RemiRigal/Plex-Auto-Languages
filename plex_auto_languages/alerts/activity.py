from __future__ import annotations
from typing import TYPE_CHECKING
from datetime import datetime, timedelta
from plexapi.video import Episode

from plex_auto_languages.alerts.base import PlexAlert
from plex_auto_languages.utils.logger import get_logger
from plex_auto_languages.constants import EventType

if TYPE_CHECKING:
    from plex_auto_languages.plex_server import PlexServer


logger = get_logger()


class PlexActivity(PlexAlert):

    TYPE = "activity"

    TYPE_LIBRARY_REFRESH_ITEM = "library.refresh.items"
    TYPE_LIBRARY_UPDATE_SECTION = "library.update.section"
    TYPE_PROVIDER_SUBSCRIPTIONS_PROCESS = "provider.subscriptions.process"
    TYPE_MEDIA_GENERATE_BIF = "media.generate.bif"

    def is_type(self, activity_type: str):
        return self.type == activity_type

    @property
    def event(self):
        return self._message.get("event", None)

    @property
    def type(self):
        return self._message.get("Activity", {}).get("type", None)

    @property
    def item_key(self):
        return self._message.get("Activity", {}).get("Context", {}).get("key", None)

    @property
    def user_id(self):
        return self._message.get("Activity", {}).get("userID", None)

    def process(self, plex: PlexServer):
        if self.event != "ended":
            return
        if not self.is_type(self.TYPE_LIBRARY_REFRESH_ITEM):
            return

        # Switch to the user's Plex instance
        user_plex = plex.get_plex_instance_of_user(self.user_id)
        if user_plex is None:
            return

        # Skip if not an Episode
        item = user_plex.fetch_item(self.item_key)
        if item is None or not isinstance(item, Episode):
            return

        # Skip if the show should be ignored
        if plex.should_ignore_show(item.show()):
            logger.debug(f"[Activity] Ignoring episode {item} due to Plex show tags")
            return

        # Skip if this item has already been seen in the last 3 seconds
        activity_key = (self.user_id, self.item_key)
        if activity_key in plex.cache.recent_activities and \
                plex.cache.recent_activities[activity_key] > datetime.now() - timedelta(seconds=3):
            return
        plex.cache.recent_activities[activity_key] = datetime.now()

        # Change tracks if needed
        item.reload()
        user = plex.get_user_by_id(self.user_id)
        if user is None:
            return
        logger.debug(f"[Activity] User: {user.name} | Episode: {item}")
        plex.change_tracks(user.name, item, EventType.PLAY_OR_ACTIVITY)
