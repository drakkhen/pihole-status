"""
Show Pi-hole statistics on a small OLED such as the Adafruit PiOLED.
"""

from importlib.metadata import PackageNotFoundError, version

from .api import AuthenticationError, PiholeClient, PiholeError, Summary
from .app import StatusApp

try:
    __version__ = version("pihole-status")
except PackageNotFoundError:
    __version__ = "0+unknown"

__all__ = ["AuthenticationError", "PiholeClient", "PiholeError", "StatusApp", "Summary"]
