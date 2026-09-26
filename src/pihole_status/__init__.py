"""
A Pi-hole screen for adafruitdisplay's carousel, and its API client.
"""

from importlib.metadata import PackageNotFoundError, version

from .api import AuthenticationError, PiholeClient, PiholeError, Summary
from .screen import PiholeScreen, client_from_environment

try:
    __version__ = version("pihole-status")
except PackageNotFoundError:
    __version__ = "0+unknown"

__all__ = [
    "AuthenticationError",
    "PiholeClient",
    "PiholeError",
    "PiholeScreen",
    "Summary",
    "client_from_environment",
]
