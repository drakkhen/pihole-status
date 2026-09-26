"""
Tests for the carousel screen and the command, against the fake Pi-hole.
"""

from pathlib import Path

import pytest
from adafruitdisplay import Display, PreviewDriver, Settings, available_screens
from PIL import Image

from pihole_status import PiholeClient, PiholeScreen, client_from_environment
from pihole_status.cli import main
from pihole_status.screen import AUTH_RETRY_SECONDS

from .fake_pihole import FakePihole


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def display(tmp_path: Path) -> Display:
    return Display(PreviewDriver(tmp_path / "frame.png"))


def test_screen_shows_queries_and_blocked(pihole: FakePihole, display: Display) -> None:
    screen = PiholeScreen(display, Settings(), PiholeClient(pihole.url))

    frame = screen.render()
    screen.close()

    assert frame.lines == ["Queries: 36,692", "Blocked: 9,013"]
    assert frame.image.getbbox() is not None


def test_unreachable_pihole(display: Display) -> None:
    screen = PiholeScreen(display, Settings(), PiholeClient("http://127.0.0.1:9", timeout=1))

    assert screen.render().lines == ["Pi-hole", "unreachable"]


def test_a_rejected_password_is_retried_after_a_pause(
    pihole: FakePihole, display: Display
) -> None:
    pihole.password = "correct horse"
    clock = Clock()
    screen = PiholeScreen(display, Settings(), PiholeClient(pihole.url, "wrong"), clock)

    assert screen.render().lines == ["Pi-hole", "bad password"]
    clock.now = AUTH_RETRY_SECONDS - 1
    assert screen.render().lines == ["Pi-hole", "bad password"]
    assert pihole.requests.count(("POST", "/api/auth")) == 1

    screen.client.password = "correct horse"
    clock.now = AUTH_RETRY_SECONDS
    assert screen.render().lines[0] == "Queries: 36,692"
    screen.close()


def test_a_missing_password(pihole: FakePihole, display: Display) -> None:
    pihole.password = "correct horse"
    screen = PiholeScreen(display, Settings(), PiholeClient(pihole.url))

    assert screen.render().lines == ["Pi-hole", "no password"]


def test_client_from_environment(tmp_path: Path) -> None:
    secret = tmp_path / "password"
    secret.write_text("from file\n")

    from_file = client_from_environment(
        {"PIHOLE_URL": "http://pi.hole/", "PIHOLE_PASSWORD_FILE": str(secret)}
    )
    from_variable = client_from_environment({"PIHOLE_PASSWORD": "from env"})

    assert from_file.url == "http://pi.hole"
    assert from_file.password_file == secret
    assert (from_variable.url, from_variable.password) == ("http://localhost", "from env")


def test_the_screen_is_registered_with_the_carousel() -> None:
    assert available_screens()["pihole"] is PiholeScreen


def test_command_previews_every_screen(
    pihole: FakePihole, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pihole.password = "correct horse"
    monkeypatch.setenv("PIHOLE_URL", pihole.url)
    monkeypatch.setenv("PIHOLE_PASSWORD", "correct horse")

    assert main(["--preview", str(tmp_path)]) == 0

    for name in ("identity", "system", "pihole", "screensaver"):
        assert Image.open(tmp_path / f"{name}.png").getbbox() is not None
    assert pihole.sessions == set()
