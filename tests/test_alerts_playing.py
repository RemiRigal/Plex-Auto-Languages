import copy
from unittest.mock import patch

from plex_auto_languages.constants import EventType
from plex_auto_languages.plex_server import PlexServer
from plex_auto_languages.alerts import PlexPlaying


def test_playing(plex, episode):
    playing_message = {
        "clientIdentifier": "some_identifier",
        "key": episode.key,
        "sessionKey": "1",
        "state": "playing"
    }
    playing = PlexPlaying(copy.deepcopy(playing_message))
    assert playing.client_identifier == "some_identifier"
    assert playing.item_key == episode.key
    assert playing.session_key == "1"
    assert playing.session_state == "playing"

    with patch.object(PlexServer, "get_user_from_client_identifier", return_value=(None, None)) as mocked_get_user:
        playing.process(plex)
        mocked_get_user.assert_called_once_with("some_identifier")

    plex.cache.user_clients["some_identifier"] = (plex.user_id, plex.username)

    with patch.object(PlexServer, "change_tracks") as mocked_change_tracks:
        # Not called because the show is ignored
        mocked_change_tracks.reset_mock()
        plex.config._config["ignore_labels"] = ["PAL_IGNORE"]
        episode.show().addLabel("PAL_IGNORE")
        playing.process(plex)
        mocked_change_tracks.assert_not_called()
        episode.show().removeLabel("PAL_IGNORE")

        # Default behavior
        mocked_change_tracks.reset_mock()
        playing.process(plex)
        mocked_change_tracks.assert_called_once_with(plex.username, episode, EventType.PLAY_OR_ACTIVITY)
        plex.cache.default_streams.clear()

        # Not called because the state hasn't changed
        mocked_change_tracks.reset_mock()
        playing.process(plex)
        mocked_change_tracks.assert_not_called()
        plex.cache.default_streams.clear()

        # Called because the state has changed
        mocked_change_tracks.reset_mock()
        playing._message["state"] = "paused"
        assert playing.session_state == "paused"
        playing.process(plex)
        mocked_change_tracks.assert_called_once_with(plex.username, episode, EventType.PLAY_OR_ACTIVITY)

        # Not called because the selected streams are unchanged
        mocked_change_tracks.reset_mock()
        plex.cache.session_states.clear()
        playing.process(plex)
        mocked_change_tracks.assert_not_called()
        playing._message = copy.deepcopy(playing_message)
        plex.cache.default_streams.clear()

        # Not called because the user is invalid
        mocked_change_tracks.reset_mock()
        plex.cache.user_clients["some_identifier"] = ("invalid_user_id", plex.username)
        playing.process(plex)
        mocked_change_tracks.assert_not_called()
        plex.cache.user_clients["some_identifier"] = (plex.user_id, plex.username)

        # Not called because the item key is invalid
        mocked_change_tracks.reset_mock()
        playing._message["key"] = "/metadata/library/invalid_key"
        assert playing.item_key == "/metadata/library/invalid_key"
        playing.process(plex)
        mocked_change_tracks.assert_not_called()
        playing._message = copy.deepcopy(playing_message)

        # Called because the state has changed
        mocked_change_tracks.reset_mock()
        playing._message["state"] = "stopped"
        assert playing.session_state == "stopped"
        assert "some_identifier" in plex.cache.user_clients
        playing.process(plex)
        assert "some_identifier" not in plex.cache.user_clients
        mocked_change_tracks.assert_called_once_with(plex.username, episode, EventType.PLAY_OR_ACTIVITY)
        playing._message = copy.deepcopy(playing_message)
        plex.cache.default_streams.clear()
