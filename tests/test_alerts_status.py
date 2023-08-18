import copy
from unittest.mock import patch

from plex_auto_languages.constants import EventType
from plex_auto_languages.plex_server import PlexServer
from plex_auto_languages.plex_server_cache import PlexServerCache
from plex_auto_languages.alerts import PlexStatus


def test_status(plex, episode):
    status_message = {
        "title": "Library scan complete"
    }
    status = PlexStatus(copy.deepcopy(status_message))
    assert status.title == "Library scan complete"

    plex.config._config["ignore_labels"] = ["PAL_IGNORE"]

    with patch.object(PlexServer, "process_new_or_updated_episode") as mocked_process:

        plex.config._config["refresh_library_on_scan"] = True

        with patch.object(PlexServerCache, "refresh_library_cache", return_value=([episode], [])):
            # Not called because the show should be ignored
            mocked_process.reset_mock()
            episode.show().addLabel("PAL_IGNORE")
            status.process(plex)
            mocked_process.assert_not_called()
            episode.show().removeLabel("PAL_IGNORE")

            # Default behavior for new episode
            mocked_process.reset_mock()
            status.process(plex)
            mocked_process.assert_called_once_with(episode.key, EventType.NEW_EPISODE, True)

            # Not called because the episode has been processed recently
            mocked_process.reset_mock()
            status.process(plex)
            mocked_process.assert_not_called()
            plex.cache.newly_added.clear()

        with patch.object(PlexServerCache, "refresh_library_cache", return_value=([], [episode])):
            # Not called because the show should be ignored
            mocked_process.reset_mock()
            episode.show().addLabel("PAL_IGNORE")
            status.process(plex)
            mocked_process.assert_not_called()
            episode.show().removeLabel("PAL_IGNORE")

            # Default behavior for updated episode
            mocked_process.reset_mock()
            status.process(plex)
            mocked_process.assert_called_once_with(episode.key, EventType.UPDATED_EPISODE, False)

            # Not called because the episode has been processed recently
            mocked_process.reset_mock()
            status.process(plex)
            mocked_process.assert_not_called()
            plex.cache.newly_updated.clear()

        plex.config._config["refresh_library_on_scan"] = False

        with patch.object(PlexServer, "get_recently_added_episodes", return_value=[episode]):
            # Default behavior for new episode
            mocked_process.reset_mock()
            status.process(plex)
            mocked_process.assert_called_once_with(episode.key, EventType.NEW_EPISODE, True)
            plex.cache.newly_added.clear()

        # Not called because the title is invalid
        mocked_process.reset_mock()
        status._message["title"] = "invalid_title"
        status.process(plex)
        mocked_process.assert_not_called()
        status._message = copy.deepcopy(status_message)
