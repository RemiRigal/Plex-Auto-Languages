import copy
from unittest.mock import patch
from datetime import datetime, timedelta

from plex_auto_languages.constants import EventType
from plex_auto_languages.plex_server import PlexServer
from plex_auto_languages.alerts import PlexTimeline


def test_timeline(plex, episode):
    item_id = int(episode.key.split("/")[-1])
    timeline_message = {
        "itemID": str(item_id),
        "identifier": "com.plexapp.plugins.library",
        "state": 5,
        "type": 0
    }
    timeline = PlexTimeline(copy.deepcopy(timeline_message))
    assert timeline.item_id == item_id
    assert timeline.identifier == "com.plexapp.plugins.library"
    assert timeline.state == 5
    assert timeline.entry_type == 0

    plex.config._config["ignore_labels"] = ["PAL_IGNORE"]

    with patch.object(PlexServer, "process_new_or_updated_episode") as mocked_process:
        fake_recent_episode = copy.deepcopy(episode)
        fake_recent_episode.addedAt = datetime.now()
        with patch.object(PlexServer, "fetch_item", return_value=fake_recent_episode):
            # Not called because the show should be ignored
            mocked_process.reset_mock()
            episode.show().addLabel("PAL_IGNORE")
            timeline.process(plex)
            mocked_process.assert_not_called()
            episode.show().removeLabel("PAL_IGNORE")

            # Default behavior
            mocked_process.reset_mock()
            timeline.process(plex)
            mocked_process.assert_called_once_with(item_id, EventType.NEW_EPISODE, True)

            # Not called because it has already been processed
            mocked_process.reset_mock()
            timeline.process(plex)
            mocked_process.assert_not_called()
            plex.cache.newly_added.clear()

            # Not called because the alert has metadata state
            mocked_process.reset_mock()
            timeline._message["metadataState"] = "state"
            timeline.process(plex)
            mocked_process.assert_not_called()
            timeline._message = copy.deepcopy(timeline_message)

            # Not called because the alert has media state
            mocked_process.reset_mock()
            timeline._message["mediaState"] = "state"
            timeline.process(plex)
            mocked_process.assert_not_called()
            timeline._message = copy.deepcopy(timeline_message)

            # Not called because the alert has an invalid identifier
            mocked_process.reset_mock()
            timeline._message["identifier"] = "invalid_identifier"
            timeline.process(plex)
            mocked_process.assert_not_called()
            timeline._message = copy.deepcopy(timeline_message)

            # Not called because the alert has an invalid state
            mocked_process.reset_mock()
            timeline._message["state"] = 2
            timeline.process(plex)
            mocked_process.assert_not_called()
            timeline._message = copy.deepcopy(timeline_message)

            # Not called because the alert has the type '-1'
            mocked_process.reset_mock()
            timeline._message["type"] = -1
            timeline.process(plex)
            mocked_process.assert_not_called()
            timeline._message = copy.deepcopy(timeline_message)

        with patch.object(PlexServer, "fetch_item", return_value=None):
            # Not called because the episode is None
            mocked_process.reset_mock()
            timeline.process(plex)
            mocked_process.assert_not_called()

        fake_old_episode = copy.deepcopy(episode)
        fake_old_episode.addedAt = datetime.now() - timedelta(minutes=10)
        with patch.object(PlexServer, "fetch_item", return_value=fake_old_episode):
            # Not called because the episode has been added more than 5 minutes ago
            mocked_process.reset_mock()
            timeline.process(plex)
            mocked_process.assert_not_called()
