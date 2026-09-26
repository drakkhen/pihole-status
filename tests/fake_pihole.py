"""
A fake Pi-hole web server for the client tests.

It follows the v6 API's login rules (POST /api/auth, the X-FTL-SID
header, 401 without a valid session) and can pose as v5 instead.
"""

from __future__ import annotations

import json
import secrets
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

V6_SUMMARY = {
    "queries": {"total": 36692, "blocked": 9013, "percent_blocked": 24.563938140869141},
    "clients": {"active": 5, "total": 7},
    "gravity": {"domains_being_blocked": 450350},
}

V5_SUMMARY = {
    "dns_queries_today": 1200,
    "ads_blocked_today": 300,
    "ads_percentage_today": 25.0,
    "unique_clients": 4,
}


@dataclass
class FakePihole:
    """
    State shared with the request handler.
    """

    version: int = 6
    password: str | None = None
    v5_token: str | None = None
    summary: dict[str, Any] = field(default_factory=lambda: json.loads(json.dumps(V6_SUMMARY)))
    sessions: set[str] = field(default_factory=set)
    requests: list[tuple[str, str]] = field(default_factory=list)
    url: str = ""

    def expire_sessions(self) -> None:
        self.sessions.clear()


def serve(pihole: FakePihole) -> tuple[ThreadingHTTPServer, threading.Thread]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            pass

        def _send(self, status: int, body: object) -> None:
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _authorised(self) -> bool:
            return pihole.password is None or self.headers.get("X-FTL-SID") in pihole.sessions

        def _route(self, method: str) -> None:
            url = urlparse(self.path)
            pihole.requests.append((method, url.path))
            if pihole.version == 5:
                self._route_v5(method, url.path, parse_qs(url.query, keep_blank_values=True))
            else:
                self._route_v6(method, url.path)

        def _route_v6(self, method: str, path: str) -> None:
            if (method, path) == ("GET", "/api/stats/summary"):
                if not self._authorised():
                    self._send(401, {"error": {"key": "unauthorized"}})
                else:
                    self._send(200, pihole.summary)
            elif (method, path) == ("POST", "/api/auth"):
                length = int(self.headers.get("Content-Length", 0))
                given = json.loads(self.rfile.read(length) or b"{}").get("password")
                if pihole.password is None:
                    session = {"valid": True, "sid": None, "validity": -1}
                    self._send(200, {"session": session})
                elif given == pihole.password:
                    sid = secrets.token_urlsafe(16)
                    pihole.sessions.add(sid)
                    self._send(200, {"session": {"valid": True, "sid": sid, "validity": 1800}})
                else:
                    self._send(401, {"session": {"valid": False, "sid": None}})
            elif (method, path) == ("DELETE", "/api/auth"):
                sid = self.headers.get("X-FTL-SID")
                if sid in pihole.sessions:
                    pihole.sessions.discard(sid)
                    self._send(204, {})
                else:
                    self._send(404, {"error": {"key": "not_found"}})
            else:
                self._send(404, {"error": {"key": "not_found"}})

        def _route_v5(self, method: str, path: str, query: dict[str, list[str]]) -> None:
            if (method, path) != ("GET", "/admin/api.php") or "summaryRaw" not in query:
                self._send(404, "Not Found")
            elif pihole.v5_token and query.get("auth") != [pihole.v5_token]:
                self._send(200, [])
            else:
                self._send(200, V5_SUMMARY)

        def do_GET(self) -> None:
            self._route("GET")

        def do_POST(self) -> None:
            self._route("POST")

        def do_DELETE(self) -> None:
            self._route("DELETE")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    pihole.url = f"http://127.0.0.1:{server.server_address[1]}"
    thread = threading.Thread(target=server.serve_forever, args=(0.01,), daemon=True)
    thread.start()
    return server, thread
