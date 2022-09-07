import json
from datetime import datetime, date, time


class DateTimeEncoder(json.JSONEncoder):

    def default(self, o):
        if isinstance(o, (datetime, date, time)):
            return o.isoformat()
        return super().default(o)
