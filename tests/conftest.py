"""
Shared fixtures.
"""

from collections.abc import Iterator

import pytest

from .fake_pihole import FakePihole, serve


@pytest.fixture
def pihole() -> Iterator[FakePihole]:
    fake = FakePihole()
    server, thread = serve(fake)
    yield fake
    server.shutdown()
    server.server_close()
    thread.join()
