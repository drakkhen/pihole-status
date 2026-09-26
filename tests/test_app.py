"""
Display loop tests with a scripted clock and summaries.
"""

from pathlib import Path
from typing import cast

import pytest
from adafruitdisplay import Display, PreviewDriver, SystemStats

from pihole_status import AuthenticationError, PiholeClient, PiholeError, StatusApp, Summary
from pihole_status.app import FAST_TICK_SECONDS, TICK_SECONDS
from pihole_status.cli import main

from .fake_pihole import FakePihole

STATS = SystemStats("pi-hole", "10.0.0.2", 0.25, 48.0, 400 * 2**20, 1000 * 2**20, 3, 16)


class ScriptedClient:
    def __init__(self, *results: Summary | Exception) -> None:
        self.results = list(results)

    def summary(self) -> Summary:
        result = self.results.pop(0) if len(self.results) > 1 else self.results[0]
        if isinstance(result, Exception):
            raise result
        return result


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def blocked(count: int) -> Summary:
    return Summary(queries=1000, blocked=count, percent_blocked=count / 10, clients=3)


def make_app(tmp_path: Path, client: ScriptedClient, clock: Clock) -> StatusApp:
    display = Display(PreviewDriver(tmp_path / "frame.png"))
    scripted = cast(PiholeClient, client)
    return StatusApp(scripted, display, clock=clock, read_stats=lambda: STATS)


def screen(app: StatusApp) -> bytes:
    driver = app.display.driver
    assert isinstance(driver, PreviewDriver)
    return driver.frame.tobytes()


def shown(app: StatusApp) -> str:
    screen_bytes = screen(app)
    if any(screen_bytes == frame.image.tobytes() for frame in app.counter_frames):
        return "counter"
    if screen_bytes == app.system_frame.image.tobytes():
        return "system"
    return "summary"


def test_first_reading_shows_the_summary(tmp_path: Path) -> None:
    clock = Clock()
    app = make_app(tmp_path, ScriptedClient(blocked(90)), clock)

    assert app.step() == TICK_SECONDS

    assert shown(app) == "summary"
    assert app.summary_frame.lines == [
        "IP: 10.0.0.2 (pi-hole)",
        "Blocked: 90 (9.0%)",
        "Queries: 1,000",
        "Clients: 3",
    ]


def test_screens_alternate_every_five_seconds(tmp_path: Path) -> None:
    clock = Clock()
    app = make_app(tmp_path, ScriptedClient(blocked(90)), clock)

    screens = []
    for second in (0, 4.5, 5, 9.5, 10, 15):
        clock.now = second
        app.step()
        screens.append(shown(app))

    assert screens == ["summary", "summary", "system", "system", "summary", "system"]


def test_new_blocks_count_up_one_at_a_time(tmp_path: Path) -> None:
    clock = Clock()
    app = make_app(tmp_path, ScriptedClient(blocked(90), blocked(93)), clock)
    app.step()

    clock.now = 1.0
    delays = [app.step()]
    counts = [app.shown_blocked]
    for _ in range(3):
        clock.now += delays[-1]
        delays.append(app.step())
        counts.append(app.shown_blocked)

    assert counts == [91, 92, 93, 93]
    assert delays[:3] == [FAST_TICK_SECONDS, FAST_TICK_SECONDS, TICK_SECONDS]
    assert shown(app) == "summary"


@pytest.mark.parametrize(("count", "size"), [(9_014, 32), (123_456, 24), (1_234_567, 16)])
def test_counter_shrinks_to_fit(tmp_path: Path, count: int, size: int) -> None:
    clock = Clock()
    app = make_app(tmp_path, ScriptedClient(blocked(count - 1), blocked(count)), clock)
    app.step()
    clock.now = 1.0

    app.step()

    frame = next(frame for frame in app.counter_frames if frame.font_size == size)
    assert shown(app) == "counter"
    assert frame.fits(f"{count:,}")
    assert screen(app) == frame.image.tobytes()


def test_a_falling_count_jumps_instead_of_counting_down(tmp_path: Path) -> None:
    clock = Clock()
    app = make_app(tmp_path, ScriptedClient(blocked(500), blocked(2)), clock)
    app.step()

    clock.now = 1.0
    app.step()

    assert app.shown_blocked == 2
    assert shown(app) == "summary"


def test_outage_is_shown_and_recovers(tmp_path: Path) -> None:
    clock = Clock()
    down = PiholeError("can't reach Pi-hole")
    app = make_app(tmp_path, ScriptedClient(down, blocked(7)), clock)

    app.step()
    assert app.summary_frame.lines[1:] == ["Pi-hole: no data", "can't reach Pi-hole"]

    clock.now = 1.0
    app.step()
    assert app.error is None
    assert app.summary_frame.lines[1] == "Blocked: 7 (0.7%)"


def test_a_wrong_password_stops_the_loop(tmp_path: Path) -> None:
    app = make_app(tmp_path, ScriptedClient(AuthenticationError("rejected")), Clock())

    with pytest.raises(AuthenticationError):
        app.step()


def test_cli_once_against_the_fake_pihole(
    pihole: FakePihole, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pihole.password = "correct horse"
    secret = tmp_path / "password"
    secret.write_text("correct horse\n")
    monkeypatch.delenv("PIHOLE_PASSWORD", raising=False)

    status = main(
        ["--url", pihole.url, "--password-file", str(secret), "--preview",
         str(tmp_path / "out.png"), "--once"]
    )  # fmt: skip

    assert status == 0
    assert (tmp_path / "out.png").exists()
    assert pihole.sessions == set()


def test_cli_reports_a_wrong_password(
    pihole: FakePihole,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pihole.password = "correct horse"
    monkeypatch.setenv("PIHOLE_PASSWORD", "battery staple")

    status = main(["--url", pihole.url, "--preview", str(tmp_path / "out.png"), "--once"])

    assert status == 1
    assert capsys.readouterr().err == "pihole-status: Pi-hole rejected the password\n"
