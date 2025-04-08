#!/usr/bin/env python
"""Tests for AWS CDK version handling."""

import os
import sys
import subprocess
from unittest.mock import patch

import pytest


def test_version_imports():
    """Test that version attributes are properly imported."""
    from aws_cdk_cli.version import __version__, __cdk_version__, __node_version__

    # Verify that all required attributes exist
    assert __version__ is not None
    assert __cdk_version__ is not None
    assert __node_version__ is not None

    # Version should be a string in x.y.z format
    assert isinstance(__version__, str)
    assert len(__version__.split(".")) >= 3

    # CDK version should be a string in x.y.z format
    assert isinstance(__cdk_version__, str)
    assert len(__cdk_version__.split(".")) >= 3

    # Node version should be a string in x.y.z format
    assert isinstance(__node_version__, str)
    assert len(__node_version__.split(".")) >= 3


def test_version_module_format():
    """Test the format of the version module."""
    import aws_cdk_cli.version as version

    # Check that all the expected attributes are present
    assert hasattr(version, "__version__")
    assert hasattr(version, "__cdk_version__")
    assert hasattr(version, "__node_version__")
    assert hasattr(version, "__build_date__")
    assert hasattr(version, "__build_timestamp__")
    assert hasattr(version, "get_version_info")

    # Check the return value of get_version_info
    version_info = version.get_version_info()
    assert isinstance(version_info, dict)
    assert "version" in version_info
    assert "cdk_version" in version_info
    assert "node_version" in version_info
    assert "build_date" in version_info
    assert "build_timestamp" in version_info
    assert "build_commit" in version_info

    # Check that the dictionary values match the module attributes
    assert version_info["version"] == version.__version__
    assert version_info["cdk_version"] == version.__cdk_version__
    assert version_info["node_version"] == version.__node_version__


def test_get_version_info():
    """Test the get_version_info function."""
    from aws_cdk_cli.version import get_version_info

    version_info = get_version_info()
    assert isinstance(version_info, dict)
    assert "version" in version_info
    assert "cdk_version" in version_info
    assert "node_version" in version_info


def test_custom_wrapper_version():
    """Test handling of custom wrapper version different from CDK version."""
    # This test needs to be reworked to avoid sys.modules manipulation
    # which is causing issues with importlib.reload

    # Instead, we'll directly patch the CLI's show_versions function

    with patch("aws_cdk_cli.cli.__version__", "2.1007.1"):
        with patch("aws_cdk_cli.cli.get_cdk_version", return_value="2.1007.0"):
            with patch("sys.stdout") as mock_stdout:
                # Import the CLI module
                from aws_cdk_cli.cli import show_versions

                # Call show_versions
                show_versions()

                # Get all calls to write
                calls = [call[0][0] for call in mock_stdout.write.call_args_list]
                output = "".join(calls)

                # Verify both versions are in the output
                assert "AWS CDK Python Wrapper v2.1007.1" in output
                assert "AWS CDK npm package: v2.1007.0" in output


def test_import_version():
    """Test that version is correctly imported from the package."""
    from aws_cdk_cli import __version__

    assert __version__ is not None
    assert isinstance(__version__, str)
    assert len(__version__.split(".")) >= 3


@pytest.mark.parametrize(
    "cdk_version,wrapper_version,expected_pattern",
    [
        (
            "2.1007.0",
            "2.1007.0",
            r"AWS CDK Python Wrapper v2\.1007\.0\nAWS CDK:",
        ),  # Same versions
        (
            "2.1007.0",
            "2.1007.1",
            r"AWS CDK Python Wrapper v2\.1007\.1\nAWS CDK npm package: v2\.1007\.0",
        ),  # Different versions
    ],
)
def test_update_version_script(
    tmp_path, cdk_version, wrapper_version, expected_pattern
):
    """Test the update_version.py script with different version combinations."""
    # Skip test if running in a CI environment without necessary tools
    if not os.path.exists("update_version.py"):
        pytest.skip("update_version.py not found")

    # Create a temporary installer.py with NODE_VERSION
    installer_dir = tmp_path / "aws_cdk_cli"
    installer_dir.mkdir()
    with open(installer_dir / "installer.py", "w") as f:
        f.write('NODE_VERSION = "22.14.0"  # LTS version\n')

    # Set environment variables
    env = os.environ.copy()
    env["CDK_VERSION"] = cdk_version
    env["WRAPPER_VERSION"] = wrapper_version

    # Run the update_version.py script
    result = subprocess.run(
        [sys.executable, "update_version.py"],
        env=env,
        capture_output=True,
        text=True,
        cwd=os.getcwd(),
    )

    # Check exit code
    assert result.returncode == 0, f"Script failed: {result.stderr}"

    # Verify version file was created
    assert os.path.exists("aws_cdk_cli/version.py"), "Version file not created"

    # Verify version content
    with open("aws_cdk_cli/version.py", "r") as f:
        version_content = f.read()
        assert f'__cdk_version__ = "{cdk_version}"' in version_content
        assert f'__version__ = "{wrapper_version}"' in version_content
