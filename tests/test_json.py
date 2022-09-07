import pytest
from datetime import datetime

from plex_auto_languages.utils.json_encoders import DateTimeEncoder


def test_json():
    encoder = DateTimeEncoder()
    now = datetime.now()

    assert encoder.default(now) == now.isoformat()

    with pytest.raises(TypeError):
        encoder.default(12)
