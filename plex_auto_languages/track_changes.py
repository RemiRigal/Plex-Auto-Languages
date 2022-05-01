from typing import List, Union
from plexapi.video import Episode
from plexapi.media import AudioStream, SubtitleStream, MediaPart

from plex_auto_languages.utils.logger import get_logger


logger = get_logger()


class TrackChanges():

    def __init__(self, username: str, reference: Episode):
        self._reference = reference
        self._username = username
        self._audio_stream, self._subtitle_stream = self._get_selected_streams(reference)
        self._changes = []
        self._description = ""

    @property
    def description(self):
        return self._description

    @property
    def inline_description(self):
        return self._description.replace("\n", " | ")

    @property
    def reference_name(self):
        return f"'{self._reference.show().title}' (S{self._reference.seasonNumber:02}E{self._reference.episodeNumber:02})"

    @property
    def has_changes(self):
        return len(self._changes) > 0

    @property
    def username(self):
        return self._username

    @property
    def change_count(self):
        return len(self._changes)

    def get_episodes_to_update(self, update_level: str, update_strategy: str):
        show_or_season = None
        if update_level == "show":
            show_or_season = self._reference.show()
        elif update_level == "season":
            show_or_season = self._reference.season()
        episodes = show_or_season.episodes()
        if update_strategy == "next":
            episodes = [e for e in episodes if self._is_episode_after(e)]
        return episodes

    def compute(self, episodes: List[Episode]):
        self._changes = []
        for episode in episodes:
            episode.reload()
            for part in episode.iterParts():
                current_audio_stream, current_subtitle_stream = self._get_selected_streams(part)
                # Audio stream
                matching_audio_stream = self._match_audio_stream(part.audioStreams())
                if current_audio_stream is not None and matching_audio_stream is not None and \
                        matching_audio_stream.id != current_audio_stream.id:
                    self._changes.append((episode, part, AudioStream.STREAMTYPE, matching_audio_stream))
                # Subtitle stream
                matching_subtitle_stream = self._match_subtitle_stream(part.subtitleStreams())
                if current_subtitle_stream is not None and matching_subtitle_stream is None:
                    self._changes.append((episode, part, SubtitleStream.STREAMTYPE, None))
                if matching_subtitle_stream is not None and \
                        (current_subtitle_stream is None or matching_subtitle_stream.id != current_subtitle_stream.id):
                    self._changes.append((episode, part, SubtitleStream.STREAMTYPE, matching_subtitle_stream))
        self._update_description(episodes)

    def apply(self):
        logger.debug(f"[Language Update] Performing {len(self._changes)} change(s) for show {self._reference.show()}")
        for episode, part, stream_type, new_stream in self._changes:
            stream_type_name = "audio" if stream_type == AudioStream.STREAMTYPE else "subtitle"
            logger.debug(f"[Language Update] Updating {stream_type_name} stream of episode {episode} to {new_stream}")
            if stream_type == AudioStream.STREAMTYPE:
                part.setDefaultAudioStream(new_stream)
            elif stream_type == SubtitleStream.STREAMTYPE and new_stream is None:
                part.resetDefaultSubtitleStream()
            elif stream_type == SubtitleStream.STREAMTYPE:
                part.setDefaultSubtitleStream(new_stream)

    def _is_episode_after(self, episode: Episode):
        return self._reference.seasonNumber < episode.seasonNumber or \
            (self._reference.seasonNumber == episode.seasonNumber and self._reference.episodeNumber < episode.episodeNumber)

    def _update_description(self, episodes: List[Episode]):
        season_numbers = [e.seasonNumber for e in episodes]
        min_season_number, max_season_number = min(season_numbers), max(season_numbers)
        min_episode_number = min([e.episodeNumber for e in episodes if e.seasonNumber == min_season_number])
        max_episode_number = max([e.episodeNumber for e in episodes if e.seasonNumber == max_season_number])
        from_str = f"S{min_season_number:02}E{min_episode_number:02}"
        to_str = f"S{max_season_number:02}E{max_episode_number:02}"
        range_str = f"{from_str} - {to_str}" if from_str != to_str else from_str
        nb_updated = len({e.key for e, _, _, _ in self._changes})
        nb_total = len(episodes)
        self._description = (
            f"Show: {self._reference.show().title}\n"
            f"User: {self._username}\n"
            f"Audio: {self._audio_stream.displayTitle if self._audio_stream is not None else 'None'}\n"
            f"Subtitles: {self._subtitle_stream.displayTitle if self._subtitle_stream is not None else 'None'}\n"
            f"Updated episodes: {nb_updated}/{nb_total} ({range_str})"
        )

    def _match_audio_stream(self, audio_streams: List[AudioStream]):
        # The reference stream can be 'None'
        if self._audio_stream is None:
            return None
        # We only want stream with the same language code
        streams = [s for s in audio_streams if s.languageCode == self._audio_stream.languageCode]
        if len(streams) == 0:
            return None
        if len(streams) == 1:
            return streams[0]
        # If multiple streams match, order them based on a score
        scores = [0] * len(streams)
        for index, stream in enumerate(streams):
            if self._audio_stream.codec == stream.codec:
                scores[index] += 3
            if self._audio_stream.audioChannelLayout == stream.audioChannelLayout:
                scores[index] += 3
            if self._audio_stream.channels <= stream.channels:
                scores[index] += 1
            if self._audio_stream.title is not None and stream.title is not None and self._audio_stream.title == stream.title:
                scores[index] += 5
        return streams[scores.index(max(scores))]

    def _match_subtitle_stream(self, subtitle_streams: List[SubtitleStream]):
        # If no subtitle is selected, the reference stream can be 'None'
        if self._subtitle_stream is None:
            return None
        # We only want stream with the same language code
        streams = [s for s in subtitle_streams if s.languageCode == self._subtitle_stream.languageCode]
        if len(streams) == 0:
            return None
        if len(streams) == 1:
            return streams[0]
        # If multiple streams match, order them based on a score
        scores = [0] * len(streams)
        for index, stream in enumerate(streams):
            if self._subtitle_stream.forced == stream.forced:
                scores[index] += 3
            if self._subtitle_stream.codec is not None and stream.codec is not None and \
                    self._subtitle_stream.codec == stream.codec:
                scores[index] += 1
            if self._subtitle_stream.title is not None and stream.title is not None and \
                    self._subtitle_stream.title == stream.title:
                scores[index] += 5
        return streams[scores.index(max(scores))]

    @staticmethod
    def _get_selected_streams(episode: Union[Episode, MediaPart]):
        audio_stream = ([a for a in episode.audioStreams() if a.selected] + [None])[0]
        subtitle_stream = ([s for s in episode.subtitleStreams() if s.selected] + [None])[0]
        return audio_stream, subtitle_stream
