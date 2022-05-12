import math
import pytest
from datetime import datetime
from unittest.mock import patch, call
from plexapi.video import Episode, Show
from plexapi.server import PlexServer as BasePlexServer

from plex_auto_languages.track_changes import TrackChanges, NewOrUpdatedTrackChanges
from plex_auto_languages.plex_server import PlexServer, UnprivilegedPlexServer
from plex_auto_languages.plex_server_cache import PlexServerCache
from plex_auto_languages.constants import EventType
from plex_auto_languages.exceptions import UserNotFound


def test_unique_id(plex):
    assert plex.unique_id is not None and isinstance(plex.unique_id, str) and len(plex.unique_id) == 40


def test_episodes(plex):
    episodes = plex.episodes()
    assert len(episodes) == 46


def test_fetch_item(plex, episode):
    same_episode = plex.fetch_item(episode.key)
    assert same_episode is not None and isinstance(same_episode, Episode)
    assert episode == same_episode

    invalid_episode = plex.fetch_item("/library/metadata/invalid_key")
    assert invalid_episode is None


def test_recently_added(plex, episode):
    added_at = episode.addedAt
    delta = datetime.now() - added_at
    delta_minutes = math.ceil(delta.total_seconds() / 60)
    recently_added = plex.get_recently_added_episodes(minutes=delta_minutes + 1)
    assert episode in recently_added


def test_last_watched_or_first(plex, episode):
    show = episode.show()
    show.markUnwatched()
    first_episode = show.episode(season=1, episode=1)
    last_watched_or_first = plex.get_last_watched_or_first_episode(show)
    assert first_episode == last_watched_or_first

    last_episode = show.episodes()[-1]
    last_episode.markWatched()
    last_watched_or_first = plex.get_last_watched_or_first_episode(show)
    assert last_episode == last_watched_or_first

    show.markUnwatched()
    with patch.object(Show, "episodes", return_value=[]):
        last_watched_or_first = plex.get_last_watched_or_first_episode(show)
        assert last_watched_or_first is None


def test_get_selected_streams(plex, episode):
    episode.reload()
    part = episode.media[0].parts[0]
    audio_stream = part.audioStreams()[0]
    part.setDefaultAudioStream(audio_stream)
    subtitle_stream = part.subtitleStreams()[0]
    part.setDefaultSubtitleStream(subtitle_stream)

    episode.reload()
    part = episode.media[0].parts[0]
    audio, subtitle = plex.get_selected_streams(part)
    assert audio.id == audio_stream.id
    assert subtitle.id == subtitle_stream.id

    part.resetDefaultSubtitleStream()

    episode.reload()
    part = episode.media[0].parts[0]
    audio, subtitle = plex.get_selected_streams(part)
    assert audio.id == audio_stream.id
    assert subtitle is None


def test_episode_short_name(plex, episode):
    show = episode.show()
    first_episode = show.episode(season=1, episode=1)
    assert plex.get_episode_short_name(first_episode, include_show=False) == "S01E01"
    assert plex.get_episode_short_name(first_episode, include_show=True) == f"'{show.title}' (S01E01)"


def test_sections(plex):
    sections = plex.get_show_sections()
    assert len(sections) == 1


def test_get_user_id(plex):
    with patch.object(BasePlexServer, "systemAccounts", return_value=[]):
        user_id, username = plex._get_user_id()
        assert user_id is None
        assert username is None


def test_get_user_by_id(plex):
    user = plex.get_user_by_id(plex.user_id)
    assert user.id == plex.user_id
    assert user.name == plex.username

    other_user_id = plex.get_all_user_ids()[1]
    user = plex.get_user_by_id(other_user_id)
    assert user.id == other_user_id

    user = plex.get_user_by_id("invalid_user_id")
    assert user is None


def test_get_all_user_ids(plex):
    user_ids = plex._get_user_id()
    assert len(user_ids) == 2
    assert plex.user_id in user_ids


def test_get_plex_instance_of_user(plex):
    new_plex = plex.get_plex_instance_of_user(plex.user_id)
    assert plex == new_plex
    assert isinstance(new_plex, PlexServer)

    other_user_id = plex.get_all_user_ids()[1]
    new_plex = plex.get_plex_instance_of_user(other_user_id)
    assert plex != new_plex
    assert isinstance(new_plex, UnprivilegedPlexServer)

    new_plex = plex.get_plex_instance_of_user("invalid_user_id")
    assert new_plex is None


def test_get_user_from_client_identifier(plex):
    user_id, username = plex.get_user_from_client_identifier("invalid_client_identifier")
    assert user_id is None and username is None


def test_is_alive(plex):
    assert plex.is_alive is False


def test_save_cache(plex):
    with patch.object(PlexServerCache, "save") as mocked_save:
        plex.save_cache()
        mocked_save.assert_called_once()


def test_init(config):
    with patch.object(PlexServer, "_get_user_id", return_value=(None, None)):
        with pytest.raises(UserNotFound):
            _ = PlexServer(config.get("plex.url"), config.get("plex.token"), None, config)


def test_process_new_or_updated_episode(plex, episode):
    show = episode.show()
    show.markUnwatched()
    first_episode = show.episodes()[0]
    first_episode.reload()
    part = first_episode.media[0].parts[0]
    french_audio = [audio for audio in part.audioStreams() if audio.languageCode == "fra"][0]
    part.setDefaultAudioStream(french_audio)
    french_sub = [sub for sub in part.subtitleStreams() if sub.languageCode == "fra"][0]
    part.setDefaultSubtitleStream(french_sub)

    last_episode = show.episodes()[-1]
    last_episode.reload()
    part = last_episode.media[0].parts[0]
    french_audio = [audio for audio in part.audioStreams() if audio.languageCode == "eng"][0]
    part.setDefaultAudioStream(french_audio)
    french_sub = [sub for sub in part.subtitleStreams() if sub.languageCode == "eng"][0]
    part.setDefaultSubtitleStream(french_sub)

    # The mocked function must be called once per user
    with patch.object(NewOrUpdatedTrackChanges, "change_track_for_user") as mocked_change_track:
        plex.process_new_or_updated_episode(last_episode.key, EventType.NEW_EPISODE, True)
        mocked_change_track.assert_called()
        assert mocked_change_track.call_count == len(plex.get_all_user_ids())

    # The function must update the language of the last episode
    plex.process_new_or_updated_episode(last_episode.key, EventType.NEW_EPISODE, True)
    last_episode.reload()
    selected_audio, selected_sub = plex.get_selected_streams(last_episode)
    assert selected_audio.languageCode == "fra"
    assert selected_sub.languageCode == "fra"


def test_change_tracks(plex, episode):
    show = episode.show()
    first_episode = show.episodes()[0]
    first_episode.reload()

    part = first_episode.media[0].parts[0]
    french_audio = [audio for audio in part.audioStreams() if audio.languageCode == "fra"][0]
    part.setDefaultAudioStream(french_audio)
    french_sub = [sub for sub in part.subtitleStreams() if sub.languageCode == "fra"][0]
    part.setDefaultSubtitleStream(french_sub)

    second_episode = show.episodes()[1]
    second_episode.reload()

    part = second_episode.media[0].parts[0]
    french_audio = [audio for audio in part.audioStreams() if audio.languageCode == "eng"][0]
    part.setDefaultAudioStream(french_audio)
    french_sub = [sub for sub in part.subtitleStreams() if sub.languageCode == "eng"][0]
    part.setDefaultSubtitleStream(french_sub)

    # The mocked function must be called once
    with patch.object(TrackChanges, "apply") as mocked_apply:
        plex.change_tracks(plex.username, first_episode, EventType.PLAY_OR_ACTIVITY)
        mocked_apply.assert_called_once()

    # The function must update the language of the second episode
    plex.change_tracks(plex.username, first_episode, EventType.PLAY_OR_ACTIVITY)
    second_episode.reload()
    selected_audio, selected_sub = plex.get_selected_streams(second_episode)
    assert selected_audio.languageCode == "fra"
    assert selected_sub.languageCode == "fra"
