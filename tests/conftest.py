"""
Configuration for AWS CDK Python wrapper tests.
"""

import pytest
import sys
import os
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
        help="Run slow tests that use real CDK commands"
    )

def pytest_configure(config):
    """Configure pytest based on command line options."""
    config.addinivalue_line("markers", "slow: mark test as slow to run")

def pytest_collection_modifyitems(config, items):
    """Skip slow tests unless --slow is specified."""
    if config.getoption("--slow"):
        # --slow given in cli: do not skip slow tests
        return
    
    skip_slow = pytest.mark.skip(reason="Need --slow option to run")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow) 