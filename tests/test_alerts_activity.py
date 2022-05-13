import copy
from unittest.mock import patch

from plex_auto_languages.constants import EventType
from plex_auto_languages.plex_server import PlexServer
from plex_auto_languages.alerts import PlexActivity


def test_activity(plex, episode):
    activity_message = {
        "event": "ended",
        "Activity": {
            "type": "library.refresh.items",
            "userID": plex.user_id,
            "Context": {
                "key": episode.key
            }
        }
    }
    activity = PlexActivity(copy.deepcopy(activity_message))
    assert activity.event == "ended"
    assert activity.type == "library.refresh.items"
    assert activity.is_type(PlexActivity.TYPE_LIBRARY_REFRESH_ITEM) is True
    assert activity.is_type(PlexActivity.TYPE_LIBRARY_UPDATE_SECTION) is False
    assert activity.item_key == episode.key
    assert activity.user_id == plex.user_id

    with patch.object(PlexServer, "change_tracks") as mocked_change_tracks:
        # Default behavior
        activity.process(plex)
        mocked_change_tracks.assert_called_once_with(plex.username, episode, EventType.PLAY_OR_ACTIVITY)
        assert (plex.user_id, episode.key) in plex.cache.recent_activities

        # Not called because the previous call is too recent
        mocked_change_tracks.reset_mock()
        activity.process(plex)
        mocked_change_tracks.assert_not_called()

        # Called because the cache for recent activities has been cleared
        mocked_change_tracks.reset_mock()
        plex.cache.recent_activities.clear()
        activity.process(plex)
        mocked_change_tracks.assert_called_once_with(plex.username, episode, EventType.PLAY_OR_ACTIVITY)
        plex.cache.recent_activities.clear()

        # Not called because the event is 'started'
        mocked_change_tracks.reset_mock()
        activity._message["event"] = "started"
        activity.process(plex)
        mocked_change_tracks.assert_not_called()
        activity._message = copy.deepcopy(activity_message)

        # Not called because the type is 'provider.subscriptions.process'
        mocked_change_tracks.reset_mock()
        activity._message["Activity"]["type"] = PlexActivity.TYPE_MEDIA_GENERATE_BIF
        assert activity.type == PlexActivity.TYPE_MEDIA_GENERATE_BIF
        activity.process(plex)
        mocked_change_tracks.assert_not_called()
        activity._message = copy.deepcopy(activity_message)

        # Not called because the item key is invalid
        mocked_change_tracks.reset_mock()
        activity._message["Activity"]["Context"]["key"] = "/metadata/library/invalid_key"
        assert activity.item_key == "/metadata/library/invalid_key"
        activity.process(plex)
        mocked_change_tracks.assert_not_called()
        activity._message = copy.deepcopy(activity_message)

        # Not called because the user id is invalid
        mocked_change_tracks.reset_mock()
        activity._message["Activity"]["userID"] = "invalid_user_id"
        assert activity.user_id == "invalid_user_id"
        activity.process(plex)
        mocked_change_tracks.assert_not_called()
        activity._message = copy.deepcopy(activity_message)

        with patch.object(PlexServer, "get_user_by_id", return_value=None):
            # Not called because the user can't be found
            mocked_change_tracks.reset_mock()
            activity.process(plex)
            mocked_change_tracks.assert_not_called()
