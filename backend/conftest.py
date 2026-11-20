"""Shared pytest configuration for the backend test suite."""

import pytest

# KNOWN_STALE held tests that already failed on main when CI was repaired (#2).
# All of them were fixed or deleted in #3, so the set is empty and must stay
# empty: fix a failing test instead of adding it here.
KNOWN_STALE = set()


def pytest_collection_modifyitems(config, items):
    marker = pytest.mark.skip(reason="stale test, see homesentinel#3")
    for item in items:
        if item.nodeid in KNOWN_STALE:
            item.add_marker(marker)
