"""
Configuration for AWS CDK Python wrapper tests.
"""

import pytest
import sys
from pathlib import Path

# Add the project root to path if running tests directly
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def pytest_addoption(parser):
    """Add custom command line options to pytest."""
    parser.addoption(
        "--slow",
        action="store_true",
        default=False,
        help="Run slow tests that use real CDK commands",
    )
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="Run integration tests that perform real downloads and operations",
    )


def pytest_configure(config):
    """Configure pytest based on command line options."""
    config.addinivalue_line("markers", "slow: mark test as slow to run")
    config.addinivalue_line("markers", "integration: mark test as integration test")


def pytest_collection_modifyitems(config, items):
    """Skip slow and integration tests unless respective flags are specified."""
    # Handle slow tests
    if not config.getoption("--slow"):
        skip_slow = pytest.mark.skip(reason="Need --slow option to run")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)

    # Handle integration tests
    if not config.getoption("--integration"):
        skip_integration = pytest.mark.skip(reason="Need --integration option to run")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integration)
