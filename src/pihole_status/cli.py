"""
The ``pihole-status`` command.
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
from collections.abc import Sequence
from pathlib import Path
from types import FrameType

from adafruitdisplay import Display, PreviewDriver

from . import __version__
from .api import DEFAULT_URL, AuthenticationError, PiholeClient
from .app import POLL_SECONDS, StatusApp

PASSWORD_VARIABLE = "PIHOLE_PASSWORD"
# EX_CONFIG from sysexits.h. The systemd unit won't restart on it, since
# retrying a wrong password only runs into Pi-hole's login rate limit.
EXIT_AUTHENTICATION = 78


def main(argv: Sequence[str] | None = None) -> int:
    """
    Run the display until interrupted, and return the exit status.
    """
    parser = argparse.ArgumentParser(
        prog="pihole-status",
        description="Show Pi-hole statistics on an SSD1306 OLED such as the Adafruit PiOLED.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--url", default=DEFAULT_URL, help="Pi-hole address (%(default)s)")
    parser.add_argument(
        "--password-file",
        type=Path,
        help=f"file holding the Pi-hole password or app password (default: ${PASSWORD_VARIABLE})",
    )
    parser.add_argument(
        "--poll", type=float, default=POLL_SECONDS, help="seconds between polls (%(default)s)"
    )
    parser.add_argument(
        "--preview", metavar="PNG", help="draw to this image file instead of the display"
    )
    parser.add_argument("--once", action="store_true", help="draw one screen and exit")
    parser.add_argument("-v", "--verbose", action="store_true", help="log more detail")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )

    password = _read_password(args.password_file)
    signal.signal(signal.SIGTERM, _raise_keyboard_interrupt)
    try:
        with (
            PiholeClient(args.url, password) as client,
            Display(PreviewDriver(args.preview)) if args.preview else Display.open() as display,
        ):
            app = StatusApp(client, display, poll_seconds=args.poll)
            if args.once:
                app.step()
                return 1 if app.error else 0
            app.run()
    except AuthenticationError as error:
        print(f"pihole-status: {error}", file=sys.stderr)
        return EXIT_AUTHENTICATION
    except KeyboardInterrupt:
        pass
    return 0


def _read_password(path: Path | None) -> str | None:
    if path is not None:
        return path.read_text().strip() or None
    return os.environ.get(PASSWORD_VARIABLE) or None


def _raise_keyboard_interrupt(signum: int, frame: FrameType | None) -> None:
    raise KeyboardInterrupt


if __name__ == "__main__":
    sys.exit(main())
