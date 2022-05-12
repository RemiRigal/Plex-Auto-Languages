import pytest
from unittest.mock import patch, call

from plex_auto_languages.constants import EventType
from plex_auto_languages.utils.notifier import Notifier, ConditionalApprise


@pytest.mark.filterwarnings("ignore:Possible nested set at position")
def test_notifier():
    notifier = Notifier([])
    assert len(notifier._global_apprise) == 0
    assert len(notifier._user_apprise) == 0

    config = [
        "pover://user@token",
        {
            "urls": ["pover://user@token"]
        },
        {
            "urls": "pover://user@token"
        },
        {
            "someother_field": None
        },
        {
            "urls": "pover://user@token",
            "users": "User1"
        },
        {
            "urls": "pover://user@token",
            "users": ["User1"]
        },
        {
            "urls": "pover://user@token",
            "users": ["User1", "User2"]
        },
        {
            "urls": "pover://user@token",
            "users": "User3",
            "events": "play_or_activity"
        },
        {
            "urls": "pover://user@token",
            "users": "User4",
            "events": ["play_or_activity", "scheduler"]
        }
    ]
    notifier = Notifier(config)
    assert len(notifier._global_apprise) == 3
    assert len(notifier._global_apprise._event_types) == 0
    assert len(notifier._user_apprise["User1"]) == 3
    assert len(notifier._user_apprise["User2"]) == 1
    assert len(notifier._user_apprise["User3"]) == 1
    assert notifier._user_apprise["User3"]._event_types == {EventType.PLAY_OR_ACTIVITY}
    assert len(notifier._user_apprise["User4"]) == 1
    assert notifier._user_apprise["User4"]._event_types == {EventType.PLAY_OR_ACTIVITY, EventType.SCHEDULER}

    title, body = "title", "body"
    mocked_call = call(title=title, body=body)

    with patch.object(ConditionalApprise, "notify") as mocked_notify:
        notifier.notify(title, body, EventType.PLAY_OR_ACTIVITY)
        mocked_notify.assert_has_calls([mocked_call] * 1)

    with patch.object(ConditionalApprise, "notify") as mocked_notify:
        notifier.notify_user(title, body, "User1", EventType.PLAY_OR_ACTIVITY)
        mocked_notify.assert_has_calls([mocked_call] * 2)

    with patch.object(ConditionalApprise, "notify") as mocked_notify:
        notifier.notify_user(title, body, "User2", EventType.PLAY_OR_ACTIVITY)
        mocked_notify.assert_has_calls([mocked_call] * 2)

    with patch.object(ConditionalApprise, "notify") as mocked_notify:
        notifier.notify_user(title, body, "User3", EventType.UPDATED_EPISODE)
        mocked_notify.assert_has_calls([mocked_call] * 1)

    with patch.object(ConditionalApprise, "notify") as mocked_notify:
        notifier.notify_user(title, body, "User4", EventType.PLAY_OR_ACTIVITY)
        mocked_notify.assert_has_calls([mocked_call] * 2)

    with patch.object(ConditionalApprise, "notify") as mocked_notify:
        notifier.notify_user(title, body, "User4", EventType.SCHEDULER)
        mocked_notify.assert_has_calls([mocked_call] * 2)

    with patch.object(ConditionalApprise, "notify") as mocked_notify:
        notifier.notify_user(title, body, "User4", EventType.NEW_EPISODE)
        mocked_notify.assert_has_calls([mocked_call] * 1)

    with patch.object(ConditionalApprise, "notify") as mocked_notify:
        notifier.notify_user(title, body, "User4", EventType.UPDATED_EPISODE)
        mocked_notify.assert_has_calls([mocked_call] * 1)

    with patch.object(ConditionalApprise, "notify") as mocked_notify:
        notifier.notify_user(title, body, "User5", EventType.PLAY_OR_ACTIVITY)
        mocked_notify.assert_has_calls([mocked_call] * 1)
