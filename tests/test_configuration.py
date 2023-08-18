import os
import sys
import yaml
import shutil
import pytest
import logging
import tempfile
import warnings
from unittest.mock import patch

from plex_auto_languages.exceptions import InvalidConfiguration
from plex_auto_languages.utils.configuration import Configuration
from plex_auto_languages.utils.configuration import deep_dict_update, env_dict_update, is_docker
from plex_auto_languages.utils.configuration import logger


def test_is_docker():
    assert isinstance(is_docker(), bool)


def test_get_data_directory():
    os.environ["PLEX_URL"] = "http://localhost:32400"
    os.environ["PLEX_TOKEN"] = "token"
    config = Configuration(None)

    initial_platform = sys.platform
    with patch("plex_auto_languages.utils.configuration.is_docker", return_value=False):
        sys.platform = "win32"
        assert config._get_data_directory("test") == os.path.expanduser("~/AppData/Roaming/test")

        sys.platform = "linux"
        assert config._get_data_directory("test") == os.path.expanduser("~/.local/share/test")

        sys.platform = "darwin"
        assert config._get_data_directory("test") == os.path.expanduser("~/Library/Application Support/test")

        sys.platform = "freebsdxx"
        with patch("os.uname", return_value=["FreeBSD"]):
            assert config._get_data_directory("test") == os.path.expanduser("~/.local/share/test")

        sys.platform = "unknown_platform"
        with patch.object(warnings, "warn") as mocked_warn:
            assert config._get_data_directory("test") is None
            mocked_warn.assert_called_once()

        os.environ["DATA_PATH"] = "/tmp"
        config = Configuration(None)
        assert config._get_data_directory("test") == os.path.expanduser("/tmp/test")
        del os.environ["DATA_PATH"]

    config = Configuration(None)

    with patch("plex_auto_languages.utils.configuration.is_docker", return_value=True):
        sys.platform = "win32"
        assert config._get_data_directory("test") == "/config"

        sys.platform = "linux"
        assert config._get_data_directory("test") == "/config"

        sys.platform = "darwin"
        assert config._get_data_directory("test") == "/config"

        sys.platform = "freebsdxx"
        with patch("os.uname", return_value=["FreeBSD"]):
            assert config._get_data_directory("test") == "/config"

        sys.platform = "unknown_platform"
        assert config._get_data_directory("test") == "/config"

        os.environ["DATA_PATH"] = "/tmp"
        config = Configuration(None)
        assert config._get_data_directory("test") == os.path.expanduser("/tmp/test")
        del os.environ["DATA_PATH"]

    sys.platform = initial_platform


def test_deep_dict_update():
    original = {
        "nested": {
            "data1": 8,
            "data2": 12
        }
    }
    update = {
        "nested": {
            "data2": 42,
            "data3": 117
        }
    }
    updated = deep_dict_update(original, update)
    assert updated["nested"]["data1"] == 8
    assert updated["nested"]["data2"] == 42


def test_env_dict_update():
    original = {
        "nested": {
            "data1": 8,
            "data2": 12
        },
        "non_nested": "hello"
    }
    os.environ["NESTED_DATA2"] = "42"
    os.environ["NON_NESTED"] = "hi"
    updated = env_dict_update(original)
    assert updated["nested"]["data1"] == 8
    assert updated["nested"]["data2"] == 42
    assert updated["non_nested"] == "hi"


def test_configuration_none():
    os.environ["PLEX_URL"] = "http://localhost:32400"
    os.environ["PLEX_TOKEN"] = "token"

    config = Configuration(None)
    assert config.get("plex.url") == "http://localhost:32400"
    assert config.get("plex.token") == "token"

    del os.environ["PLEX_URL"]
    del os.environ["PLEX_TOKEN"]


def test_configuration_user_config():
    config_dict = {
        "plexautolanguages": {
            "plex": {
                "url": "http://localhost:32400",
                "token": "token"
            },
            "ignore_labels": "LABEL_1,LABEL_2"
        }
    }
    fd, path = tempfile.mkstemp()
    try:
        with open(fd, "w", encoding="utf-8") as stream:
            yaml.dump(config_dict, stream)
        config = Configuration(path)
        assert config.get("plex.url") == "http://localhost:32400"
        assert config.get("plex.token") == "token"
        assert isinstance(config.get("ignore_labels"), list)
        assert len(config.get("ignore_labels")) == 2
        assert "LABEL_1" in config.get("ignore_labels")
        assert "LABEL_2" in config.get("ignore_labels")
    finally:
        os.remove(path)


def test_configuration_docker_secret():
    os.environ["PLEX_URL"] = "http://localhost:32400"

    fd, path = tempfile.mkstemp()
    try:
        with open(fd, "w", encoding="utf-8") as stream:
            stream.write("token_with_docker_secret\n")
        os.environ["PLEX_TOKEN_FILE"] = path
        config = Configuration(None)
        assert config.get("plex.url") == "http://localhost:32400"
        assert config.get("plex.token") == "token_with_docker_secret"
    finally:
        os.remove(path)

    del os.environ["PLEX_URL"]
    del os.environ["PLEX_TOKEN_FILE"]


def test_configuration_debug():
    os.environ["PLEX_URL"] = "http://localhost:32400"
    os.environ["PLEX_TOKEN"] = "token"
    os.environ["DEBUG"] = "true"

    config = Configuration(None)
    assert config.get("debug") is True
    assert logger.level == logging.DEBUG

    del os.environ["PLEX_URL"]
    del os.environ["PLEX_TOKEN"]
    del os.environ["DEBUG"]


def test_configuration_unvalidated():
    with pytest.raises(InvalidConfiguration):
        _ = Configuration(None)

    os.environ["PLEX_URL"] = "http://localhost:32400"
    with pytest.raises(InvalidConfiguration):
        _ = Configuration(None)

    os.environ["PLEX_TOKEN"] = "token"
    os.environ["UPDATE_LEVEL"] = "_"
    with pytest.raises(InvalidConfiguration):
        _ = Configuration(None)
    del os.environ["UPDATE_LEVEL"]

    os.environ["UPDATE_STRATEGY"] = "_"
    with pytest.raises(InvalidConfiguration):
        _ = Configuration(None)
    del os.environ["UPDATE_STRATEGY"]

    config_dict = {
        "plexautolanguages": {
            "ignore_labels": 12
        }
    }
    fd, path = tempfile.mkstemp()
    try:
        with open(fd, "w", encoding="utf-8") as stream:
            yaml.dump(config_dict, stream)
        with pytest.raises(InvalidConfiguration):
            _ = Configuration(path)
    finally:
        os.remove(path)

    os.environ["SCHEDULER_ENABLE"] = "true"
    os.environ["SCHEDULER_SCHEDULE_TIME"] = "12h30"
    with pytest.raises(InvalidConfiguration):
        _ = Configuration(None)
    del os.environ["SCHEDULER_ENABLE"]
    del os.environ["SCHEDULER_SCHEDULE_TIME"]


def test_configuration_data_dir():
    with patch("plex_auto_languages.utils.configuration.is_docker", return_value=False):
        os.environ["PLEX_URL"] = "http://localhost:32400"
        os.environ["PLEX_TOKEN"] = "token"

        config = Configuration(None)
        data_dir = config._get_data_directory("PlexAutoLanguages")
        if os.path.exists(data_dir):
            shutil.rmtree(data_dir)

        _ = Configuration(None)
        assert os.path.exists(data_dir)

        del os.environ["PLEX_URL"]
        del os.environ["PLEX_TOKEN"]
