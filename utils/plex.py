import itertools
from typing import List, Union
from plexapi.video import Episode
from plexapi.server import PlexServer
from plexapi.media import AudioStream, SubtitleStream

from utils.logger import get_logger


logger = get_logger()


class PlexUtils(object):

    @staticmethod
    def get_plex_instance_of_user(plex: PlexServer, plex_user_id: int, user_id: Union[int, str]):
        if plex_user_id == int(user_id):
            return plex
        matching_users = [u for u in plex.myPlexAccount().users() if u.id == int(user_id)]
        if len(matching_users) == 0:
            logger.error(f"Unable to find user with id '{user_id}'")
            return None
        user_token = matching_users[0].get_token(plex.machineIdentifier)
        return PlexServer(plex._baseurl, token=user_token)

    @staticmethod
    def get_user_from_client_identifier(plex: PlexServer, client_identifier: str):
        plex_sessions = plex.sessions()
        current_players = list(itertools.chain.from_iterable([s.players for s in plex_sessions]))
        matching_players = [p for p in current_players if p.machineIdentifier == client_identifier]
        if len(matching_players) == 0:
            return (None, None)
        player = matching_players[0]
        user = PlexUtils.get_user_from_user_id(plex, player.userID)
        if user is None:
            return (None, None)
        return (user.id, user.name)

    @staticmethod
    def get_user_from_user_id(plex: PlexServer, user_id: Union[int, str]):
        matching_users = [u for u in plex.systemAccounts() if u.id == int(user_id)]
        if len(matching_users) == 0:
            return None
        return matching_users[0]

    @staticmethod
    def get_selected_streams(episode: Episode):
        audio_stream = ([a for a in episode.audioStreams() if a.selected] + [None])[0]
        subtitle_stream = ([s for s in episode.subtitleStreams() if s.selected] + [None])[0]
        return audio_stream, subtitle_stream

    @staticmethod
    def is_episode_after(reference: Episode, episode: Episode):
        return reference.seasonNumber < episode.seasonNumber or \
            (reference.seasonNumber == episode.seasonNumber and reference.episodeNumber < episode.episodeNumber)

    @staticmethod
    def get_episodes_to_process(update_level: str, update_strategy: str, episode: Episode):
        show_or_season = None
        if update_level == "show":
            show_or_season = episode.show()
        elif update_level == "season":
            show_or_season = episode.season()
        episodes = show_or_season.episodes()
        if update_strategy == "next":
            episodes = [e for e in episodes if PlexUtils.is_episode_after(episode, e)]
        return episodes

    @staticmethod
    def match_audio_stream(reference: AudioStream, audio_streams: List[AudioStream]):
        # We only want stream with the same language code
        streams = [s for s in audio_streams if s.languageCode == reference.languageCode]
        if len(streams) == 0:
            return None
        if len(streams) == 1:
            return streams[0]
        # If multiple streams match, order them based on a score
        scores = [0] * len(streams)
        for index, stream in enumerate(streams):
            if reference.codec == stream.codec:
                scores[index] += 3
            if reference.audioChannelLayout == stream.audioChannelLayout:
                scores[index] += 3
            if reference.channels <= stream.channels:
                scores[index] += 1
            if reference.title is not None and stream.title is not None and reference.title == stream.title:
                scores[index] += 5
        return streams[scores.index(max(scores))]

    @staticmethod
    def match_subtitle_stream(reference: SubtitleStream, subtitle_streams: List[SubtitleStream]):
        # If no subtitle is selected, the reference stream can be 'None'
        if reference is None:
            return None
        # We only want stream with the same language code
        streams = [s for s in subtitle_streams if s.languageCode == reference.languageCode]
        if len(streams) == 0:
            return None
        if len(streams) == 1:
            return streams[0]
        # If multiple streams match, order them based on a score
        scores = [0] * len(streams)
        for index, stream in enumerate(streams):
            if reference.forced == stream.forced:
                scores[index] += 3
            if reference.codec is not None and stream.codec is not None and reference.codec == stream.codec:
                scores[index] += 1
            if reference.title is not None and stream.title is not None and reference.title == stream.title:
                scores[index] += 5
        return streams[scores.index(max(scores))]

    @staticmethod
    def get_track_changes(reference: Episode, episodes: List[Episode]):
        selected_audio_stream, selected_subtitle_stream = PlexUtils.get_selected_streams(reference)
        changes = list()
        for episode in episodes:
            episode.reload()
            for part in episode.iterParts():
                current_audio_stream, current_subtitle_stream = PlexUtils.get_selected_streams(part)
                # Audio stream
                matching_audio_stream = PlexUtils.match_audio_stream(selected_audio_stream, part.audioStreams())
                if matching_audio_stream is not None and matching_audio_stream.id != current_audio_stream.id:
                    changes.append((episode, part, AudioStream.STREAMTYPE, matching_audio_stream))
                # Subtitle stream
                matching_subtitle_stream = PlexUtils.match_subtitle_stream(selected_subtitle_stream, part.subtitleStreams())
                if current_subtitle_stream is not None and matching_subtitle_stream is None:
                    changes.append((episode, part, SubtitleStream.STREAMTYPE, None))
                if matching_subtitle_stream is not None and \
                        (current_subtitle_stream is None or matching_subtitle_stream.id != current_subtitle_stream.id):
                    changes.append((episode, part, SubtitleStream.STREAMTYPE, matching_subtitle_stream))
        return changes
