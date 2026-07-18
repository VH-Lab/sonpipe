"""Shared pytest fixtures: wire sonpipe up to the fake sonpy."""

import pytest

import fakesonpy
from sonpipe import sonfile


@pytest.fixture(autouse=True)
def use_fake_sonpy(request, monkeypatch):
    """Make ``SmrxFile`` (and therefore the CLI) use the fake sonpy module.

    Integration tests (marked ``integration``) are exempt: they run against the
    real CED sonpy and a real Spike2 file.
    """
    if request.node.get_closest_marker("integration"):
        yield
        return
    monkeypatch.setattr(sonfile, "load_sonpy", lambda: fakesonpy)
    yield


@pytest.fixture
def smrx_path(tmp_path):
    """A real (but empty) file on disk; content is served by the fake sonpy."""
    p = tmp_path / "example.smrx"
    p.write_bytes(b"")  # SmrxFile only checks that the path exists
    return str(p)
