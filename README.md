# pihole-status

Show Pi-hole statistics on a 128x32 OLED such as the
[Adafruit PiOLED][pioled]. Every ten seconds the screen shows five seconds of
Pi-hole numbers (blocked, queries, clients), then five of host status
(address, load, temperature, memory, disk). When a query is blocked it
switches to a large counter that ticks up.

Works with Pi-hole v6 and falls back to the v5 API automatically.

## Install on the Pi

Switch on I2C first (`sudo raspi-config`, Interface Options), then:

```sh
sudo python3 -m venv /opt/pihole-status
sudo /opt/pihole-status/bin/pip install \
    'pihole-status[pi] @ git+https://github.com/drakkhen/pihole-status.git'
```

## Password

If the Pi-hole has a password, create an app password in the web interface
under Settings > Web interface / API and store it where only root can read it:

```sh
echo 'PIHOLE_PASSWORD=<app password>' | sudo tee /etc/pihole-status.env
sudo chmod 600 /etc/pihole-status.env
```

On Pi-hole v5 use the API token instead. `--password-file` reads the password
from a file of its own instead of the environment.

## Run as a service

```sh
sudo cp contrib/pihole-status.service /etc/systemd/system/
sudo systemctl enable --now pihole-status
```

The service runs as an unprivileged user with access to I2C, and the screen
blanks when it stops.

## Options

```sh
pihole-status --url http://pi.hole          # another Pi-hole (default: localhost)
pihole-status --poll 2                      # seconds between polls
pihole-status --preview screen.png --once   # draw one screen to a file, no display
pihole-status -v                            # log more detail
```

## Development

The display code lives in [python-adafruitdisplay][display].

```sh
pip install -e '.[dev]'
ruff check . && ruff format --check .
pytest
```

The tests run against a fake Pi-hole web server and a preview display, so
neither a Pi-hole nor the hardware is needed.

[pioled]: https://www.adafruit.com/product/3527
[display]: https://github.com/drakkhen/python-adafruitdisplay
