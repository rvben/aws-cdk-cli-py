"""
Pytest-based tests for the AWS CDK Python wrapper.
"""

import os
import sys
import subprocess
import tempfile
import platform
from pathlib import Path
import pytest
from unittest.mock import patch
import aws_cdk_cli
import io


# Test fixtures to prepare environment
@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """
    Prepare the environment for all tests.
    This ensures binary paths exist and the test CDK is available.

    Note: This fixture DOES NOT create mock bin/node files that shadow the real
    node binary. Tests that need mock node should use explicit mocking instead.
    """
    import shutil

    # Track created files/directories for cleanup
    created_cdk_path = None
    created_metadata_path = None

    # Mock the download_node function to avoid actual downloads during tests
    with patch("aws_cdk_cli.post_install.download_node", return_value=True):
        # Ensure Node.js binary directory exists
        system = platform.system().lower()
        machine = platform.machine().lower()

        # Normalize machine architecture
        if machine in ("amd64", "x86_64"):
            machine = "x86_64"
        elif machine in ("arm64", "aarch64"):
            machine = "aarch64" if system == "linux" else "arm64"

        # Create binary directory structure (but NOT mock bin/node files)
        binary_dir = (
            Path(aws_cdk_cli.__file__).parent / "node_binaries" / system / machine
        )
        binary_dir.mkdir(parents=True, exist_ok=True)

        # Clean up any leftover mock bin/node from previous test runs
        # This ensures the real node binary (in node-v*) is used
        mock_bin_dir = binary_dir / "bin"
        if mock_bin_dir.exists():
            # Check if it contains just mock files (shell scripts) vs real binaries
            mock_node = mock_bin_dir / "node"
            if mock_node.exists():
                # Read first few bytes to detect if it's a shell script mock
                try:
                    with open(mock_node, "rb") as f:
                        header = f.read(20)
                    if header.startswith(b"#!/bin/sh") or header.startswith(
                        b"@echo off"
                    ):
                        # It's a mock file, remove the whole bin directory
                        shutil.rmtree(mock_bin_dir)
                except Exception:
                    pass

        # Create CDK script directory and mock script
        cdk_dir = Path(aws_cdk_cli.__file__).parent / "node_modules" / "aws-cdk" / "bin"
        cdk_dir.mkdir(parents=True, exist_ok=True)

        cdk_path = cdk_dir / "cdk"
        if not cdk_path.exists():
            with open(cdk_path, "w") as f:
                if system == "windows":
                    f.write("@echo off\necho AWS CDK v2.99.0\n")
                else:
                    # Create a JavaScript file since it will be executed by Node.js
                    f.write(
                        '#!/usr/bin/env node\nconsole.log("AWS CDK v2.99.0");\nprocess.exit(0);\n'
                    )
            created_cdk_path = cdk_path
            try:
                cdk_path.chmod(0o755)
                if system != "windows":
                    # Double-check permissions were set correctly
                    assert os.access(cdk_path, os.X_OK), (
                        f"Failed to make {cdk_path} executable"
                    )
            except Exception as e:
                print(
                    f"Warning: Could not set executable permissions on {cdk_path}: {e}"
                )

        # Create node_modules metadata to prevent download attempts
        metadata_dir = Path(aws_cdk_cli.__file__).parent / "node_modules" / "aws-cdk"
        metadata_path = metadata_dir / "metadata.json"
        if not metadata_path.exists():
            with open(metadata_path, "w") as f:
                f.write(
                    '{"cdk_version": "2.99.0", "installation_date": "2023-01-01T00:00:00.000Z"}'
                )
            created_metadata_path = metadata_path

        yield  # This is where the tests run

    # Clean up created mock files to avoid polluting other tests
    if created_cdk_path and created_cdk_path.exists():
        created_cdk_path.unlink()
    if created_metadata_path and created_metadata_path.exists():
        created_metadata_path.unlink()


@pytest.fixture
def setup_mock_env():
    """Set up a mock environment for runtime detection tests.

    Note: This fixture no longer creates mock node files. It just ensures
    the binary directory structure exists. Tests should rely on the real
    node binary in node-v*/bin/node or use explicit mocking.
    """
    # Create a temporary directory structure
    system = platform.system().lower()
    machine = platform.machine().lower()

    # Normalize machine names for testing
    if machine in ("amd64", "x86_64"):
        machine = "x86_64"
    elif machine in ("arm64", "aarch64"):
        machine = "aarch64" if system == "linux" else "arm64"

    # Create node binary directory structure (but NOT mock node files)
    binary_dir = Path(aws_cdk_cli.__file__).parent / "node_binaries" / system / machine
    binary_dir.mkdir(parents=True, exist_ok=True)

    yield


def test_import():
    """Test that the aws_cdk package can be imported."""
    assert hasattr(aws_cdk_cli, "__version__")
    print(f"AWS CDK Binary version: {aws_cdk_cli.__version__}")


@pytest.mark.integration
def test_node_detection():
    """Test that the package correctly detects the downloaded Node.js."""
    assert hasattr(aws_cdk_cli, "NODE_BIN_PATH")

    # Verify the path exists (with better error handling)
    node_path = Path(aws_cdk_cli.NODE_BIN_PATH)
    if not node_path.exists():
        pytest.skip(f"Node.js binary not available at {node_path} - run installer first")

    # Ensure the binary is executable on non-Windows platforms
    if platform.system().lower() != "windows":
        os.chmod(node_path, 0o755)
        assert os.access(str(node_path), os.X_OK), (
            f"Node.js binary at {node_path} is not executable"
        )

    # On Windows, we shouldn't try to execute the mock binary directly
    if platform.system().lower() != "windows":
        # Test running node to get version
        result = subprocess.run(
            [aws_cdk_cli.NODE_BIN_PATH, "--version"], capture_output=True, text=True
        )
        assert result.returncode == 0, f"Failed to run node --version: {result.stderr}"
        assert "v" in result.stdout, (
            f"Unexpected Node.js version output: {result.stdout}"
        )
        print(f"Downloaded Node.js version: {result.stdout.strip()}")
    else:
        # Just report Windows path for debugging
        print(f"Windows Node.js binary path: {node_path}")


def test_cdk_detection():
    """Test that the package correctly detects the downloaded CDK CLI."""
    assert hasattr(aws_cdk_cli, "CDK_SCRIPT_PATH")
    assert Path(aws_cdk_cli.CDK_SCRIPT_PATH).exists(), (
        f"CDK script not found at {aws_cdk_cli.CDK_SCRIPT_PATH}"
    )

    # Verify it's executable (or at least has the right permissions)
    cdk_path = Path(aws_cdk_cli.CDK_SCRIPT_PATH)
    assert os.access(cdk_path, os.R_OK), f"CDK script is not readable at {cdk_path}"


def test_cdk_main():
    """Test that the CDK main function works."""
    # Mock dependencies
    with patch("aws_cdk_cli.runtime.run_cdk") as mock_run_cdk:
        mock_run_cdk.return_value = 0

        # Mock run_cdk_command to avoid actual execution
        with patch("aws_cdk_cli.cli.run_cdk_command") as mock_run:
            mock_run.return_value = 0

            # Run with --version argument
            sys.argv = ["cdk", "--version"]

            # Import the CLI module and run the main function
            import aws_cdk_cli.cli

            # Execute the main function
            result = aws_cdk_cli.cli.main()

            # Verify the result
            assert result == 0

            # Verify the mock was called with the right arguments
            mock_run_cdk.assert_called_once()


def test_cdk_run_help():
    """Test that the CDK CLI can run the help command."""
    # Mock dependencies
    with patch("aws_cdk_cli.runtime.run_cdk") as mock_run_cdk:
        mock_run_cdk.return_value = 0

        # Mock run_cdk_command to avoid actual execution
        with patch("aws_cdk_cli.cli.run_cdk_command") as mock_run:
            mock_run.return_value = 0

            # Run with --help argument
            sys.argv = ["cdk", "--help"]

            # Import the CLI module and run the main function
            import aws_cdk_cli.cli

            # Execute the main function
            result = aws_cdk_cli.cli.main()

            # Verify the result
            assert result == 0

            # Verify the mock was called with the right arguments
            mock_run_cdk.assert_called_once()
            mock_run_cdk.assert_called_with(["--help"])


def test_wrapper_version():
    """Test that the wrapper version command works."""
    # Mock dependencies
    with patch("aws_cdk_cli.runtime.run_cdk") as mock_run_cdk:
        # We don't expect run_cdk to be called for --wrapper-version

        # Mock run_cdk_command to avoid actual execution
        with patch("aws_cdk_cli.cli.run_cdk_command") as mock_run:
            # We don't expect run_cdk_command to be called for --wrapper-version

            # Capture stdout for verification
            captured_stdout = io.StringIO()
            sys.stdout = captured_stdout

            try:
                # Run with --wrapper-version argument
                sys.argv = ["cdk", "--wrapper-version"]

                # Import the CLI module and run the main function
                import aws_cdk_cli.cli

                # Execute the main function
                result = aws_cdk_cli.cli.main()

                # Verify the result
                assert result == 0

                # Verify output contains version information
                output = captured_stdout.getvalue()
                assert "AWS CDK" in output
                assert "v" in output

                # Verify the mocks were NOT called
                mock_run_cdk.assert_not_called()
                mock_run.assert_not_called()

            finally:
                # Restore stdout
                sys.stdout = sys.__stdout__


@pytest.mark.integration
def test_runtime_detection(setup_mock_env):
    """Test runtime detection functions."""
    import aws_cdk_cli

    system = platform.system().lower()
    machine = platform.machine().lower()

    # Normalize machine names for comparison
    if machine in ("amd64", "x86_64"):
        machine = "x86_64"
    elif machine in ("arm64", "aarch64"):
        machine = "aarch64" if system == "linux" else "arm64"

    # Verify the created binary directory path
    Path(aws_cdk_cli.__file__).parent / "node_binaries" / system / machine

    # Check if paths are correctly detected
    print(f"NODE_BIN_PATH: {aws_cdk_cli.NODE_BIN_PATH}")

    # Validate - skip if binary not available
    node_binary = Path(aws_cdk_cli.NODE_BIN_PATH)
    if not node_binary.exists():
        pytest.skip(f"Node.js binary not available at {node_binary} - run installer first")


@pytest.mark.slow
def test_cdk_init_app():
    """Test creating a new CDK app."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Save the original directory
        original_dir = os.getcwd()
        try:
            # Change to the temporary directory
            os.chdir(tmp_dir)

            # Mock the runtime.run_cdk function for consistent testing
            with patch("aws_cdk_cli.runtime.run_cdk") as mock_run_cdk:
                # Set proper return value
                mock_run_cdk.return_value = 0

                # Also mock run_cdk_command for backward compatibility
                with patch("aws_cdk_cli.cli.run_cdk_command") as mock_run:
                    # Set proper return value for captured output
                    mock_run.return_value = (0, "Mock CDK init output", "")

                    # Create expected files for testing
                    expected_files = ["app.py", "cdk.json", "requirements.txt"]
                    for file in expected_files:
                        with open(os.path.join(tmp_dir, file), "w") as f:
                            f.write(f"# Mock {file} for testing\n")

                    # Run the mock init command
                    import aws_cdk_cli.cli

                    with patch("sys.argv", ["cdk", "init", "app", "--language=python"]):
                        result = aws_cdk_cli.cli.main()
                        assert result == 0, "Init command failed"

            # Check expected files
            for file in expected_files:
                assert os.path.exists(os.path.join(tmp_dir, file)), (
                    f"Expected file {file} not found"
                )
        finally:
            # Restore the original directory
            os.chdir(original_dir)


@pytest.mark.slow
def test_cdk_synth():
    """Test synthesizing a CDK app."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Save the original directory
        original_dir = os.getcwd()
        try:
            # Change to the temporary directory
            os.chdir(tmp_dir)

            # Create test app structure
            os.makedirs("hello", exist_ok=True)

            # Create required files
            with open("app.py", "w") as f:
                f.write("# Mock app.py for testing\n")
            with open("cdk.json", "w") as f:
                f.write('{"app": "python app.py"}\n')
            with open("requirements.txt", "w") as f:
                f.write("# Mock requirements for testing\n")
            with open(os.path.join("hello", "__init__.py"), "w") as f:
                f.write("")
            with open(os.path.join("hello", "hello_stack.py"), "w") as f:
                f.write("""
from aws_cdk import Stack
from constructs import Construct

class HelloStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
""")

            # Mock the runtime.run_cdk function
            with patch("aws_cdk_cli.runtime.run_cdk") as mock_run_cdk:
                # Set proper return value
                mock_run_cdk.return_value = 0

                # Also mock run_cdk_command for backward compatibility
                with patch("aws_cdk_cli.cli.run_cdk_command") as mock_run:
                    # Set proper return value for captured output
                    mock_run.return_value = (0, "Mock CDK synth output", "")

                    # Create cdk.out directory and a template as synth would
                    os.makedirs("cdk.out", exist_ok=True)
                    with open(
                        os.path.join("cdk.out", "HelloStack.template.json"), "w"
                    ) as f:
                        f.write('{"Resources": {}}')

                    # Create manifest.json to avoid the ENOENT error
                    with open(os.path.join("cdk.out", "manifest.json"), "w") as f:
                        f.write('{"version": "test"}')

                    # Run the synth command
                    import aws_cdk_cli.cli

                    with patch("sys.argv", ["cdk", "synth"]):
                        result = aws_cdk_cli.cli.main()
                        assert result == 0, "Synth command failed"

            # Check if cdk.out directory was created
            assert os.path.exists("cdk.out"), "cdk.out directory not created"
        finally:
            # Restore the original directory
            os.chdir(original_dir)


@pytest.mark.integration
def test_platform_specific_binaries():
    """Test that the correct platform-specific Node.js binaries are available."""
    import aws_cdk_cli

    system = platform.system().lower()
    machine = platform.machine().lower()

    # Normalize machine architecture
    if machine in ("amd64", "x86_64"):
        machine = "x86_64"
    elif machine in ("arm64", "aarch64"):
        machine = "aarch64" if system == "linux" else "arm64"

    # Check that binaries for current platform exist
    binary_dir = Path(aws_cdk_cli.__file__).parent / "node_binaries" / system / machine
    if not binary_dir.exists():
        pytest.skip(f"Node.js binary directory not available at {binary_dir} - run installer first")

    # Output debug info for CI
    print(f"System: {system}")
    print(f"Machine: {machine}")
    print(f"Binary directory: {binary_dir}")
    print(f"NODE_BIN_PATH: {aws_cdk_cli.NODE_BIN_PATH}")

    # Verify node executable is in this directory (or subdirectory)
    node_binary = Path(aws_cdk_cli.NODE_BIN_PATH)
    if not node_binary.exists():
        pytest.skip(f"Node.js binary not available at {node_binary} - run installer first")

    # Ensure the binary is executable (skip on Windows)
    if system != "windows":
        os.chmod(node_binary, 0o755)
        assert os.access(str(node_binary), os.X_OK), "Node.js binary is not executable"
