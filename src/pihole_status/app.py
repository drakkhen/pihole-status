"""
The display loop: Pi-hole numbers, host status, and a blocked counter.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from adafruitdisplay import (
    ON,
    Display,
    SystemStats,
    SystemStatusFrame,
    TextFrame,
    address_line,
    read_system_stats,
)

from .api import AuthenticationError, PiholeClient, PiholeError, Summary

log = logging.getLogger(__name__)

POLL_SECONDS = 1.0
TICK_SECONDS = 0.5
FAST_TICK_SECONDS = 0.1
# Each ten-second cycle shows the Pi-hole summary, then host status.
CYCLE_SECONDS = 10.0
SUMMARY_SECONDS = 5.0


class StatusApp:
    """
    Cycle the display between Pi-hole and host status.

    When the blocked count goes up, the screen switches to a large
    counter that ticks up one query at a time, faster when it's behind.
    """

    def __init__(
        self,
        client: PiholeClient,
        display: Display,
        *,
        poll_seconds: float = POLL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
        read_stats: Callable[[], SystemStats] = read_system_stats,
    ) -> None:
        self.client = client
        self.display = display
        self.poll_seconds = poll_seconds
        self.clock = clock
        self.read_stats = read_stats

        self.summary: Summary | None = None
        self.error: str | None = None
        self.shown_blocked: int | None = None
        self._next_poll = float("-inf")

        self.summary_frame = TextFrame(display)
        # Big digits when they fit, smaller as the count grows.
        self.counter_frames = [TextFrame(display, font_size=size) for size in (32, 24, 16)]
        self.system_frame = SystemStatusFrame(display)

    def run(self, sleep: Callable[[float], None] = time.sleep) -> None:
        """
        Update the display until interrupted.
        """
        while True:
            sleep(self.step())

    def step(self) -> float:
        """
        Poll if due, draw one screen, and return the seconds to wait.
        """
        now = self.clock()
        if now >= self._next_poll:
            self._poll()
            self._next_poll = now + self.poll_seconds

        if self.summary is not None and self.shown_blocked is not None:
            behind = self.summary.blocked - self.shown_blocked
            if behind > 0:
                self.shown_blocked += 1
                self._show_counter(self.shown_blocked)
                return FAST_TICK_SECONDS if behind > 1 else TICK_SECONDS

        stats = self.read_stats()
        if now % CYCLE_SECONDS < SUMMARY_SECONDS:
            self._show_summary(stats)
        else:
            self.system_frame.update(stats)
            self.display.show(self.system_frame)
        return TICK_SECONDS

    def _poll(self) -> None:
        try:
            summary = self.client.summary()
        except AuthenticationError:
            # Retrying a wrong password won't help, and Pi-hole
            # rate-limits failed logins.
            raise
        except PiholeError as error:
            if str(error) != self.error:
                log.warning("%s", error)
            self.error = str(error)
            return
        self.error = None
        self.summary = summary
        # Start from the current count, and jump rather than count down
        # when it drops (a new day on v5, the 24-hour window on v6).
        if self.shown_blocked is None or summary.blocked < self.shown_blocked:
            self.shown_blocked = summary.blocked

    def _show_counter(self, blocked: int) -> None:
        text = f"{blocked:,}"
        frame = next(
            (frame for frame in self.counter_frames if frame.fits(text)),
            self.counter_frames[-1],
        )
        frame.clear(ON)
        frame.center_text(text, fill=0)
        self.display.show(frame)

    def _show_summary(self, stats: SystemStats) -> None:
        frame = self.summary_frame
        frame.clear()
        frame.add_line(address_line(frame, stats))
        if self.summary is None:
            frame.add_line("Pi-hole: no data")
            frame.add_line(self.error or "Waiting...")
        else:
            summary = self.summary
            frame.add_line(f"Blocked: {summary.blocked:,} ({summary.percent_blocked:.1f}%)")
            frame.add_line(f"Queries: {summary.queries:,}")
            frame.add_line(f"Clients: {summary.clients}")
        self.display.show(frame)
