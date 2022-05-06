import json
from datetime import datetime, date, time


class DateTimeEncoder(json.JSONEncoder):

    def default(self, obj):
        if isinstance(obj, (datetime, date, time)):
            return obj.isoformat()
        return super(DateTimeEncoder, self).default(obj)
