import time
from datetime import datetime, timedelta

from plex_auto_languages.utils.scheduler import Scheduler


UPDATED = False


def dummy_callback():
    global UPDATED
    UPDATED = True


def test_scheduler():
    global UPDATED
    next_minute = (datetime.now() + timedelta(minutes=1, seconds=5)).strftime("%H:%M")
    scheduler = Scheduler(next_minute, dummy_callback)

    assert scheduler.is_alive() is False

    scheduler.start()
    time.sleep(1)

    assert scheduler.is_alive() is True

    start_time = time.time()
    while not UPDATED and time.time() - start_time < 70:
        time.sleep(1)
    assert UPDATED is True

    assert scheduler.is_alive() is True

    scheduler.shutdown()
    time.sleep(6)

    assert scheduler.is_alive() is False
