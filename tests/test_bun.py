#!/usr/bin/env python3
"""
Pytest test file for Bun runtime detection and compatibility.
"""

import pytest
import os
import sys

# Use our custom semver_helper
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aws_cdk_cli import semver_helper as semver

from aws_cdk_cli.installer import (
    find_system_bun,
    get_bun_version,
    get_bun_reported_nodejs_version,
    is_bun_compatible_with_cdk,
    get_cdk_node_requirements,
    setup_nodejs,
    MIN_BUN_VERSION,
)


@pytest.fixture
def bun_env():
    """Set up environment variables for Bun testing."""
    old_env = os.environ.copy()
    os.environ["AWS_CDK_CLI_USE_BUN"] = "1"

    # Ensure other runtime selection variables are unset
    if "AWS_CDK_CLI_USE_SYSTEM_NODE" in os.environ:
        del os.environ["AWS_CDK_CLI_USE_SYSTEM_NODE"]
    if "AWS_CDK_CLI_USE_DOWNLOADED_NODE" in os.environ:
        del os.environ["AWS_CDK_CLI_USE_DOWNLOADED_NODE"]

    yield

    # Restore environment
    os.environ.clear()
    os.environ.update(old_env)


@pytest.mark.integration
def test_find_system_bun():
    """Test finding Bun in the system."""
    bun_path = find_system_bun()
    if bun_path:
        assert os.path.exists(bun_path)
        assert (
            os.path.basename(bun_path) == "bun"
            or os.path.basename(bun_path) == "bun.exe"
        )


@pytest.mark.integration
def test_get_bun_version():
    """Test getting Bun version."""
    bun_path = find_system_bun()
    if bun_path:
        version = get_bun_version(bun_path)
        assert version is not None
        assert semver.is_valid(version)


@pytest.mark.integration
def test_get_bun_reported_nodejs_version():
    """Test getting Node.js version reported by Bun."""
    bun_path = find_system_bun()
    if bun_path and bun_path is not None:
        bun_version = get_bun_version(bun_path)
        if bun_version and semver.compare(bun_version, MIN_BUN_VERSION) >= 0:
            version = get_bun_reported_nodejs_version(bun_path)
            assert version is not None
            assert semver.is_valid(version)


@pytest.mark.integration
def test_is_bun_compatible_with_cdk():
    """Test if Bun is compatible with CDK requirements."""
    bun_path = find_system_bun()
    if bun_path and bun_path is not None:
        bun_version = get_bun_version(bun_path)
        if bun_version and semver.compare(bun_version, MIN_BUN_VERSION) >= 0:
            node_req = get_cdk_node_requirements() or ">= 14.15.0"
            result = is_bun_compatible_with_cdk(bun_path, node_req)
            # Function may return either a boolean or a tuple (is_compatible, node_version)
            if isinstance(result, tuple):
                is_compatible, node_version = result
                assert isinstance(is_compatible, bool)
                assert isinstance(node_version, str)
            else:
                assert isinstance(result, bool)


@pytest.mark.integration
def test_setup_nodejs_with_bun(bun_env):
    """Test setting up Node.js with Bun as the runtime."""
    success, result = setup_nodejs()

    bun_path = find_system_bun()
    if bun_path and bun_path is not None:
        bun_version = get_bun_version(bun_path)
        if bun_version and semver.compare(bun_version, MIN_BUN_VERSION) >= 0:
            # If Bun is available and compatible, it should be used
            node_req = get_cdk_node_requirements() or ">= 14.15.0"
            is_compatible = is_bun_compatible_with_cdk(bun_path, node_req)
            if is_compatible:
                assert success
                assert result == bun_path
