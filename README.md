# pihole-status

A Pi-hole screen for the OLED carousel in [python-adafruitdisplay][display],
for a 128x32 display such as the [Adafruit PiOLED][pioled]. The
`pihole-status` command runs the carousel with three screens: hostname and
address, host status (load, temperature, memory, disk, uptime), and Pi-hole's
query and blocked counts.

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

`PIHOLE_URL` points at another Pi-hole (default `http://localhost`), and
`PIHOLE_PASSWORD_FILE` reads the password from a file of its own. On Pi-hole
v5 use the API token instead. A rejected password shows on the screen and is
tried again every five minutes, because Pi-hole rate-limits failed logins.

## Run as a service

```sh
sudo cp contrib/pihole-status.service /etc/systemd/system/
sudo systemctl enable --now pihole-status
```

The service runs as an unprivileged user with access to I2C, and serves `/on`,
`/off` and `/` on port 5001 for switching between the screens and the screen
saver. It takes all of `oled-display`'s options; see `pihole-status --help`.

## Other carousels

Installing the package also registers the screen as `pihole`, so any
`oled-display` carousel can include it:

```sh
oled-display --screen identity --screen pihole
```

## Development

```sh
pip install -e '.[dev]'
ruff check . && ruff format --check .
pytest
```

The tests run against a fake Pi-hole web server and a preview display, so
neither a Pi-hole nor the hardware is needed.

[display]: https://github.com/drakkhen/python-adafruitdisplay
[pioled]: https://www.adafruit.com/product/3527
