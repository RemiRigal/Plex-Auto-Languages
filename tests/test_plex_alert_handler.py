import time
from queue import Queue
from logging import Logger
from unittest.mock import patch

from plex_auto_languages.plex_alert_handler import PlexAlertHandler
from plex_auto_languages.alerts import PlexStatus, PlexPlaying, PlexActivity, PlexTimeline


def test_plex_alert_handler():
    handler = PlexAlertHandler(None, True, True, True)

    playing_alert = {"type": PlexPlaying.TYPE, "PlaySessionStateNotification": [{}]}
    with patch.object(Queue, "put") as mocked_put:
        handler(playing_alert)
        mocked_put.assert_called_once()

        mocked_put.reset_mock()
        del playing_alert["PlaySessionStateNotification"]
        handler(playing_alert)
        mocked_put.assert_not_called()

    timeline_alert = {"type": PlexTimeline.TYPE, "TimelineEntry": [{}]}
    with patch.object(Queue, "put") as mocked_put:
        handler(timeline_alert)
        mocked_put.assert_called_once()

        mocked_put.reset_mock()
        del timeline_alert["TimelineEntry"]
        handler(timeline_alert)
        mocked_put.assert_not_called()

    status_alert = {"type": PlexStatus.TYPE, "StatusNotification": [{}]}
    with patch.object(Queue, "put") as mocked_put:
        handler(status_alert)
        mocked_put.assert_called_once()

        mocked_put.reset_mock()
        del status_alert["StatusNotification"]
        handler(status_alert)
        mocked_put.assert_not_called()

    activity_alert = {"type": PlexActivity.TYPE, "ActivityNotification": [{}]}
    with patch.object(Queue, "put") as mocked_put:
        handler(activity_alert)
        mocked_put.assert_called_once()

        mocked_put.reset_mock()
        del activity_alert["ActivityNotification"]
        handler(activity_alert)
        mocked_put.assert_not_called()

    handler.stop()


def test_alert_processing():
    handler = PlexAlertHandler(None, True, True, True)

    status_alert = PlexStatus({"type": PlexStatus.TYPE, "StatusNotification": [{}]})
    with patch.object(PlexStatus, "process") as mocked_process:
        handler._alerts_queue.put(status_alert)
        time.sleep(1)
        mocked_process.assert_called_once()

    status_alert = PlexStatus({"type": PlexStatus.TYPE, "StatusNotification": [{"title": "Library scan complete"}]})
    with patch.object(PlexStatus, "process", side_effect=Exception()) as mocked_process:
        with patch.object(Logger, "debug") as mocked_debug:
            handler._alerts_queue.put(status_alert)
            time.sleep(1)
            mocked_debug.assert_called_with(status_alert.message)

    handler.stop()


def test_processor_thread():
    handler = PlexAlertHandler(None, True, True, True)
    assert handler._processor_thread.is_alive() is True

    handler.stop()
    assert handler._processor_thread.is_alive() is False
