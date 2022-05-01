import signal
import argparse
from time import sleep

from plex_auto_languages.plex_server import PlexServer
from plex_auto_languages.utils.notifier import Notifier
from plex_auto_languages.utils.logger import init_logger
from plex_auto_languages.utils.scheduler import Scheduler
from plex_auto_languages.utils.configuration import Configuration
from plex_auto_languages.utils.healthcheck import HealthcheckServer


class PlexAutoLanguages():

    def __init__(self, user_config_path: str):
        self.alive = False
        self.plex_alert_listener = None
        self.set_signal_handlers()

        # Health-check server
        self.healthcheck_server = HealthcheckServer("Plex-Auto-Languages", self.is_ready, self.is_healthy)
        self.healthcheck_server.start()

        # Configuration
        self.config = Configuration(user_config_path)

        # Notifications
        self.notifier = None
        if self.config.get("notifications.enable"):
            self.notifier = Notifier(self.config.get("notifications.apprise_configs"))

        # Plex
        self.plex = PlexServer(self.config.get("plex.url"), self.config.get("plex.token"), self.notifier, self.config)

        # Scheduler
        self.scheduler = None
        if self.config.get("scheduler.enable"):
            self.scheduler = Scheduler(self.config.get("scheduler.schedule_time"), self.scheduler_callback)

    def is_ready(self):
        return self.alive

    def is_healthy(self):
        return self.alive and self.plex.is_alive

    def set_signal_handlers(self):
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)

    def stop(self, *_):
        logger.info("Received SIGINT or SIGTERM, stopping gracefully")
        self.alive = False

    def start(self):
        logger.info("Starting alert listener")
        self.plex.start_alert_listener()
        if self.scheduler:
            logger.info("Starting scheduler")
            self.scheduler.start()
        self.alive = True
        while self.is_healthy():
            sleep(1)
        if self.scheduler:
            logger.info("Stopping scheduler")
            self.scheduler.stop_event.set()
        logger.info("Stopping alert listener")
        self.healthcheck_server.shutdown()

    def scheduler_callback(self):
        logger.info("Starting scheduler task")
        self.plex.start_deep_analysis()


if __name__ == "__main__":
    logger = init_logger()

    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config_file", type=str, help="Config file path")
    args = parser.parse_args()

    plex_auto_languages = PlexAutoLanguages(args.config_file)
    plex_auto_languages.start()
