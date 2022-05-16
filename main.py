import signal
import argparse
from time import sleep
from websocket import WebSocketConnectionClosedException

from plex_auto_languages.plex_server import PlexServer
from plex_auto_languages.utils.notifier import Notifier
from plex_auto_languages.utils.logger import init_logger
from plex_auto_languages.utils.scheduler import Scheduler
from plex_auto_languages.utils.configuration import Configuration
from plex_auto_languages.utils.healthcheck import HealthcheckServer


class PlexAutoLanguages():

    def __init__(self, user_config_path: str):
        self.alive = False
        self.must_stop = False
        self.stop_signal = False
        self.plex_alert_listener = None

        # Health-check server
        self.healthcheck_server = HealthcheckServer("Plex-Auto-Languages", self.is_ready, self.is_healthy)
        self.healthcheck_server.start()

        # Configuration
        self.config = Configuration(user_config_path)

        # Notifications
        self.notifier = None
        if self.config.get("notifications.enable"):
            self.notifier = Notifier(self.config.get("notifications.apprise_configs"))

        # Scheduler
        self.scheduler = None
        if self.config.get("scheduler.enable"):
            self.scheduler = Scheduler(self.config.get("scheduler.schedule_time"), self.scheduler_callback)

        # Plex
        self.plex = None

        self.set_signal_handlers()

    def init(self):
        self.plex = PlexServer(self.config.get("plex.url"), self.config.get("plex.token"), self.notifier, self.config)

    def is_ready(self):
        return self.alive

    def is_healthy(self):
        return self.alive and self.plex.is_alive

    def set_signal_handlers(self):
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)

    def stop(self, *_):
        logger.info("Received SIGINT or SIGTERM, stopping gracefully")
        self.must_stop = True
        self.stop_signal = True

    def start(self):
        if self.scheduler:
            self.scheduler.start()

        while not self.stop_signal:
            self.must_stop = False
            self.init()
            self.plex.start_alert_listener(self.alert_listener_error_callback)
            self.alive = True
            count = 0
            while not self.must_stop:
                sleep(1)
                count += 1
                if count % 60 == 0 and not self.plex.is_alive:
                    logger.warning("Lost connection to the Plex server")
                    self.must_stop = True
            self.alive = False
            self.plex.save_cache()
            if not self.stop_signal:
                sleep(1)
                logger.info("Trying to restore the connection to the Plex server...")

        if self.scheduler:
            self.scheduler.shutdown()
            self.scheduler.join()
        self.healthcheck_server.shutdown()

    def alert_listener_error_callback(self, error: Exception):
        if isinstance(error, WebSocketConnectionClosedException):
            logger.warning("The Plex server closed the websocket connection")
        else:
            logger.error("Alert listener had an unexpected error")
            logger.error(error, exc_info=True)
        self.must_stop = True

    def scheduler_callback(self):
        if self.plex or not self.plex.is_alive:
            return
        logger.info("Starting scheduler task")
        self.plex.start_deep_analysis()


if __name__ == "__main__":
    logger = init_logger()

    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config_file", type=str, help="Config file path")
    args = parser.parse_args()

    plex_auto_languages = PlexAutoLanguages(args.config_file)
    plex_auto_languages.start()
