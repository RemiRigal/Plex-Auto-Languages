import os
import re
import sys
import yaml
from collections.abc import Mapping

from utils.logger import get_logger


logger = get_logger()


def deep_dict_update(d, u):
    for k, v in u.items():
        if isinstance(v, Mapping):
            d[k] = deep_dict_update(d.get(k, {}), v)
        else:
            d[k] = v
    return d


def env_dict_update(d, var_name: str=""):
    for k, v in d.items():
        new_var_name = (f"{var_name}_{k}" if var_name != "" else k).upper()
        if isinstance(v, Mapping):
            d[k] = env_dict_update(d[k], new_var_name)
        elif new_var_name in os.environ:
            d[k] = yaml.safe_load(os.environ.get(new_var_name))
            logger.info(f"Setting value of parameter {new_var_name} from environment variable")
    return d


class Configuration(object):

    TRIGGER_ON_PLAY = "onPlay"
    TRIGGER_ON_ACTIVITY = "onActivity"

    def __init__(self, user_config_path: str):
        default_config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "default.yaml")
        with open(default_config_path, "r") as stream:
            self._config = yaml.safe_load(stream).get("plexautolanguages", {})
        if user_config_path is not None and os.path.exists(user_config_path):
            logger.info(f"Parsing config file '{user_config_path}'")
            self._override_from_config_file(user_config_path)
        self._override_from_env()
        self._override_plex_token_from_secret()
        self._validate_config()
        self._trigger_on_play = None
        self._trigger_on_activity = None
        self._trigger_on_schedule = None

    def get(self, parameter_path: str):
        return self._get(self._config, parameter_path)

    def _get(self, config: dict, parameter_path: str):
        separator = "."
        if separator in parameter_path:
            splitted = parameter_path.split(separator)
            return self._get(config[splitted[0]], separator.join(splitted[1:]))
        else:
            return config[parameter_path]

    @property
    def trigger_on_play(self):
        if self._trigger_on_play is None:
            self._trigger_on_play = self.get("trigger_on_play")
        return self._trigger_on_play
    
    @property
    def trigger_on_activity(self):
        if self._trigger_on_activity is None:
            self._trigger_on_activity = self.get("trigger_on_activity")
        return self._trigger_on_activity
    
    def _override_from_config_file(self, user_config_path: str):
        with open(user_config_path, "r") as stream:
            user_config = yaml.safe_load(stream).get("plexautolanguages", {})
        self._config = deep_dict_update(self._config, user_config)

    def _override_from_env(self):
        self._config = env_dict_update(self._config)

    def _override_plex_token_from_secret(self):
        plex_token_secret_path = "/run/secrets/plex_token"
        if not os.path.exists(plex_token_secret_path):
            return
        logger.info("Getting PLEX_TOKEN from Docker secret")
        with open(plex_token_secret_path, "r") as stream:
            plex_token = stream.read()
        self._config["plex"]["token"] = plex_token

    def _validate_config(self):
        if self.get("plex.url") == "":
            logger.error("A Plex URL is required")
            sys.exit(0)
        if self.get("plex.token") == "":
            logger.error("A Plex Token is required")
            sys.exit(0)
        if self.get("update_level") not in ["show", "season"]:
            logger.error("The 'update_level' parameter must be either 'show' or 'season'")
            sys.exit(0)
        if self.get("update_strategy") not in ["all", "next"]:
            logger.error("The 'update_strategy' parameter must be either 'all' or 'next'")
            sys.exit(0)
        if self.get("scheduler.enable") and not re.match(r"^\d{2}:\d{2}$", self.get("scheduler.schedule_time")):
            logger.error("A valid 'schedule_time' parameter with the format 'HH:MM' is required (ex: 02:30)")
            sys.exit(0)
        if self.get("notifications.enable") and not "apprise_configs" in self.get("notifications"):
            logger.error("To enable notifications, the field 'apprise_configs' is required")
            sys.exit(0)
        logger.info(f"The provided configuration has been successfully validated")

