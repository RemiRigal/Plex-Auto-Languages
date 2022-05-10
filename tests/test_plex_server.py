import math
from datetime import datetime
from plexapi.video import Episode


def test_unique_id(plex):
    assert plex.unique_id is not None and isinstance(plex.unique_id, str) and len(plex.unique_id) == 40


def test_episodes(plex):
    episodes = plex.episodes()
    assert len(episodes) == 46


def test_fetch_item(plex, episode):
    same_episode = plex.fetch_item(episode.key)
    assert same_episode is not None and isinstance(same_episode, Episode)
    assert episode == same_episode


def test_recently_added(plex, episode):
    added_at = episode.addedAt
    delta = datetime.now() - added_at
    delta_minutes = math.ceil(delta.total_seconds() / 60)
    recently_added = plex.get_recently_added_episodes(minutes=delta_minutes + 1)
    assert episode in recently_added


def test_last_watched_or_first(plex, episode):
    show = episode.show()
    show.markUnwatched()
    first_episode = show.episode(season=1, episode=1)
    last_watched_or_first = plex.get_last_watched_or_first_episode(show)
    assert first_episode == last_watched_or_first

    last_episode = show.episodes()[-1]
    last_episode.markWatched()
    last_watched_or_first = plex.get_last_watched_or_first_episode(show)
    assert last_episode == last_watched_or_first


def test_episode_short_name(plex, episode):
    show = episode.show()
    first_episode = show.episode(season=1, episode=1)
    assert plex.get_episode_short_name(first_episode, include_show=False) == "S01E01"
    assert plex.get_episode_short_name(first_episode, include_show=True) == f"'{show.title}' (S01E01)"


def test_sections(plex):
    sections = plex.get_show_sections()
    assert len(sections) == 1


def test_is_alive(plex):
    assert plex.is_alive is False
