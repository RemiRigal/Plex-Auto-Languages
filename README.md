# Plex Auto Languages

[![GitHub Build](https://img.shields.io/github/workflow/status/RemiRigal/Plex-Auto-Languages/dockerhub_build_push?style=flat-square)](https://github.com/RemiRigal/Plex-Auto-Languages/actions/workflows/dockerhub_build_push.yml)
[![Docker Pulls](https://img.shields.io/docker/pulls/remirigal/plex-auto-languages?style=flat-square)](https://hub.docker.com/r/remirigal/plex-auto-languages)
[![Version](https://img.shields.io/github/v/tag/RemiRigal/Plex-Auto-Languages?style=flat-square&label=version)](https://github.com/RemiRigal/Plex-Auto-Languages/tags)
[![License](https://img.shields.io/github/license/RemiRigal/Plex-Auto-Languages?style=flat-square)](https://github.com/RemiRigal/Plex-Auto-Languages/blob/master/LICENSE)

This application lets you have a Netflix-like experience by auto-updating the language of your Plex TV Show episodes based on the current language you are using without messing with your existing language preferences.  

**You want to watch Squid Game in korean with english subtitles ?**  
Set the language for the first episode and don't think about it for the rest of the show. :heavy_check_mark:

**You want to watch The Mandalorian in english but still want to watch Game of Thrones in french ?**  
Don't worry, the language is set per TV Show and it won't interfere. :heavy_check_mark:

**You have multiple managed and shared users with various preferences ?**  
The proper tracks will be selected automatically and independently for all your users. :heavy_check_mark:


## Getting Started

The application requires a `Plex Token`, if you don't know how to find yours, please see the [official guide](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/).

The recommended way of running this application is by using Docker. A Docker image is available on [Docker Hub](https://hub.docker.com/r/remirigal/plex-auto-languages) and [installation instructions](#docker-installation) are detailed below.

PlexAutoLanguages can also be run natively with Python, see the [detailed instructions](#python-installation).


## Docker installation

### Docker compose minimal configuration

Here is a minimal example of a docker-compose configuration:
```yaml
version: "3"
services:
  plexautolanguages:
    image: remirigal/plex-auto-languages:latest
    environment:
      - PLEX_URL=http://plex:32400
      - PLEX_TOKEN=MY_PLEX_TOKEN
      - TZ=Europe/Paris
```

### Docker compose advanced configuration

Here is an example of a docker-compose configuration that uses a YAML configuration file, see [Configuration](#configuration) for more information:
```yaml
version: "3"
services:
  plexautolanguages:
    image: remirigal/plex-auto-languages:latest
    container_name: PlexAutoLanguages
    environment:
      - TZ=Europe/Paris
    volumes:
      - ./config.yaml:/config/config.yaml
    restart: unless-stopped
```


## Python installation

This application requires Python 3 and has only been tested with Python 3.8 and higher.

Start by cloning the repository:
```bash
git clone git@github.com:RemiRigal/Plex-Auto-Languages.git
```

Install the required dependencies:
```bash
cd Plex-Auto-Languages
python3 -m pip install -r requirements.txt
```

Create a YAML configuration file (`config.yaml` for example) based on the template showed in the [configuration section](#configuration) below. Note that only the parameters `plex.url` and `plex.token` are required.

You can now start PlexAutoLanguages (don't forget to change the name of the configuration file if yours is different):
```bash
python3 main.py -c ./config.yaml
```



## Configuration

The application can be configured either with environment variables or with a YAML file mounted at `/config/config.yaml`. Every parameter listed in this section can be overriden with the corresponding environment variables (eg. the environment variable `PLEX_URL` will override the parameter `plex.url`, `NOTIFICATIONS_ENABLE` will override the parameter `notifications.enable` etc...).

The Plex Token can also be provided as a Docker secret, the filepath of the secret must then be specified in the environment variable `PLEX_TOKEN_FILE` which defaults to `/run/secrets/plex_token`.

Here is an example of a complete configuration file:
```yaml
plexautolanguages:
  # Update language for the entire show or only for the current season
  # Accepted values:
  #   - show (default)
  #   - season
  update_level: "show"

  # Update all episodes of the show/season or only the next ones
  # Accepted values:
  #   - all (default)
  #   - next
  update_strategy: "all"

  # Whether or not playing a file should trigger a language update, defaults to 'true'
  trigger_on_play: true

  # Whether or not scanning the library for new files should trigger a language update, defaults to 'true'
  # A newly added episode will be updated based on the most recently watched episode, or the first episode of the show if it has never been watched
  trigger_on_scan: true

  # Whether or not navigating the Plex library should trigger a language update, defaults to 'false'
  # Only the Plex web client and the Plex for Windows app support this feature
  # Set this to 'true' only if you want to perform changes whenever the default track of an episode is updated, even when the episode is not played.
  # Setting this parameter to 'true' can result in higher resource usage.
  trigger_on_activity: false

  # Plex configuration
  plex:
    # A valid Plex URL (required)
    url: "http://plex:32400"
    # A valid Plex Token (required)
    token: "MY_PLEX_TOKEN"

  scheduler:
    # Whether of not to enable the scheduler, defaults to 'true'
    # The scheduler will perform a deeper analysis of all recently played TV Shows
    enable: true
    # The time at which the scheduler start its task with the format 'HH:MM', defaults to '02:00'
    schedule_time: "04:30"

  notifications:
    # Whether or not to enable the notifications through Apprise, defaults to 'false'
    # A notification is sent whenever a language change is performed
    enable: true
    # An array of Apprise configurations, see Apprise docs for more information: https://github.com/caronc/apprise
    # The array 'users' can be specified in order to link notification URLs with specific users
    #   Defaults to all users if not present
    # The array 'events' can be specified in order to get notifications only for specific events
    #   Valid event values: "play_or_activity" "new_episode" "updated_episode" "scheduler"
    #   Defaults to all events if not present
    apprise_configs:
      # This URL will be notified of all changes during all events
      - "discord://webhook_id/webhook_token"
      # These URLs will only be notified of language change for users "MyUser1" and "MyUser2"
      - urls:
          - "gotify://hostname/token"
          - "pover://user@token"
        users:
          - "MyUser1"
          - "MyUser2"
      # This URL will only be notified of language change for user "MyUser3" during play or activity events
      - urls:
          - "tgram://bottoken/ChatID"
        users:
          - "MyUser3"
        events:
          - "play_or_activity"
      # This URL will be notified of language change during scheduler tasks only
      - urls:
          - "gotify://hostname/token"
        events:
          - "scheduler"
      - "..."

  # Whether or not to enable the debug mode, defaults to 'false'
  # Enabling debug mode will significantly increase the number of output logs
  debug: false
```

## License

This application is licensed under the [MIT License](LICENSE).
