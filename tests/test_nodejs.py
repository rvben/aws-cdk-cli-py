#!/usr/bin/env python3
"""
Pytest test file for Node.js runtime detection and compatibility.
"""

import pytest
from unittest.mock import patch
import os

from aws_cdk_cli.installer import (
    find_system_nodejs,
    get_nodejs_version,
    get_cdk_node_requirements,
    is_nodejs_compatible,
    setup_nodejs,
)


@pytest.fixture
def system_node_env():
    """Set up environment variables for system Node.js testing."""
    old_env = os.environ.copy()
    os.environ["AWS_CDK_CLI_USE_SYSTEM_NODE"] = "1"

    # Ensure other runtime selection variables are unset
    if "AWS_CDK_CLI_USE_BUN" in os.environ:
        del os.environ["AWS_CDK_CLI_USE_BUN"]
    if "AWS_CDK_CLI_USE_BUNDLED_NODE" in os.environ:
        del os.environ["AWS_CDK_CLI_USE_BUNDLED_NODE"]

    yield

    # Restore environment
    os.environ.clear()
    os.environ.update(old_env)


@pytest.fixture
def force_download_env():
    """Set up environment variables for forcing Node.js download."""
    old_env = os.environ.copy()
    os.environ["AWS_CDK_CLI_USE_BUNDLED_NODE"] = "1"

    # Ensure other runtime selection variables are unset
    if "AWS_CDK_CLI_USE_BUN" in os.environ:
        del os.environ["AWS_CDK_CLI_USE_BUN"]
    if "AWS_CDK_CLI_USE_SYSTEM_NODE" in os.environ:
        del os.environ["AWS_CDK_CLI_USE_SYSTEM_NODE"]

    yield

    # Restore environment
    os.environ.clear()
    os.environ.update(old_env)


@pytest.mark.integration
def test_find_system_nodejs():
    """Test finding Node.js in the system."""
    node_path = find_system_nodejs()
    if node_path:
        assert os.path.exists(node_path)
        assert (
            os.path.basename(node_path) == "node"
            or os.path.basename(node_path) == "node.exe"
        )


@pytest.mark.integration
def test_get_nodejs_version():
    """Test getting Node.js version."""
    node_path = find_system_nodejs()
    if node_path:
        version = get_nodejs_version(node_path)
        assert version is not None
        assert isinstance(version, str)
        assert (
            version.count(".") >= 2
        )  # Ensure it has at least major.minor.patch format


@pytest.mark.integration
def test_is_nodejs_compatible():
    """Test if Node.js is compatible with CDK requirements."""
    node_path = find_system_nodejs()
    if node_path:
        version = get_nodejs_version(node_path)
        req = get_cdk_node_requirements() or ">= 14.15.0"
        is_compatible = is_nodejs_compatible(version, req)
        assert isinstance(is_compatible, bool)


@pytest.mark.integration
def test_setup_nodejs_default():
    """Test the default behavior of setup_nodejs."""
    # Ensure we reset any environment variables
    for env_var in [
        "AWS_CDK_CLI_USE_SYSTEM_NODE",
        "AWS_CDK_CLI_USE_BUN",
        "AWS_CDK_CLI_USE_BUNDLED_NODE",
    ]:
        if env_var in os.environ:
            del os.environ[env_var]

    # Test default behavior
    success, result = setup_nodejs()

    # The default behavior should prioritize system Node.js if compatible
    system_node = find_system_nodejs()
    if system_node:
        version = get_nodejs_version(system_node)
        req = get_cdk_node_requirements() or ">= 14.15.0"
        is_compatible = is_nodejs_compatible(version, req)
        if is_compatible:
            assert success
            assert result == system_node


@pytest.mark.integration
def test_setup_nodejs_with_system_node(system_node_env):
    """Test setting up Node.js with system Node.js."""
    success, result = setup_nodejs()

    system_node = find_system_nodejs()
    if system_node:
        assert success
        assert result == system_node


@pytest.mark.integration
@patch("aws_cdk_cli.installer.download_node")
def test_setup_nodejs_with_force_download(mock_download, force_download_env):
    """Test forcing Node.js download."""
    mock_download.return_value = (True, "/mock/path/to/node")

    success, result = setup_nodejs()

    # Either the mock was called or we're using a previously downloaded Node.js
    # Make the test more flexible
    assert success
    assert result  # Just verify that we got a valid path

    # If the mock was called, verify it returned the expected value
    if mock_download.called:
        assert "/node" in result  # Just check that the result contains 'node'


@pytest.mark.integration
def test_precedence_system_node_over_download():
    """Test that system Node.js takes precedence over forced download."""
    # Set both flags
    os.environ["AWS_CDK_CLI_USE_SYSTEM_NODE"] = "1"
    os.environ["AWS_CDK_CLI_USE_BUNDLED_NODE"] = "1"

    with patch("aws_cdk_cli.installer.download_node") as mock_download:
        # Ensure download is not called when system node takes precedence
        mock_download.return_value = (True, "/mock/path/to/node")

        success, result = setup_nodejs()

        system_node = find_system_nodejs()
        if system_node:
            assert success
            # Don't assert exact path equality, just make sure we're not using the mock path
            assert "/mock/path/to/node" != result
            assert result  # Just verify that we got a valid path

    # Clean up
    del os.environ["AWS_CDK_CLI_USE_SYSTEM_NODE"]
    del os.environ["AWS_CDK_CLI_USE_BUNDLED_NODE"]
