#!/usr/bin/env python3
"""
Tests for verifying that the Node.js symlink is created correctly.
"""

import os
import sys
import subprocess
import platform
import pytest
from unittest.mock import patch

from aws_cdk_cli.cli import create_node_symlink
from aws_cdk_cli.installer import setup_nodejs, find_system_nodejs
from aws_cdk_cli import NODE_BIN_PATH, is_node_installed


@pytest.fixture
def clean_symlink_env():
    """Remove any existing Node.js symlink for testing."""
    system = platform.system().lower()
    if system == "windows":
        venv_bin_dir = os.path.join(sys.prefix, "Scripts")
        node_binary = os.path.join(venv_bin_dir, "node.exe")
    else:
        venv_bin_dir = os.path.join(sys.prefix, "bin")
        node_binary = os.path.join(venv_bin_dir, "node")

    # Remove existing symlink if it exists
    if os.path.exists(node_binary):
        try:
            if system != "windows" and os.path.islink(node_binary):
                os.unlink(node_binary)
            else:
                os.remove(node_binary)
        except (OSError, PermissionError) as e:
            pytest.skip(f"Could not remove existing Node.js symlink for testing: {e}")

    # Store old environment variables
    old_env = os.environ.copy()

    # Clean environment
    for env_var in [
        "AWS_CDK_CLI_USE_SYSTEM_NODE",
        "AWS_CDK_CLI_USE_BUN",
        "AWS_CDK_CLI_USE_DOWNLOADED_NODE",
        "AWS_CDK_CLI_CREATE_NODE_SYMLINK",
    ]:
        if env_var in os.environ:
            del os.environ[env_var]

    yield

    # Restore environment
    os.environ.clear()
    os.environ.update(old_env)


@pytest.mark.integration
def test_manual_symlink_creation(clean_symlink_env):
    """Test that the create_node_symlink function works correctly."""
    # Skip the test if Node.js is not installed
    if not is_node_installed():
        pytest.skip("Node.js is not installed, skipping test")

    # Verify that we're in a virtual environment
    in_venv = hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    )
    if not in_venv:
        pytest.skip("Not in a virtual environment, skipping test")

    # Get the bin directory of the virtual environment
    system = platform.system().lower()
    if system == "windows":
        venv_bin_dir = os.path.join(sys.prefix, "Scripts")
        node_binary = os.path.join(venv_bin_dir, "node.exe")
    else:
        venv_bin_dir = os.path.join(sys.prefix, "bin")
        node_binary = os.path.join(venv_bin_dir, "node")

    # Create the symlink
    result = create_node_symlink()
    assert result is True, "create_node_symlink should return True on success"

    # Verify that the symlink was created
    assert os.path.exists(node_binary), (
        f"Node.js binary symlink was not created at {node_binary}"
    )

    # On non-Windows platforms, verify it's a symlink (on Windows it's a copy)
    if system != "windows":
        assert os.path.islink(node_binary), (
            f"Node.js binary at {node_binary} is not a symlink"
        )
        # Verify that the symlink points to the correct binary
        assert os.path.realpath(node_binary) == os.path.realpath(NODE_BIN_PATH), (
            f"Node.js symlink points to {os.path.realpath(node_binary)} instead of {os.path.realpath(NODE_BIN_PATH)}"
        )

    # Verify that the node binary is executable by running a simple command
    # On Windows, we should skip executing the binary directly
    if system != "windows":
        # Make sure the binary is executable
        os.chmod(node_binary, 0o755)

        # Try running the node binary
        try:
            result = subprocess.run(
                [node_binary, "--version"], capture_output=True, text=True, timeout=5
            )
            assert result.returncode == 0, (
                f"Node.js binary failed to run: {result.stderr}"
            )
            assert "v" in result.stdout, (
                f"Unexpected Node.js version output: {result.stdout}"
            )
            print(f"Node.js version: {result.stdout.strip()}")
        except subprocess.SubprocessError as e:
            pytest.fail(f"Failed to run node --version command: {e}")


@pytest.mark.integration
def test_cli_symlink_creation(clean_symlink_env):
    """Test that the --create-node-symlink CLI option works correctly."""
    # Skip the test if Node.js is not installed
    if not is_node_installed():
        pytest.skip("Node.js is not installed, skipping test")

    # Verify that we're in a virtual environment
    in_venv = hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    )
    if not in_venv:
        pytest.skip("Not in a virtual environment, skipping test")

    # Get the bin directory of the virtual environment
    system = platform.system().lower()
    if system == "windows":
        venv_bin_dir = os.path.join(sys.prefix, "Scripts")
        node_binary = os.path.join(venv_bin_dir, "node.exe")
    else:
        venv_bin_dir = os.path.join(sys.prefix, "bin")
        node_binary = os.path.join(venv_bin_dir, "node")

    # Run the CLI command to create the symlink
    cdk_binary = os.path.join(venv_bin_dir, "cdk")
    if system == "windows":
        cdk_binary += ".exe"

    if not os.path.exists(cdk_binary):
        pytest.skip(f"CDK binary not found at {cdk_binary}, skipping test")

    try:
        result = subprocess.run(
            [cdk_binary, "--create-node-symlink"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"CDK command failed: {result.stderr}"
        assert "Node.js symlink created successfully" in result.stdout, (
            f"Unexpected output: {result.stdout}"
        )
    except subprocess.SubprocessError as e:
        pytest.fail(f"Failed to run cdk --create-node-symlink command: {e}")

    # Verify that the symlink was created
    assert os.path.exists(node_binary), (
        f"Node.js binary symlink was not created at {node_binary}"
    )


@pytest.mark.integration
@pytest.mark.parametrize(
    "use_system_node,expect_symlink",
    [
        (True, False),  # System Node.js should not create symlink
        (
            False,
            False,
        ),  # Downloaded Node.js should also not create symlink during setup
    ],
)
def test_symlink_behavior_with_system_node(
    clean_symlink_env, use_system_node, expect_symlink
):
    """Test that symlinks are not created during setup_nodejs, only at runtime."""
    # Skip if system Node.js is requested but not available
    system_node = find_system_nodejs()
    if use_system_node and not system_node:
        pytest.skip("System Node.js requested but not available")

    # Skip if we want to test downloaded Node.js but it's not installed
    if not use_system_node and not is_node_installed():
        pytest.skip("Downloaded Node.js not installed")

    # Set the appropriate environment variable
    if use_system_node:
        os.environ["AWS_CDK_CLI_USE_SYSTEM_NODE"] = "1"
    else:
        os.environ["AWS_CDK_CLI_USE_DOWNLOADED_NODE"] = "1"

    # Run setup_nodejs which should manage the symlink
    with patch("aws_cdk_cli.cli.create_node_symlink") as mock_create_symlink:
        # Allow the real download_node to be called but mock create_node_symlink
        mock_create_symlink.return_value = True

        # Call setup_nodejs
        success, result = setup_nodejs()
        assert success, "setup_nodejs should succeed"

        if expect_symlink:
            # Should have attempted to create a symlink
            mock_create_symlink.assert_called_once()
        else:
            # Should not have attempted to create a symlink
            mock_create_symlink.assert_not_called()


@pytest.mark.integration
def test_symlink_creation_in_post_install(clean_symlink_env):
    """Test that symlinks are never created in post_install.py."""
    # Skip if downloaded Node.js is not installed
    if not is_node_installed():
        pytest.skip("Downloaded Node.js not installed")

    # Test that even with --create-node-symlink argument, post_install doesn't create a symlink
    with patch("sys.argv", ["post_install.py", "--create-node-symlink"]):
        with patch("aws_cdk_cli.post_install.is_node_installed", return_value=False):
            # Mock the download_node function to avoid actual downloads
            with patch("aws_cdk_cli.post_install.download_node", return_value=True):
                # Mock the create_node_symlink function to check if it's called
                with patch("aws_cdk_cli.cli.create_node_symlink") as mock_symlink:
                    mock_symlink.return_value = True

                    # Run the main function with symlink argument
                    from aws_cdk_cli.post_install import main

                    result = main()

                    # Should have succeeded
                    assert result == 0, "post_install.main should succeed"

                    # Should NOT have tried to create symlink (post_install never creates symlinks)
                    mock_symlink.assert_not_called()


@pytest.mark.integration
def test_explicit_symlink_request(clean_symlink_env):
    """Test that symlinks are created via CLI when explicitly requested."""
    # Set environment variables to use system Node.js
    os.environ["AWS_CDK_CLI_USE_SYSTEM_NODE"] = "1"

    # Explicitly request a symlink creation
    os.environ["AWS_CDK_CLI_CREATE_NODE_SYMLINK"] = "1"

    # Skip if system Node.js is not available
    system_node = find_system_nodejs()
    if not system_node:
        pytest.skip("System Node.js not available for testing")

    # Test with CLI module directly
    with patch("aws_cdk_cli.cli.create_node_symlink") as mock_create_symlink:
        mock_create_symlink.return_value = True

        # Simulate running a cdk command
        from aws_cdk_cli.runtime import run_cdk

        try:
            # Just run with an empty command list
            run_cdk([])
        except Exception:
            # Ignore any errors from running CDK without arguments
            pass

        # Should have attempted to create a symlink due to explicit request
        mock_create_symlink.assert_called_once()


@pytest.mark.integration
def test_env_var_overrides_system_node(clean_symlink_env):
    """Test that AWS_CDK_CLI_CREATE_NODE_SYMLINK forces symlink creation even with system Node.js."""
    # Skip if system Node.js is not available
    system_node = find_system_nodejs()
    if not system_node:
        pytest.skip("System Node.js not available for testing")

    # Use system Node.js
    os.environ["AWS_CDK_CLI_USE_SYSTEM_NODE"] = "1"

    # But force symlink creation
    os.environ["AWS_CDK_CLI_CREATE_NODE_SYMLINK"] = "1"

    # Mock create_node_symlink to check if it's called
    with patch("aws_cdk_cli.cli.create_node_symlink") as mock_create_symlink:
        mock_create_symlink.return_value = True

        # Run cdk command via runtime
        from aws_cdk_cli.runtime import run_cdk

        try:
            # Just run with a --version to get a simple response
            run_cdk(["--version"])
        except Exception:
            # Ignore any errors
            pass

        # Should have created a symlink due to explicit request via env var
        mock_create_symlink.assert_called_once()
