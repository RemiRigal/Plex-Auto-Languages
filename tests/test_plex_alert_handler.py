from logging import Logger
from unittest.mock import patch

from plex_auto_languages.plex_alert_handler import PlexAlertHandler
from plex_auto_languages.alerts import PlexStatus, PlexPlaying, PlexActivity, PlexTimeline


def test_plex_alert_handler():
    handler = PlexAlertHandler(None, True, True, True)

    playing_alert = {"type": PlexPlaying.TYPE, "PlaySessionStateNotification": [{}]}
    with patch.object(PlexPlaying, "process") as mocked_process:
        handler(playing_alert)
        mocked_process.assert_called_once()

        mocked_process.reset_mock()
        del playing_alert["PlaySessionStateNotification"]
        handler(playing_alert)
        mocked_process.assert_not_called()

    timeline_alert = {"type": PlexTimeline.TYPE, "TimelineEntry": [{}]}
    with patch.object(PlexTimeline, "process") as mocked_process:
        handler(timeline_alert)
        mocked_process.assert_called_once()

        mocked_process.reset_mock()
        del timeline_alert["TimelineEntry"]
        handler(timeline_alert)
        mocked_process.assert_not_called()

    status_alert = {"type": PlexStatus.TYPE, "StatusNotification": [{}]}
    with patch.object(PlexStatus, "process") as mocked_process:
        handler(status_alert)
        mocked_process.assert_called_once()

        mocked_process.reset_mock()
        del status_alert["StatusNotification"]
        handler(status_alert)
        mocked_process.assert_not_called()

    activity_alert = {"type": PlexActivity.TYPE, "ActivityNotification": [{}]}
    with patch.object(PlexActivity, "process") as mocked_process:
        handler(activity_alert)
        mocked_process.assert_called_once()

        mocked_process.reset_mock()
        del activity_alert["ActivityNotification"]
        handler(activity_alert)
        mocked_process.assert_not_called()

    with patch.object(Logger, "debug") as mocked_debug:
        status_alert = {"type": PlexStatus.TYPE, "StatusNotification": [{"title": "Library scan complete"}]}
        handler(status_alert)
        mocked_debug.assert_called_with(status_alert)
