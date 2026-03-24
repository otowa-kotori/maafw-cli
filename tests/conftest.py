"""
Shared test fixtures and helpers.
"""
import sys
from pathlib import Path

# Make the tests directory importable so test files can do
# ``from mock_controller import MockController``
sys.path.insert(0, str(Path(__file__).parent))
