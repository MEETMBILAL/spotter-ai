import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _clean(settings):
    cache.clear()
    settings.MAPBOX_SERVER_TOKEN = "test-token"
    # Set abuse guard limits high so they don't interfere with tests that
    # aren't specifically testing abuse detection.  Tests that DO test abuse
    # behaviour must override these values explicitly within the test body.
    settings.ABUSE_BURST_LIMIT = 1000
    settings.ABUSE_WINDOW_S = 1
    yield
    cache.clear()
