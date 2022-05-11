from datetime import datetime


def test_episode_parts(plex):
    assert len(plex.cache.episode_parts) == 46


def test_should_process_recently_added(plex):
    now = datetime.now()
    assert plex.cache.should_process_recently_added("123456", now) is True
    assert plex.cache.should_process_recently_added("123456", now) is False


def test_should_process_recently_updated(plex):
    assert plex.cache.should_process_recently_updated("123456") is True
    assert plex.cache.should_process_recently_updated("123456") is False
    plex.cache.refresh_library_cache()
    assert plex.cache.should_process_recently_updated("123456") is True
