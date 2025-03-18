#!/usr/bin/env python
"""
Command-line interface for AWS CDK Python wrapper with bundled Node.js.
"""

import os
import sys
import subprocess
import logging
import argparse
from . import runtime
from . import version

from aws_cdk_bin import (
    __version__,
    get_license_text,
    is_cdk_installed,
    is_node_installed,
    get_cdk_version,
    get_node_version,
    NODE_BIN_PATH,
    CDK_SCRIPT_PATH,
    SYSTEM,
    MACHINE,
)
from aws_cdk_bin.installer import install_cdk, download_node

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def run_cdk_command(args, capture_output=False, env=None):
    """
    Run a CDK command with the given arguments using bundled Node.js.

    Args:
        args: List of command-line arguments to pass to CDK.
        capture_output: Whether to capture and return the command output.
        env: Environment variables to pass to the command.

    Returns:
        The exit code from the CDK command, or a tuple of (exit_code, stdout, stderr) if capture_output is True.
    """
    # Ensure Node.js and CDK are installed
    if not is_node_installed():
        logger.info("Node.js is not installed. Installing...")
        success, error = download_node()
        if not success:
            error_msg = (
                f"Failed to install Node.js. Cannot run CDK commands. Error: {error}"
            )
            logger.error(error_msg)
            if capture_output:
                return 1, "", error_msg
            return 1

    if not is_cdk_installed():
        logger.info("AWS CDK is not installed. Installing...")
        success, error = install_cdk()
        if not success:
            error_msg = f"Failed to install AWS CDK. Error: {error}"
            logger.error(error_msg)
            if capture_output:
                return 1, "", error_msg
            return 1

    # Construct the command: node cdk.js [args]
    # The correct way to execute the CDK CLI is to run the script through Node.js
    cmd = [NODE_BIN_PATH, CDK_SCRIPT_PATH] + args

    # Set up environment variables
    if env is None:
        env = {}

    # Merge with current environment
    process_env = os.environ.copy()
    process_env.update(env)

    # Add PATH to ensure Node.js can find any needed binaries
    node_bin_dir = os.path.dirname(NODE_BIN_PATH)
    if "PATH" in process_env:
        process_env["PATH"] = node_bin_dir + os.pathsep + process_env["PATH"]
    else:
        process_env["PATH"] = node_bin_dir

    try:
        # Execute the CDK command
        if capture_output:
            process = subprocess.run(
                cmd, capture_output=True, text=True, env=process_env
            )
            return process.returncode, process.stdout, process.stderr
        else:
            # Pass through stdin/stdout/stderr
            process = subprocess.run(cmd, env=process_env)
            return process.returncode
    except subprocess.SubprocessError as e:
        error_msg = f"Error executing CDK command: {e}"
        logger.error(error_msg)
        if capture_output:
            return 1, "", error_msg
        return 1
    except FileNotFoundError:
        error_msg = "Node.js or CDK executable not found"
        logger.error(error_msg)
        if capture_output:
            return 1, "", error_msg
        return 1


def show_versions(verbose=False):
    """
    Show version information for the wrapper, CDK, and Node.js.

    Args:
        verbose: Whether to show detailed information.
    """
    # Show our wrapper version
    print(f"AWS CDK Python Wrapper v{__version__}")

    # Show bundled CDK version
    cdk_version = get_cdk_version()
    if cdk_version:
        print(f"AWS CDK: v{cdk_version}")
    else:
        print("AWS CDK: not installed")

    # Show bundled Node.js version
    node_version = get_node_version()
    if node_version:
        print(f"Node.js: v{node_version}")
    else:
        print("Node.js: not installed")

    # Platform information
    print(f"Platform: {SYSTEM}-{MACHINE}")

    if verbose:
        print("\nInstallation Paths:")
        print(f"  Node.js binary: {NODE_BIN_PATH}")
        print(f"  CDK script: {CDK_SCRIPT_PATH}")

        # Check if licenses are available
        aws_cdk_license = get_license_text("aws_cdk")
        node_license = get_license_text("node")

        if aws_cdk_license or node_license:
            print("\nLicense Information:")
            if aws_cdk_license:
                print("  AWS CDK: Apache License 2.0")
            if node_license:
                print("  Node.js: MIT License")


def main():
    """
    Main entry point for the AWS CDK CLI wrapper.

    Parses arguments and passes them to the actual CDK CLI.
    """
    # Parse the arguments
    parser = argparse.ArgumentParser(
        description="AWS CDK CLI",
        add_help=False,  # We'll pass --help to CDK CLI
    )

    # Add version argument
    parser.add_argument(
        "--wrapper-version",
        action="store_true",
        help="Print the version of the Python wrapper",
    )

    # Parse known arguments, the rest will be passed to CDK CLI
    args, remaining = parser.parse_known_args()

    # Handle --wrapper-version
    if args.wrapper_version:
        print(f"AWS CDK Python Wrapper v{version.__version__}")
        print(f"Bundled CDK v{version.__cdk_version__}")
        print(f"Bundled Node.js v{version.__node_version__}")
        return 0

    # Run the CDK CLI with the remaining arguments
    return runtime.run_cdk(remaining)


if __name__ == "__main__":
    sys.exit(main())
