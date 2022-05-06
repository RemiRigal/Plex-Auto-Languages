from enum import Enum


class EventType(Enum):

    PLAY_OR_ACTIVITY = 0
    NEW_EPISODE = 1
    UPDATED_EPISODE = 2
    SCHEDULER = 3
