"""
The ``pihole`` screen for adafruitdisplay's carousel.

It reads its connection from the environment: ``PIHOLE_URL`` (default
``http://localhost``), and ``PIHOLE_PASSWORD`` or a file named by
``PIHOLE_PASSWORD_FILE``, read again before each login. On a Pi-hole v6
host, ``/etc/pihole/cli_pw`` works without an app password.
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable

from adafruitdisplay import Display, Settings, TextFrame

from .api import DEFAULT_URL, AuthenticationError, PiholeClient, PiholeError

log = logging.getLogger(__name__)

# Pi-hole rate-limits failed logins, so a rejected password is only
# retried after this long.
AUTH_RETRY_SECONDS = 300.0


class PiholeScreen:
    """
    Queries and blocked queries, in large type.
    """

    def __init__(
        self,
        display: Display,
        settings: Settings,
        client: PiholeClient | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.frame = TextFrame(display, settings.title_size, settings.title_font)
        self.min_size = settings.text_size
        self.client = client or client_from_environment()
        self.clock = clock
        self._retry_login_at = float("-inf")
        self._auth_error: str | None = None

    def render(self) -> TextFrame:
        """
        Fetch the summary and draw it, or draw what went wrong.
        """
        self.frame.clear()
        if self.clock() < self._retry_login_at:
            self._draw(["Pi-hole", self._auth_error or "login failed"])
            return self.frame
        try:
            summary = self.client.summary()
        except AuthenticationError as error:
            log.error("%s; trying again in %.0f s", error, AUTH_RETRY_SECONDS)
            self._retry_login_at = self.clock() + AUTH_RETRY_SECONDS
            self._auth_error = "bad password" if "rejected" in str(error) else "no password"
            self._draw(["Pi-hole", self._auth_error])
            return self.frame
        except PiholeError as error:
            log.warning("%s", error)
            self._draw(["Pi-hole", "unreachable"])
            return self.frame
        self._draw([f"Queries: {summary.queries:,}", f"Blocked: {summary.blocked:,}"])
        return self.frame

    def _draw(self, lines: list[str]) -> None:
        self.frame.center_lines(lines, min_size=self.min_size)

    def close(self) -> None:
        """
        Log out of Pi-hole.
        """
        self.client.close()


def client_from_environment(environ: dict[str, str] | None = None) -> PiholeClient:
    """
    Build a :class:`PiholeClient` from the ``PIHOLE_*`` variables.
    """
    env = os.environ if environ is None else environ
    url = env.get("PIHOLE_URL") or DEFAULT_URL
    if env.get("PIHOLE_PASSWORD"):
        return PiholeClient(url, env["PIHOLE_PASSWORD"])
    if env.get("PIHOLE_PASSWORD_FILE"):
        return PiholeClient(url, password_file=env["PIHOLE_PASSWORD_FILE"])
    return PiholeClient(url)
