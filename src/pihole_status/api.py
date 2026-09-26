"""
A small client for the Pi-hole statistics the display shows.

Pi-hole v6 serves a REST API under ``/api`` with session logins. Pi-hole
v5 served ``/admin/api.php``. :class:`PiholeClient` tries v6 first and
falls back to v5 when ``/api`` doesn't exist.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal

import requests

log = logging.getLogger(__name__)

DEFAULT_URL = "http://localhost"
DEFAULT_TIMEOUT = 5.0
SESSION_HEADER = "X-FTL-SID"


class PiholeError(Exception):
    """
    Pi-hole couldn't be reached, or answered with something unexpected.
    """


class AuthenticationError(PiholeError):
    """
    Pi-hole refused the password, or needs one and none was given.
    """


@dataclass(frozen=True, slots=True)
class Summary:
    """
    The headline numbers: queries, blocked queries and active clients.

    Pi-hole v6 counts the last 24 hours. Pi-hole v5 counted since
    midnight, so its numbers drop back to zero once a day.
    """

    queries: int
    blocked: int
    percent_blocked: float
    clients: int


class PiholeClient:
    """
    Read summary statistics from a Pi-hole, logging in when needed.

    ``password`` is the web interface password or, better, an app
    password from Settings > Web interface / API. On v5 it's the API
    token instead. Use the client as a context manager so a v6 login
    session is closed afterwards; Pi-hole allows only a few at once.
    """

    def __init__(
        self,
        url: str = DEFAULT_URL,
        password: str | None = None,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        session: requests.Session | None = None,
    ) -> None:
        self.url = url.rstrip("/")
        self.password = password
        self.timeout = timeout
        self.http = session or requests.Session()
        self.api_version: Literal[5, 6] | None = None
        self._sid: str | None = None

    def __enter__(self) -> PiholeClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def summary(self) -> Summary:
        """
        Fetch the current :class:`Summary`.

        The first successful answer settles which API the Pi-hole
        speaks. After that the client never switches, so a stray error
        from a v6 Pi-hole can't send it to the v5 API.
        """
        if self.api_version == 6:
            return self._summary_v6(self._request("GET", "/api/stats/summary"))
        if self.api_version == 5:
            return self._summary_v5(self._fetch_v5())

        # v6 answers with JSON. v5 has no /api, and its web server
        # answers unknown paths with a 404 or an HTML splash page.
        response = self._request("GET", "/api/stats/summary")
        if response.status_code != 404 and _is_json(response):
            summary = self._summary_v6(response)
            self.api_version = 6
            return summary
        data = self._fetch_v5()
        log.info("no v6 API on %s; using the Pi-hole v5 API", self.url)
        self.api_version = 5
        return self._summary_v5(data)

    def close(self) -> None:
        """
        Log out of any v6 session and close the connection.
        """
        if self._sid is not None:
            try:
                self._request("DELETE", "/api/auth")
            except PiholeError as error:
                log.warning("couldn't log out of Pi-hole: %s", error)
            self._sid = None
        self.http.close()

    def _summary_v6(self, response: requests.Response) -> Summary:
        if response.status_code == 401:
            self._log_in()
            response = self._request("GET", "/api/stats/summary")
        data = _json(response)
        try:
            queries, clients = data["queries"], data["clients"]
            return Summary(
                queries=int(queries["total"]),
                blocked=int(queries["blocked"]),
                percent_blocked=float(queries["percent_blocked"]),
                clients=int(clients["active"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise PiholeError(f"unexpected summary from Pi-hole: {data!r}") from error

    def _log_in(self) -> None:
        self._sid = None
        response = self._request("POST", "/api/auth", json={"password": self.password or ""})
        if response.status_code == 401:
            if self.password is None:
                raise AuthenticationError("Pi-hole needs a password; none was given")
            raise AuthenticationError("Pi-hole rejected the password")
        session = _json(response).get("session") or {}
        if not session.get("valid"):
            raise AuthenticationError(session.get("message") or "Pi-hole refused the login")
        # A null sid means this client doesn't need to authenticate.
        self._sid = session.get("sid")

    def _fetch_v5(self) -> Any:
        params = {"summaryRaw": ""}
        if self.password:
            params["auth"] = self.password
        return _json(self._request("GET", "/admin/api.php", params=params))

    def _summary_v5(self, data: Any) -> Summary:
        # v5 answers an unauthorised request with an empty list.
        if not isinstance(data, dict) or not data:
            raise AuthenticationError("Pi-hole v5 needs an API token for the summary")
        try:
            return Summary(
                queries=int(data["dns_queries_today"]),
                blocked=int(data["ads_blocked_today"]),
                percent_blocked=float(data["ads_percentage_today"]),
                clients=int(data["unique_clients"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise PiholeError(f"unexpected summary from Pi-hole v5: {data!r}") from error

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        headers = {SESSION_HEADER: self._sid} if self._sid else {}
        try:
            return self.http.request(
                method, self.url + path, headers=headers, timeout=self.timeout, **kwargs
            )
        except requests.RequestException as error:
            raise PiholeError(f"can't reach Pi-hole at {self.url}: {error}") from error


def _is_json(response: requests.Response) -> bool:
    try:
        response.json()
    except ValueError:
        return False
    return True


def _json(response: requests.Response) -> Any:
    if response.status_code >= 400:
        raise PiholeError(f"Pi-hole answered {response.status_code} for {response.url}")
    try:
        return response.json()
    except ValueError as error:
        raise PiholeError(f"Pi-hole sent something other than JSON from {response.url}") from error
