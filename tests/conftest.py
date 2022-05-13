import os
import pytest
import plexapi

from plex_auto_languages.plex_server import PlexServer
from plex_auto_languages.utils.configuration import Configuration


SERVER_BASEURL = plexapi.CONFIG.get("auth.server_baseurl")
SERVER_TOKEN = plexapi.CONFIG.get("auth.server_token")


@pytest.fixture()
def config():
    assert SERVER_BASEURL, "Required SERVER_BASEURL not specified."
    assert SERVER_TOKEN, "Required SERVER_TOKEN not specified."
    os.environ["PLEX_URL"] = SERVER_BASEURL
    os.environ["PLEX_TOKEN"] = SERVER_TOKEN
    return Configuration(None)


@pytest.fixture()
def plex(config):
    return PlexServer(SERVER_BASEURL, SERVER_TOKEN, None, config)


@pytest.fixture
def show(plex):
    show = plex._plex.library.search(libtype="show", max_results=1)[0]
    print("Show: %s" % show)
    return show


@pytest.fixture()
def episode(plex):
    episode = plex.episodes()[0]
    print("Episode: %s" % episode)
    return episode
