import os
import re
import sys
import pathlib
import logging
from collections.abc import Mapping
import yaml
import warnings

from plex_auto_languages.utils.logger import get_logger
from plex_auto_languages.exceptions import InvalidConfiguration


logger = get_logger()


def deep_dict_update(original, update):
    for key, value in update.items():
        if isinstance(value, Mapping):
            original[key] = deep_dict_update(original.get(key, {}), value)
        else:
            original[key] = value
    return original


def env_dict_update(original, var_name: str = ""):
    for key, value in original.items():
        new_var_name = (f"{var_name}_{key}" if var_name != "" else key).upper()
        if isinstance(value, Mapping):
            original[key] = env_dict_update(original[key], new_var_name)
        elif new_var_name in os.environ:
            original[key] = yaml.safe_load(os.environ.get(new_var_name))
            logger.info(f"Setting value of parameter {new_var_name} from environment variable")
    return original


def is_docker():
    path = "/proc/self/cgroup"
    return (
        os.path.exists("/.dockerenv") or
        os.path.isfile(path) and any("docker" in line for line in open(path, "r", encoding="utf-8")) or
        os.getenv("CONTAINERIZED", "False").lower() == "true"
    )


def get_data_directory(app_name: str):
    home = pathlib.Path.home()
    if is_docker():
        return "/config"
    if sys.platform == "win32":
        return str(home / f"AppData/Roaming/{app_name}")
    if sys.platform == "linux":
        return str(home / f".local/share/{app_name}")
    if sys.platform == "darwin":
        return str(home / f"Library/Application Support/{app_name}")
    if os.uname()[0] == "FreeBSD":
        return str(home / f".local/share/{app_name}")
    warnings.warn("Warning: Unsupported Operating System!")
    return None


class Configuration():

    def __init__(self, user_config_path: str):
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        default_config_path = os.path.join(root_dir, "config", "default.yaml")
        with open(default_config_path, "r", encoding="utf-8") as stream:
            self._config = yaml.safe_load(stream).get("plexautolanguages", {})
        if user_config_path is not None and os.path.exists(user_config_path):
            logger.info(f"Parsing config file '{user_config_path}'")
            self._override_from_config_file(user_config_path)
        self._override_from_env()
        self._override_plex_token_from_secret()
        self._validate_config()
        self._add_system_config()
        if self.get("debug"):
            logger.setLevel(logging.DEBUG)
            logger.debug("Debug mode enabled")

    def get(self, parameter_path: str):
        return self._get(self._config, parameter_path)

    def _get(self, config: dict, parameter_path: str):
        separator = "."
        if separator in parameter_path:
            splitted = parameter_path.split(separator)
            return self._get(config[splitted[0]], separator.join(splitted[1:]))
        return config[parameter_path]

    def _override_from_config_file(self, user_config_path: str):
        with open(user_config_path, "r", encoding="utf-8") as stream:
            user_config = yaml.safe_load(stream).get("plexautolanguages", {})
        self._config = deep_dict_update(self._config, user_config)

    def _override_from_env(self):
        self._config = env_dict_update(self._config)

    def _override_plex_token_from_secret(self):
        plex_token_file_path = os.environ.get("PLEX_TOKEN_FILE", "/run/secrets/plex_token")
        if not os.path.exists(plex_token_file_path):
            return
        logger.info("Getting PLEX_TOKEN from Docker secret")
        with open(plex_token_file_path, "r", encoding="utf-8") as stream:
            plex_token = stream.readline().strip()
        self._config["plex"]["token"] = plex_token

    def _validate_config(self):
        if self.get("plex.url") == "":
            logger.error("A Plex URL is required")
            raise InvalidConfiguration
        if self.get("plex.token") == "":
            logger.error("A Plex Token is required")
            raise InvalidConfiguration
        if self.get("update_level") not in ["show", "season"]:
            logger.error("The 'update_level' parameter must be either 'show' or 'season'")
            raise InvalidConfiguration
        if self.get("update_strategy") not in ["all", "next"]:
            logger.error("The 'update_strategy' parameter must be either 'all' or 'next'")
            raise InvalidConfiguration
        if self.get("scheduler.enable") and not re.match(r"^\d{2}:\d{2}$", self.get("scheduler.schedule_time")):
            logger.error("A valid 'schedule_time' parameter with the format 'HH:MM' is required (ex: 02:30)")
            raise InvalidConfiguration
        logger.info("The provided configuration has been successfully validated")

    def _add_system_config(self):
        self._config["docker"] = is_docker()
        self._config["data_dir"] = get_data_directory("PlexAutoLanguages")
        if not os.path.exists(self._config["data_dir"]):
            os.makedirs(self._config["data_dir"])
