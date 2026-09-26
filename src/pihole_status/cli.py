"""
The ``pihole-status`` command: the carousel with a Pi-hole screen.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

from adafruitdisplay.cli import main as carousel_main

DEFAULT_SCREENS = ("identity", "system", "pihole")


def main(argv: Sequence[str] | None = None) -> int:
    """
    Run ``oled-display`` with the Pi-hole screen added by default.

    Set ``PIHOLE_URL`` and ``PIHOLE_PASSWORD`` (or
    ``PIHOLE_PASSWORD_FILE``) in the environment.
    """
    return carousel_main(argv, prog="pihole-status", default_screens=DEFAULT_SCREENS)


if __name__ == "__main__":
    sys.exit(main())
