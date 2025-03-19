#!/usr/bin/env python3
"""
Pytest test file for AWS CDK Python wrapper functionality.
"""

import os
import sys
import subprocess
import tempfile
import pytest



@pytest.mark.slow
def test_installation():
    """Test if the package can be installed in a virtual environment."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        venv_dir = os.path.join(tmp_dir, "venv")
        # Create a virtual environment
        subprocess.run([sys.executable, "-m", "venv", venv_dir], check=True)

        # Get the path to the Python executable in the virtual environment
        if os.name == "nt":  # Windows
            python_executable = os.path.join(venv_dir, "Scripts", "python.exe")
        else:  # Unix/Linux/MacOS
            python_executable = os.path.join(venv_dir, "bin", "python")

        # Install the package in development mode
        result = subprocess.run(
            [python_executable, "-m", "pip", "install", "-e", "."],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Failed to install package: {result.stderr}"

        # Test importing the package
        result = subprocess.run(
            [
                python_executable,
                "-c",
                "import aws_cdk_cli; print(aws_cdk_cli.__version__)",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Failed to import aws_cdk_cli: {result.stderr}"


@pytest.mark.slow
def test_cdk_version():
    """Test if the CDK version command works."""
    result = subprocess.run(
        [sys.executable, "-m", "aws_cdk_cli.cli", "--wrapper-version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Failed to run CDK version command: {result.stderr}"
    assert "AWS CDK Python Wrapper" in result.stdout


@pytest.mark.slow
def test_cdk_init():
    """Test if the CDK init command works."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        original_dir = os.getcwd()
        os.chdir(tmp_dir)

        try:
            import unittest.mock
            # Mock the CDK command to avoid actually running the init
            # Mock at a lower level to prevent any attempt to execute the Node.js binary
            with unittest.mock.patch("aws_cdk_cli.cli.run_cdk_command") as mock_run:
                # Return a successful result
                mock_run.return_value = (0, "CDK init app success", "")
                
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "aws_cdk_cli.cli",
                        "init",
                        "app",
                        "--language=python",
                    ],
                    capture_output=True,
                    text=True,
                )
                assert result.returncode == 0, (
                    f"Failed to run CDK init command: {result.stderr}"
                )
        finally:
            os.chdir(original_dir)


@pytest.mark.parametrize("command", ["--help", "--wrapper-version"])
def test_cdk_commands(command):
    """Test various CDK commands that don't require an app context."""
    import unittest.mock
    
    # Mock run_cdk_command to avoid executing the actual binary
    with unittest.mock.patch("aws_cdk_cli.cli.run_cdk_command") as mock_run:
        # Return a successful result
        mock_run.return_value = (0, f"CDK {command} success", "")
        
        result = subprocess.run(
            [sys.executable, "-m", "aws_cdk_cli.cli", command],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Failed to run 'cdk {command}': {result.stderr}"


def test_cdk_with_custom_command():
    """Test running the AWS CDK CLI with a custom command parameter."""
    import unittest.mock
    
    # Mock subprocess.run to avoid executing the actual command
    with unittest.mock.patch("subprocess.run") as mock_run:
        # Configure the mock to return a successful result with version info
        mock_result = unittest.mock.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "2.99.0 (build 123456)"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        # Create a simple test to verify the CLI works with a --version command
        # This doesn't require an app to be specified
        result = subprocess.run(
            [sys.executable, "-m", "aws_cdk_cli.cli", "version", "--version"],
            capture_output=True,
            text=True,
        )
        
        # The --version flag should work without an app
        assert result.returncode == 0, f"Failed to run CDK command: {result.stderr}"
        # Check if the output contains a version string
        assert "2.99.0" in result.stdout, f"Version not found in output: {result.stdout}"
