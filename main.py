import sys
import signal
import argparse
from time import sleep
from typing import List
from apprise import Apprise
from plexapi.video import Episode
from plexapi.server import PlexServer
from datetime import datetime, timedelta
from plexapi.media import AudioStream, SubtitleStream

from utils.logger import init_logger
from utils.scheduler import Scheduler
from utils.configuration import Configuration
from utils.plex import PlexUtils


class PlexAutoLanguages(object):

    def __init__(self, user_config_path: str):
        self.alive = False
        self.set_signal_handlers()
        self.notifier = None
        self.config = Configuration(user_config_path)
        # Plex
        self.plex = PlexServer(self.config.get("plex.url"), self.config.get("plex.token"))
        self.plex_user_id = self.get_plex_user_id()
        self.session_states = dict()    # session_key: session_state
        self.default_streams = dict()   # item_key: (audio_stream_id, substitle_stream_id)
        self.user_clients = dict()      # client_identifier: user_id
        # Scheduler
        self.scheduler = None
        if self.config.get("scheduler.enable"):
            self.scheduler = Scheduler(self.config.get("scheduler.schedule_time"), self.scheduler_callback)
        # Notifications
        self.apprise = None
        if self.config.get("notifications.enable"):
            self.apprise = Apprise()
            for apprise_config in self.config.get("notifications.apprise_configs"):
                self.apprise.add(apprise_config)

    def get_plex_user_id(self):
        plex_username = self.plex.myPlexAccount().username
        for account in self.plex.systemAccounts():
            if account.name == plex_username:
                logger.info(f"Successfully connected as user '{account.name}' (id: {account.id})")
                return account.id
        logger.error("Unable to find the user id associated with the provided Plex Token")
        sys.exit(0)

    def set_signal_handlers(self):
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)

    def stop(self, *args):
        logger.info("Received SIGINT or SIGTERM, stopping gracefully")
        self.alive = False

    def start(self):
        logger.info("Starting alert listener")
        self.notifier = self.plex.startAlertListener(self.alert_listener_callback)
        if self.scheduler:
            logger.info("Starting scheduler")
            self.scheduler.start()
        self.alive = True
        while self.notifier.is_alive() and self.alive:
            sleep(1)
        if self.scheduler:
            logger.info("Stopping scheduler")
            self.scheduler.stop_event.set()
        logger.info("Stopping alert listener")

    def alert_listener_callback(self, message: dict):
        if self.config.get("trigger_on_play") and message["type"] == "playing":
            self.process_playing_message(message)
        elif self.config.get("trigger_on_activity") and message["type"] == "activity":
            self.process_activity_message(message)

    def process_playing_message(self, message: dict):
        for play_session in message["PlaySessionStateNotification"]:
            try:
                self.process_play_session(play_session)
            except Exception:
                logger.exception("Unable to process play session")

    def process_play_session(self, play_session: dict):
        # Get User id and user's Plex instance
        client_identifier = play_session["clientIdentifier"]
        if client_identifier not in self.user_clients:
            self.user_clients[client_identifier] = PlexUtils.get_user_from_client_identifier(self.plex, client_identifier)
        user_id, username = self.user_clients[client_identifier]
        if user_id is None:
            return
        logger.debug(f"User id: {user_id}")
        user_plex = PlexUtils.get_plex_instance_of_user(self.plex, self.plex_user_id, user_id)
        if user_plex is None:
            return

        # Skip if not an Episode
        item = user_plex.fetchItem(play_session["key"])
        if not isinstance(item, Episode):
            return

        # Skip is the session state is unchanged
        session_key = play_session["sessionKey"]
        session_state = play_session["state"]
        if session_key in self.session_states and self.session_states[session_key] == session_state:
            return
        self.session_states[session_key] = session_state

        # Reset cache if the session is stopped
        if session_state == "stopped":
            logger.info("Reseting cache due to stopped session")
            del self.session_states[session_key]
            del self.user_clients[client_identifier]

        # Skip if selected streams are unchanged
        item.reload()
        selected_audio_stream, selected_subtitle_stream = PlexUtils.get_selected_streams(item)
        pair_id = (selected_audio_stream.id, selected_subtitle_stream.id if selected_subtitle_stream is not None else None)
        if item.key in self.default_streams and self.default_streams[item.key] == pair_id:
            return
        self.default_streams.setdefault(item.key, pair_id)

        # Change tracks if needed
        self.change_default_tracks_if_needed(username, item)

    def process_activity_message(self, message: dict):
        for activity in message["ActivityNotification"]:
            try:
                self.process_activity(activity)
            except Exception:
                logger.exception("Unable to process activity")

    def process_activity(self, activity: dict):
        event_state = activity["event"]
        if event_state != "ended":
            return
        activity_type = activity["Activity"]["type"]
        if activity_type != "library.refresh.items":
            return
        media_key = activity["Activity"]["Context"]["key"]
        user_id = activity["Activity"]["userID"]

        # Switch to the user's Plex instance
        user_plex = PlexUtils.get_plex_instance_of_user(self.plex, self.plex_user_id, user_id)
        if user_plex is None:
            return

        # Skip if not an Episode
        item = user_plex.fetchItem(media_key)
        if not isinstance(item, Episode):
            return

        # Change tracks if needed
        item.reload()
        user = PlexUtils.get_user_from_user_id(self.plex, user_id)
        if user is None:
            return
        self.change_default_tracks_if_needed(user.name, item)

    def notify_changes(self, username: str, episode: Episode, episodes: List[Episode], nb_updated: int, nb_total: int):
        target_audio, target_subtitles = PlexUtils.get_selected_streams(episode)
        season_numbers = [e.seasonNumber for e in episodes]
        min_season_number, max_season_number = min(season_numbers), max(season_numbers)
        min_episode_number = min([e.episodeNumber for e in episodes if e.seasonNumber == min_season_number])
        max_episode_number = max([e.episodeNumber for e in episodes if e.seasonNumber == max_season_number])
        from_str = f"S{min_season_number:02}E{min_episode_number:02}"
        to_str = f"S{max_season_number:02}E{max_episode_number:02}"
        range_str = f"{from_str} - {to_str}" if from_str != to_str else from_str
        title = f"PlexAutoLanguages - {episode.show().title}"
        message = (
            f"Show: {episode.show().title}\n"
            f"User: {username}\n"
            f"Audio: {target_audio.displayTitle if target_audio is not None else 'None'}\n"
            f"Subtitles: {target_subtitles.displayTitle if target_subtitles is not None else 'None'}\n"
            f"Updated episodes: {nb_updated}/{nb_total} ({range_str})"
        )
        inline_message = message.replace("\n", " | ")
        logger.info(f"Language update: {inline_message}")
        if self.apprise is None:
            return
        self.apprise.notify(title=title, body=message)

    def scheduler_callback(self):
        logger.info("Starting scheduler task")
        min_date = datetime.now() - timedelta(days=1)
        history = self.plex.history(mindate=min_date)
        for episode in [media for media in history if isinstance(media, Episode)]:
            episode.reload()
            self.change_default_tracks_if_needed(None, episode)

    def change_default_tracks_if_needed(self, username: str, episode: Episode):
        # Get episodes to update
        update_level = self.config.get("update_level")
        update_strategy = self.config.get("update_strategy")
        episodes = PlexUtils.get_episodes_to_process(update_level, update_strategy, episode)

        # Get changes to perform
        changes = PlexUtils.get_track_changes(episode, episodes)
        if len(changes) == 0:
            return

        # Perform changes
        for _, part, stream_type, new_stream in changes:
            if stream_type == AudioStream.STREAMTYPE:
                part.setDefaultAudioStream(new_stream)
            elif stream_type == SubtitleStream.STREAMTYPE and new_stream is None:
                part.resetDefaultSubtitleStream()
            elif stream_type == SubtitleStream.STREAMTYPE:
                part.setDefaultSubtitleStream(new_stream)

        # Notify changes
        nb_updated_episodes = len({e.key for e, _, _, _ in changes})
        nb_total_episodes = len(episodes)
        self.notify_changes(username, episode, episodes, nb_updated_episodes, nb_total_episodes)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config_file", type=str, help="Config file path")
    return parser.parse_args()


if __name__ == "__main__":
    logger = init_logger()

    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config_file", type=str, help="Config file path")
    args = parser.parse_args()

    plex_auto_languages = PlexAutoLanguages(args.config_file)
    try:
        plex_auto_languages.start()
    except KeyboardInterrupt:
        logger.info("Caught KeyboardInterrupt, shutting down gracefully")
