# Plex Auto Languages

[![Docker Pulls](https://img.shields.io/docker/pulls/RemiRigal/Plex-Auto-Languages?style=flat-square)](https://hub.docker.com/r/remirigal/plex-auto-languages)
[![License](https://img.shields.io/github/license/RemiRigal/Plex-Auto-Languages?style=flat-square)](https://github.com/RemiRigal/Plex-Auto-Languages/blob/master/LICENSE)

This application lets you have a Netflix-like experience by auto-updating the language of your Plex TV Show episodes based on the current language you are using without messing with your existing language preferences.  
You want to watch Squid Game in korean with english subtitles ? Set the language for the first episode and don't think about it for the rest of the show.  
You want to watch The Mandalorian in english but still want to watch Game of Thrones in french ? Don't worry, the language is set per TV Show and it won't interfere.


## Getting Started

The recommended way of running this application is by using Docker. A Docker image is available on [Docker Hub]().

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


## Configuration

The application can be configured either with environment variables or with a YAML file mounted at `/config/config.yaml`. Every parameter listed in this section can be overriden with the corresponding environment variables (eg. the environment variable `PLEX_URL` will override the parameter `plex.url`, `NOTIFICATIONS_ENABLE` will override the parameter `notifications.enable` etc...).

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

  # Whether or not navigating the Plex library should trigger a language update, defaults to 'false'
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
    # Whether of not to enable the notifications through Apprise, defaults to 'false'
    # A notification is sent whenever a language change is performed
    enable: true
    # An array of Apprise configurations, see Apprise docs for more information: https://github.com/caronc/apprise
    apprise_configs:
      - "discord://webhook_id/webhook_token"
      - "gotify://hostname/token"
      - "..."
```

## License

This application is licensed under the [MIT License](LICENSE).
