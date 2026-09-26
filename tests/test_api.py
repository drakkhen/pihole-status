"""
Client tests against the fake Pi-hole.
"""

import pytest

from pihole_status import AuthenticationError, PiholeClient, PiholeError, Summary

from .fake_pihole import FakePihole


def test_v6_without_a_password(pihole: FakePihole) -> None:
    with PiholeClient(pihole.url) as client:
        summary = client.summary()

    assert summary == Summary(queries=36692, blocked=9013, percent_blocked=24.563938140869141,
                              clients=5)  # fmt: skip
    assert client.api_version == 6
    assert ("POST", "/api/auth") not in pihole.requests


def test_v6_logs_in_once_and_reuses_the_session(pihole: FakePihole) -> None:
    pihole.password = "correct horse"

    with PiholeClient(pihole.url, "correct horse") as client:
        client.summary()
        client.summary()
        client.summary()

    assert pihole.requests.count(("POST", "/api/auth")) == 1


def test_v6_logs_out_on_close(pihole: FakePihole) -> None:
    pihole.password = "correct horse"

    with PiholeClient(pihole.url, "correct horse") as client:
        client.summary()
        assert len(pihole.sessions) == 1

    assert pihole.sessions == set()
    assert pihole.requests[-1] == ("DELETE", "/api/auth")


def test_v6_logs_in_again_when_the_session_expires(pihole: FakePihole) -> None:
    pihole.password = "correct horse"

    with PiholeClient(pihole.url, "correct horse") as client:
        client.summary()
        pihole.expire_sessions()
        assert client.summary().blocked == 9013

    assert pihole.requests.count(("POST", "/api/auth")) == 2


def test_v6_wrong_password(pihole: FakePihole) -> None:
    pihole.password = "correct horse"

    with (
        PiholeClient(pihole.url, "battery staple") as client,
        pytest.raises(AuthenticationError, match="rejected"),
    ):
        client.summary()


def test_v6_missing_password(pihole: FakePihole) -> None:
    pihole.password = "correct horse"

    with PiholeClient(pihole.url) as client, pytest.raises(AuthenticationError, match="needs"):
        client.summary()


def test_falls_back_to_v5(pihole: FakePihole) -> None:
    pihole.version = 5

    with PiholeClient(pihole.url) as client:
        summary = client.summary()
        client.summary()

    assert summary == Summary(queries=1200, blocked=300, percent_blocked=25.0, clients=4)
    assert client.api_version == 5
    assert pihole.requests.count(("GET", "/api/stats/summary")) == 1


def test_v5_sends_the_token(pihole: FakePihole) -> None:
    pihole.version = 5
    pihole.v5_token = "abc123"

    with PiholeClient(pihole.url, "abc123") as client:
        assert client.summary().blocked == 300


def test_v5_without_the_token(pihole: FakePihole) -> None:
    pihole.version = 5
    pihole.v5_token = "abc123"

    with PiholeClient(pihole.url) as client, pytest.raises(AuthenticationError):
        client.summary()


def test_unexpected_summary(pihole: FakePihole) -> None:
    pihole.summary = {"queries": {}}

    with PiholeClient(pihole.url) as client, pytest.raises(PiholeError, match="unexpected"):
        client.summary()


def test_unreachable() -> None:
    with (
        PiholeClient("http://127.0.0.1:9", timeout=1) as client,
        pytest.raises(PiholeError, match="can't reach"),
    ):
        client.summary()
