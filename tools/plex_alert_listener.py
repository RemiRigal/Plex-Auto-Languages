import time
import json
import argparse
from datetime import datetime
from plexapi.server import PlexServer


def callback(message):
    message["time"] = datetime.now().isoformat()
    print(json.dumps(message))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--plex_url", type=str, default="http://localhost:32400", help="Plex URL")
    parser.add_argument("--plex_token", type=str, required=True, help="Plex Token")
    args = parser.parse_args()

    plex = PlexServer(args.plex_url, args.plex_token)

    notifier = plex.startAlertListener(callback)

    while notifier.is_alive():
        time.sleep(1)
    time.sleep(1)
