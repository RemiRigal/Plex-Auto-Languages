from unittest.mock import patch

from plex_auto_languages.constants import EventType
from plex_auto_languages.track_changes import TrackChanges, NewOrUpdatedTrackChanges


class SubtitleStream():

    def __init__(self, languageCode, codec, title, forced):
        self.languageCode = languageCode
        self.codec = codec
        self.title = title
        self.forced = forced


class AudioStream():

    def __init__(self, languageCode, codec, title, audioChannelLayout, channels):
        self.languageCode = languageCode
        self.codec = codec
        self.title = title
        self.audioChannelLayout = audioChannelLayout
        self.channels = channels


def test_match_audio_stream(plex, episode):
    changes = TrackChanges(plex.username, episode, EventType.NEW_EPISODE)
    audio_streams = [
        AudioStream("eng", "ac3", "English", "5.1", 6),
        AudioStream("eng", "ac3", "English", "7.1", 8),
        AudioStream("eng", "ac3", "English with another title", "5.1", 6),
        AudioStream("eng", "truehd", "English", "5.1", 6),
        AudioStream("fre", "truehd", "French TrueHD", "7.1", 8),
        AudioStream("fre", "truehd", "", "7.1", 8),
        AudioStream("fre", "truehd", "", "5.1", 6)
    ]

    changes._audio_stream = AudioStream("eng", "ac3", "English", "5.1", 6)
    assert changes._match_audio_stream(audio_streams) == audio_streams[0]

    changes._audio_stream = AudioStream("eng", "truehd", "English", "7.1", 8)
    assert changes._match_audio_stream(audio_streams) == audio_streams[3]

    changes._audio_stream = AudioStream("fre", "truehd", "French", "7.1", 8)
    assert changes._match_audio_stream(audio_streams) == audio_streams[4]


def test_match_subtitle_stream(plex, episode):
    changes = TrackChanges(plex.username, episode, EventType.NEW_EPISODE)
    subtitle_streams = [
        SubtitleStream("eng", "srt", "English", False),
        SubtitleStream("eng", "srt", "English (Forced)", True),
        SubtitleStream("spa", "srt", "Spanish", False),
        SubtitleStream("spa", "srt", "Spanish (Forced)", True),
        SubtitleStream("fra", "srt", "French", False)
    ]

    changes._audio_stream = AudioStream("eng", "ac3", "English", "5.1", 6)
    changes._subtitle_stream = SubtitleStream("fra", "srt", "", False)
    assert changes._match_subtitle_stream(subtitle_streams) == subtitle_streams[4]

    changes._subtitle_stream = SubtitleStream("spa", "srt", "", True)
    assert changes._match_subtitle_stream(subtitle_streams) == subtitle_streams[3]

    changes._subtitle_stream = None
    assert changes._match_subtitle_stream(subtitle_streams) == subtitle_streams[1]

    changes._audio_stream = AudioStream("fra", "ac3", "French", "5.1", 6)
    changes._subtitle_stream = None
    assert changes._match_subtitle_stream(subtitle_streams) is None


def test_track_changes(plex, show):
    season_one_episodes = [e for e in show.episodes() if e.seasonNumber == 1]
    episode = season_one_episodes[-2]
    next_episode = season_one_episodes[-1]

    episode.reload()
    part = episode.media[0].parts[0]
    french_audio = [audio for audio in part.audioStreams() if audio.languageCode == "fra"][0]
    part.setDefaultAudioStream(french_audio)
    french_sub = [sub for sub in part.subtitleStreams() if sub.languageCode == "fra"][0]
    part.setDefaultSubtitleStream(french_sub)

    next_episode.reload()
    part = next_episode.media[0].parts[0]
    english_audio = [audio for audio in part.audioStreams() if audio.languageCode == "eng"][0]
    part.setDefaultAudioStream(english_audio)
    english_sub = [sub for sub in part.subtitleStreams() if sub.languageCode == "eng"][0]
    part.setDefaultSubtitleStream(english_sub)

    episode.reload()
    changes = TrackChanges(plex.username, episode, EventType.NEW_EPISODE)
    assert changes.username == plex.username
    assert changes.event_type == EventType.NEW_EPISODE
    assert changes.description == ""
    assert changes.title == ""
    assert changes.inline_description == ""
    assert changes.reference_name != ""

    assert changes.computed is False
    assert changes.has_changes is False
    assert changes.change_count == 0

    episodes = changes.get_episodes_to_update("season", "next")
    assert len(episodes) == 1
    assert episodes[0].key == next_episode.key

    changes.compute(episodes)

    assert changes.description != ""
    assert changes.title != ""
    assert changes.inline_description != ""

    assert changes.computed is True
    assert changes.has_changes is True
    assert changes.change_count == 2


def test_new_or_updated_track_changes(plex, show):
    changes = NewOrUpdatedTrackChanges(EventType.NEW_EPISODE, True)
    assert changes.episode_name == ""
    assert changes.event_type == EventType.NEW_EPISODE
    assert changes.description == ""
    assert changes.title == ""
    assert changes.inline_description == ""

    changes._update_description()
    assert changes.description == ""
    assert changes.title == ""
    assert changes.inline_description == ""

    assert changes.has_changes is False

    season_one_episodes = [e for e in show.episodes() if e.seasonNumber == 1]
    reference = season_one_episodes[-2]
    new_episode = season_one_episodes[-1]

    with patch.object(TrackChanges, "apply") as mocked_apply:
        changes.change_track_for_user(plex.username, reference, new_episode)
        mocked_apply.assert_called_once()

    assert changes.episode_name != ""
    assert changes.description != ""
    assert changes.title != ""
    assert changes.inline_description != ""


def test_get_episodes_to_update(plex, show):
    season_one_episodes = [e for e in show.episodes() if e.seasonNumber == 1]
    keys_before = {e.key for e in season_one_episodes[:3]}
    episode = season_one_episodes[2]
    changes = TrackChanges(plex.username, episode, EventType.NEW_EPISODE)

    assert changes._is_episode_after(season_one_episodes[0]) is False
    assert changes._is_episode_after(episode) is False
    assert changes._is_episode_after(season_one_episodes[3]) is True

    episodes = changes.get_episodes_to_update("show", "all")
    assert {e.key for e in episodes} == {e.key for e in show.episodes()}

    episodes = changes.get_episodes_to_update("show", "next")
    assert {e.key for e in episodes} == {e.key for e in show.episodes()} - keys_before

    episodes = changes.get_episodes_to_update("season", "all")
    assert {e.key for e in episodes} == {e.key for e in season_one_episodes}

    episodes = changes.get_episodes_to_update("season", "next")
    assert {e.key for e in episodes} == {e.key for e in season_one_episodes} - keys_before
