"""
Shared test fixtures and helpers.
"""
import sys
from pathlib import Path

import pytest

# Make the tests directory importable so test files can do
# ``from mock_controller import MockController``
sys.path.insert(0, str(Path(__file__).parent))


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Sort integration tests to run after all unit tests."""
    regular, integration = [], []
    for item in items:
        if "integration" in str(item.fspath):
            integration.append(item)
        else:
            regular.append(item)
    items[:] = regular + integration
