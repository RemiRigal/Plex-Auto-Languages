import argparse
import os
import shutil
import socket
import time
from shutil import copyfile, which
from subprocess import call
from uuid import uuid4

import plexapi
from plexapi.exceptions import BadRequest
from plexapi.myplex import MyPlexAccount
from plexapi.server import PlexServer
from plexapi.utils import SEARCHTYPES
from tqdm import tqdm


DOCKER_CMD = [
    "docker",
    "run",
    "-d",
    "--name",
    "plex-test-%(container_name_extra)s%(image_tag)s",
    "--restart",
    "on-failure",
    "-p",
    "32400:32400/tcp",
    "-p",
    "3005:3005/tcp",
    "-p",
    "8324:8324/tcp",
    "-p",
    "32469:32469/tcp",
    "-p",
    "1900:1900/udp",
    "-p",
    "32410:32410/udp",
    "-p",
    "32412:32412/udp",
    "-p",
    "32413:32413/udp",
    "-p",
    "32414:32414/udp",
    "-e",
    "PLEX_CLAIM=%(claim_token)s",
    "-e",
    "ADVERTISE_IP=http://%(advertise_ip)s:32400/",
    "-e",
    "TZ=%(timezone)s",
    "-e",
    "LANG=%(language)s",
    "-h",
    "%(hostname)s",
    "-v",
    "%(destination)s/db:/config",
    "-v",
    "%(destination)s/transcode:/transcode",
    "-v",
    "%(destination)s/media:/data",
    "linuxserver/plex:%(image_tag)s",
]


STUB_VIDEO_PATH = os.path.expanduser("~/.cache/data/empty.mkv")


def check_ext(path, ext):
    """I hate glob so much."""
    result = []
    for root, dirs, fil in os.walk(path):
        for f in fil:
            fp = os.path.join(root, f)
            if fp.endswith(ext):
                result.append(fp)
    return result


class ExistingSection(Exception):
    """This server has sections, exiting"""

    def __init__(self, *args):
        raise SystemExit("This server has sections exiting")


def clean_pms(server, path):
    for section in server.library.sections():
        print("Deleting %s" % section.title)
        section.delete()

    server.library.cleanBundles()
    server.library.optimize()
    print("optimized db and removed any bundles")

    shutil.rmtree(path, ignore_errors=False, onerror=None)
    print("Deleted %s" % path)


def setup_tv_shows(root_path):
    print("Setup files for the TV-Shows section...")
    os.makedirs(root_path, exist_ok=True)
    tv_shows = {
        "The Mandalorian": [list(range(1, 3)), list(range(1, 9))],
        "Peaky Blinders": [list(range(1, 6)), list(range(1, 7))],
    }
    expected_media_count = 0
    for show_name, seasons in tv_shows.items():
        os.makedirs(os.path.join(root_path, show_name), exist_ok=True)
        season_ids, episode_ids = seasons
        for season_id in season_ids:
            for episode_id in episode_ids:
                expected_media_count += 1
                episode_path = os.path.join(
                    root_path, show_name, "%sS%02dE%02d.mkv" % (show_name.replace(" ", "."), season_id, episode_id)
                )
                if not os.path.isfile(episode_path):
                    copyfile(STUB_VIDEO_PATH, episode_path)
    return expected_media_count


def get_default_ip():
    """ Return the first IP address of the current machine if available. """
    available_ips = list(
        set(
            [
                i[4][0]
                for i in socket.getaddrinfo(socket.gethostname(), None)
                if i[4][0] not in ("127.0.0.1", "::1")
                and not i[4][0].startswith("fe80:")
            ]
        )
    )
    return available_ips[0] if len(available_ips) else None


def get_plex_account(opts):
    """ Authenticate with Plex using the command line options. """
    if not opts.unclaimed:
        if opts.token:
            return MyPlexAccount(token=opts.token)
        return plexapi.utils.getMyPlexAccount(opts)
    return None


def add_library_section(server, section):
    """ Add the specified section to our Plex instance. This tends to be a bit
        flaky, so we retry a few times here.
    """
    start = time.time()
    runtime = 0
    while runtime < 60:
        try:
            server.library.add(**section)
            return True
        except BadRequest as err:
            if "server is still starting up. Please retry later" in str(err):
                time.sleep(1)
                continue
            raise
        runtime = time.time() - start
    raise SystemExit("Timeout adding section to Plex instance.")


def create_section(server, section, opts): # noqa
    processed_media = 0
    expected_media_count = section.pop("expected_media_count", 0)
    expected_media_type = (section["type"],)
    if section["type"] == "show":
        expected_media_type = ("show", "season", "episode")
    if section["type"] == "artist":
        expected_media_type = ("artist", "album", "track")
    expected_media_type = tuple(SEARCHTYPES[t] for t in expected_media_type)

    def alert_callback(data):
        """ Listen to the Plex notifier to determine when metadata scanning is complete. """
        global processed_media
        if data["type"] == "timeline":
            for entry in data["TimelineEntry"]:
                if (
                    entry.get("identifier", "com.plexapp.plugins.library")
                    == "com.plexapp.plugins.library"
                ):
                    # Missed mediaState means that media was processed (analyzed & thumbnailed)
                    if (
                        "mediaState" not in entry
                        and entry["type"] in expected_media_type
                    ):
                        # state=5 means record processed, applicable only when metadata source was set
                        if entry["state"] == 5:
                            cnt = 1
                            if entry["type"] == SEARCHTYPES["show"]:
                                show = server.library.sectionByID(
                                    entry["sectionID"]
                                ).get(entry["title"])
                                cnt = show.leafCount
                            bar.update(cnt)
                            processed_media += cnt
                        # state=1 means record processed, when no metadata source was set
                        elif (
                            entry["state"] == 1
                            and entry["type"] == SEARCHTYPES["photo"]
                        ):
                            bar.update()
                            processed_media += 1

    runtime = 0
    start = time.time()
    bar = tqdm(desc="Scanning section " + section["name"], total=expected_media_count)
    notifier = server.startAlertListener(alert_callback)
    time.sleep(3)
    add_library_section(server, section)
    while bar.n < bar.total:
        if runtime >= 120:
            print("Metadata scan taking too long, but will continue anyway..")
            break
        time.sleep(3)
        runtime = int(time.time() - start)
    bar.close()
    notifier.stop()


if __name__ == "__main__": # noqa
    default_ip = get_default_ip()
    parser = argparse.ArgumentParser(description=__doc__)
    # Authentication arguments
    mg = parser.add_mutually_exclusive_group()
    g = mg.add_argument_group()
    g.add_argument("--username", help="Your Plex username")
    g.add_argument("--password", help="Your Plex password")
    mg.add_argument(
        "--token",
        help="Plex.tv authentication token",
        default=plexapi.CONFIG.get("auth.server_token"),
    )
    mg.add_argument(
        "--unclaimed",
        help="Do not claim the server",
        default=False,
        action="store_true",
    )
    # Test environment arguments
    parser.add_argument(
        "--no-docker", help="Use docker", default=False, action="store_true"
    )
    parser.add_argument(
        "--timezone", help="Timezone to set inside plex", default="UTC"
    )  # noqa
    parser.add_argument(
        "--language", help="Language to set inside plex", default="en_US.UTF-8"
    )  # noqa
    parser.add_argument(
        "--destination",
        help="Local path where to store all the media",
        default=os.path.join(os.getcwd(), "plex"),
    )  # noqa
    parser.add_argument(
        "--advertise-ip",
        help="IP address which should be advertised by new Plex instance",
        required=default_ip is None,
        default=default_ip,
    )  # noqa
    parser.add_argument(
        "--docker-tag", help="Docker image tag to install", default="latest"
    )  # noqa
    parser.add_argument(
        "--bootstrap-timeout",
        help="Timeout for each step of bootstrap, in seconds (default: %(default)s)",
        default=180,
        type=int,
    )  # noqa
    parser.add_argument(
        "--server-name",
        help="Name for the new server",
        default="plex-test-docker-%s" % str(uuid4()),
    )  # noqa
    parser.add_argument(
        "--accept-eula", help="Accept Plex's EULA", default=False, action="store_true"
    )  # noqa
    parser.add_argument(
        "--show-token",
        help="Display access token after bootstrap",
        default=False,
        action="store_true",
    )  # noqa
    opts, _ = parser.parse_known_args()

    account = get_plex_account(opts)
    if account:
        print("Successfully logged as user '%s'" % account.username)

    path = os.path.realpath(os.path.expanduser(opts.destination))
    media_path = os.path.join(path, "media")
    os.makedirs(media_path, exist_ok=True)

    # Download the Plex Docker image
    if opts.no_docker is False:
        print(
            "Creating Plex instance named %s with advertised ip %s"
            % (opts.server_name, opts.advertise_ip)
        )
        if which("docker") is None:
            print("Docker is required to be available")
            exit(1)
        if call(["docker", "pull", "linuxserver/plex:%s" % opts.docker_tag]) != 0:
            print("Got an error when executing docker pull!")
            exit(1)

        # Start the Plex Docker container

        arg_bindings = {
            "destination": path,
            "hostname": opts.server_name,
            "claim_token": account.claimToken() if account else "",
            "timezone": opts.timezone,
            "language": opts.language,
            "advertise_ip": opts.advertise_ip,
            "image_tag": opts.docker_tag,
            "container_name_extra": "" if account else "unclaimed-",
        }
        docker_cmd = [c % arg_bindings for c in DOCKER_CMD]
        exit_code = call(docker_cmd)
        if exit_code != 0:
            raise SystemExit(
                "Error %s while starting the Plex docker container" % exit_code
            )

    # Wait for the Plex container to start
    print("Waiting for the Plex to start..")
    start = time.time()
    runtime = 0
    server = None
    while not server and (runtime < opts.bootstrap_timeout):
        try:
            if account:
                server = account.device(opts.server_name).connect()
            else:
                server = PlexServer("http://%s:32400" % opts.advertise_ip)

        except KeyboardInterrupt:
            break

        except Exception as err:
            print(err)
            time.sleep(1)

        runtime = time.time() - start

    if not server:
        raise SystemExit(
            "Server didn't appear in your account after %ss" % opts.bootstrap_timeout
        )

    print("Plex container started after %ss" % int(runtime))
    print("Plex server version %s" % server.version)

    if opts.accept_eula:
        server.settings.get("acceptedEULA").set(True)
    # Disable settings for background tasks when using the test server.
    # These tasks won't work on the test server since we are using fake media files
    if not opts.unclaimed and account and account.subscriptionActive:
        server.settings.get("GenerateIntroMarkerBehavior").set("never")
    server.settings.get("GenerateBIFBehavior").set("never")
    server.settings.get("GenerateChapterThumbBehavior").set("never")
    server.settings.get("LoudnessAnalysisBehavior").set("never")
    server.settings.save()

    sections = []

    # Lets add a check here do somebody don't mess up
    # there normal server if they run manual tests.
    # Like i did....
    if len(server.library.sections()) and opts.no_docker is True:
        ans = input(
            "The server has %s sections, do you wish to remove it?\n> "
            % len(server.library.sections())
        )
        if ans in ("y", "Y", "Yes"):
            ans = input(
                "Are you really sure you want to delete %s libraries? There is no way back\n> "
                % len(server.library.sections())
            )
            if ans in ("y", "Y", "Yes"):
                clean_pms(server, path)
            else:
                raise ExistingSection()
        else:
            raise ExistingSection()

    # Prepare TV Show section
    tvshows_path = os.path.join(media_path, "TV-Shows")
    episode_count = setup_tv_shows(tvshows_path)
    sections.append(dict(
        name="TV Shows",
        type="show",
        location="/data/TV-Shows" if opts.no_docker is False else tvshows_path,
        agent="tv.plex.agents.series",
        scanner="Plex TV Series",
        language="en-US",
        expected_media_count=episode_count,
    ))

    # Create the Plex library in our instance
    if sections:
        print("Creating the Plex libraries on %s" % server.friendlyName)
        for section in sections:
            create_section(server, section, opts)

    # Create a home user
    if account:
        print("Creating home user 'HomeUser'")
        account.createHomeUser("HomeUser", server)

    # Finished: Display our Plex details
    print("Base URL is %s" % server.url("", False))
    if account and opts.show_token:
        print("Auth token is %s" % account.authenticationToken)
    print("Server %s is ready to use!" % opts.server_name)

    time.sleep(10)
