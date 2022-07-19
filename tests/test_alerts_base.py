import pytest

from plex_auto_languages.alerts import PlexAlert


def test_alert(plex):
    alert = PlexAlert({})
    assert alert._message == {}
    assert alert.message == alert._message
    with pytest.raises(NotImplementedError):
        alert.process(plex)
