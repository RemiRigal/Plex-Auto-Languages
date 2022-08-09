import os
import copy
from datetime import datetime
from unittest.mock import patch

from plex_auto_languages.plex_server_cache import PlexServerCache


class FakeUser():

    def __init__(self, user_id):
        self.id = user_id

    def get_token(self, machine_identifier):
        return "token"


def test_episode_parts(plex):
    assert len(plex.cache.episode_parts) == 46


def test_is_refreshing(plex):
    plex.cache._is_refreshing = True
    assert plex.cache.refresh_library_cache() == ([], [])


def test_cache_dir(plex):
    mocked_path = "/tmp/mocked_cache_dir"
    plex.config._config["data_dir"] = mocked_path
    assert plex.config.get("data_dir") == mocked_path

    mocked_path_cache = os.path.join(mocked_path, "cache")
    if os.path.exists(mocked_path_cache):
        os.removedirs(mocked_path_cache)

    assert not os.path.exists(mocked_path_cache)
    assert plex.cache._get_cache_file_path() == os.path.join(mocked_path_cache, plex.unique_id)
    assert os.path.exists(mocked_path_cache)


def test_load_save():
    mocked_path = "/tmp/mocked_cache"
    if os.path.exists(mocked_path):
        os.remove(mocked_path)

    with patch.object(PlexServerCache, "_get_cache_file_path", return_value=mocked_path):
        with patch.object(PlexServerCache, "refresh_library_cache") as mocked_refresh:
            cache = PlexServerCache(None)
            mocked_refresh.assert_called_once()

            mocked_refresh.reset_mock()
            old_episode_parts = copy.deepcopy(cache.episode_parts)
            cache.save()
            cache = PlexServerCache(None)
            mocked_refresh.assert_not_called()

            assert old_episode_parts == cache.episode_parts


def test_instance_users(plex):
    assert plex.cache.get_instance_users() is None
    assert plex.cache.get_instance_users(check_validity=False) == []

    plex.cache.set_instance_users([FakeUser("user1"), FakeUser("user2")])
    assert len(plex.cache.get_instance_users()) == 2
    user1_token = plex.cache.get_instance_user_token("user1")
    assert user1_token is not None

    plex.cache.set_instance_users([FakeUser("user1")])
    assert len(plex.cache.get_instance_users()) == 1
    assert plex.cache.get_instance_user_token("user1") == user1_token


def test_instance_user_tokens(plex):
    assert plex.cache.get_instance_user_token("fake_user_id") is None
    plex.cache.set_instance_user_token("user_id", "token")
    assert plex.cache.get_instance_user_token("user_id") == "token"


def test_refresh(plex):
    keys = list(plex.cache.episode_parts.keys())
    assert len(keys) > 1
    first_key = keys[0]
    second_key = keys[1]

    del plex.cache.episode_parts[first_key]
    plex.cache.episode_parts[second_key] = []

    added, updated = plex.cache.refresh_library_cache()

    added_keys = [episode.key for episode in added]
    assert added_keys == [first_key]

    updated_keys = [episode.key for episode in updated]
    assert updated_keys == [second_key]


def test_should_process_recently_added(plex):
    now = datetime.now()
    assert plex.cache.should_process_recently_added("123456", now) is True
    assert plex.cache.should_process_recently_added("123456", now) is False


def test_should_process_recently_updated(plex):
    assert plex.cache.should_process_recently_updated("123456") is True
    assert plex.cache.should_process_recently_updated("123456") is False
    plex.cache.refresh_library_cache()
    assert plex.cache.should_process_recently_updated("123456") is True
