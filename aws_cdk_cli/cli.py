#!/usr/bin/env python
"""
Command-line interface for AWS CDK Python wrapper with Node.js runtime support.
"""

import os
import sys
import subprocess
import logging
import argparse
from . import runtime
from . import version
import shutil
import re
from typing import List, Tuple, Optional, Union

from aws_cdk_cli import (
    __version__,
    get_license_text,
    is_node_installed,
    get_cdk_version,
    get_node_version,
    NODE_BIN_PATH,
    CDK_SCRIPT_PATH,
    SYSTEM,
    MACHINE,
)
from aws_cdk_cli.installer import setup_nodejs

# Configure logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def should_filter(line: str) -> bool:
    """Return True if the line should be filtered out (upgrade recommendation)."""
    upgrade_pattern = re.compile(r"^\*\*\*.*npm install -g aws-cdk.*\*\*\*")
    return "npm install -g aws-cdk" in line and upgrade_pattern.match(line) is not None


def run_cdk_command(
    args: List[str], capture_output: bool = False, env: Optional[dict] = None
) -> Union[int, Tuple[int, str, str]]:
    """
    Run a CDK command with the given arguments using downloaded Node.js.

    Args:
        args: List of command-line arguments to pass to CDK.
        capture_output: Whether to capture and return the command output.
        env: Environment variables to pass to the command.

    Returns:
        The exit code from the CDK command, or a tuple of (exit_code, stdout, stderr) if capture_output is True.
    """
    # Ensure Node.js and CDK are installed
    if not is_node_installed():
        logger.info("Node.js is not installed. Setting up...")
        success, result = setup_nodejs()
        if not success:
            error_msg = (
                f"Failed to set up Node.js. Cannot run CDK commands. Error: {result}"
            )
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

    # Always disable CDK version check unless user explicitly overrides
    if "CDK_DISABLE_VERSION_CHECK" not in process_env:
        process_env["CDK_DISABLE_VERSION_CHECK"] = "1"

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
            # Filter out upgrade recommendation lines using the optimized check
            filtered_stdout = [
                line for line in process.stdout.splitlines() if not should_filter(line)
            ]
            filtered_stderr = [
                line for line in process.stderr.splitlines() if not should_filter(line)
            ]
            return (
                process.returncode,
                "\n".join(filtered_stdout),
                "\n".join(filtered_stderr),
            )
        else:
            # Pass through stdin/stdout/stderr, but filter upgrade messages
            process = subprocess.run(
                cmd, capture_output=True, text=True, env=process_env
            )
            for line in process.stdout.splitlines():
                if not should_filter(line):
                    print(line)
            for line in process.stderr.splitlines():
                if not should_filter(line):
                    print(line, file=sys.stderr)
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

    # Show installed versions
    cdk_version = get_cdk_version()
    if cdk_version:
        print(f"AWS CDK npm package: v{cdk_version}")
    else:
        print("AWS CDK npm package: not installed")

    # Show Node.js version
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


def create_node_symlink():
    """
    Create a symlink to the Node.js binary in a suitable directory in the user's PATH.

    This function tries to create a symlink in the following locations, in priority order:
    1. Virtual environment bin directories
    2. Local .venv directories in current working directory
    3. User-specific directories (~/.local/bin, ~/bin)
    4. System directories (/usr/local/bin, /usr/bin) for root users
    5. Script's parent directory as fallback

    Returns:
        bool: True if symlink was created successfully, False otherwise
    """
    logger.debug("Creating Node.js symlink")

    # Find Node.js binary
    node_binary = None

    # Try to get the node path from runtime module
    try:
        node_path = runtime.get_node_path()
        if node_path and os.path.exists(node_path) and os.access(node_path, os.X_OK):
            node_binary = node_path
            logger.debug(f"Found Node.js binary via runtime: {node_binary}")
    except Exception as e:
        logger.debug(f"Error getting Node.js path from runtime: {e}")

    # Check NODE_BIN_PATH as fallback
    if (
        not node_binary
        and os.path.exists(NODE_BIN_PATH)
        and os.access(NODE_BIN_PATH, os.X_OK)
    ):
        node_binary = NODE_BIN_PATH
        logger.debug(f"Found Node.js binary via NODE_BIN_PATH: {node_binary}")

    # Check cache directory
    if not node_binary:
        logger.debug("Looking for Node.js binary in cache and other locations")
        cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "aws-cdk-cli")
        cached_binary = os.path.join(
            cache_dir, f"node-v{runtime.NODE_VERSION}", "bin", "node"
        )
        if os.path.exists(cached_binary) and os.access(cached_binary, os.X_OK):
            node_binary = cached_binary
            logger.debug(f"Found Node.js binary in cache: {node_binary}")

    # If still not found, search for it in the node_binaries directory
    if not node_binary:
        logger.debug("Searching for Node.js binary in node_binaries directory")
        node_binaries_dir = os.path.join(os.path.dirname(__file__), "node_binaries")
        node_file = "node.exe" if SYSTEM == "windows" else "node"

        # Check common paths first before walking the directory
        potential_paths = []

        # 1. Direct platform path (expected structure for Docker containers)
        platform_dir = os.path.join(node_binaries_dir, SYSTEM, MACHINE)
        if os.path.exists(platform_dir):
            # Standard path for our installation
            if SYSTEM == "windows":
                potential_paths.append(os.path.join(platform_dir, node_file))
            else:
                potential_paths.append(os.path.join(platform_dir, "bin", node_file))

            # Look for node-v* directories for original node distribution structure
            try:
                for item in os.listdir(platform_dir):
                    if item.startswith("node-v") and os.path.isdir(
                        os.path.join(platform_dir, item)
                    ):
                        if SYSTEM == "windows":
                            potential_paths.append(
                                os.path.join(platform_dir, item, node_file)
                            )
                        else:
                            potential_paths.append(
                                os.path.join(platform_dir, item, "bin", node_file)
                            )
            except (FileNotFoundError, PermissionError) as e:
                logger.debug(f"Error listing platform directory: {e}")

        # Check all potential paths first
        for potential_path in potential_paths:
            if os.path.exists(potential_path) and (
                SYSTEM == "windows" or os.access(potential_path, os.X_OK)
            ):
                node_binary = potential_path
                logger.debug(f"Found Node.js binary at predefined path: {node_binary}")
                break

        # If still not found, do the recursive search as a last resort
        if not node_binary:
            for root, dirs, files in os.walk(node_binaries_dir):
                if node_file in files:
                    potential_node = os.path.join(root, node_file)
                    if SYSTEM == "windows" or os.access(potential_node, os.X_OK):
                        node_binary = potential_node
                        logger.debug(
                            f"Found Node.js binary via recursive search: {node_binary}"
                        )
                        break

    # Check if we found a valid Node.js binary
    if not node_binary:
        logger.error("Could not find Node.js binary")
        return False

    # Determine potential bin directories in priority order
    bin_dirs = []

    # 1. Virtual environment bin directory
    if hasattr(sys, "prefix") and sys.prefix != sys.base_prefix:
        if SYSTEM == "windows":
            venv_bin_dir = os.path.join(sys.prefix, "Scripts")
        else:
            venv_bin_dir = os.path.join(sys.prefix, "bin")

        if os.path.exists(venv_bin_dir):
            bin_dirs.append(venv_bin_dir)
            logger.debug(f"Found virtual environment bin directory: {venv_bin_dir}")

    # 2. Look for .venv directory in current working directory
    local_venv_bin = os.path.join(
        os.getcwd(), ".venv", "bin" if SYSTEM != "windows" else "Scripts"
    )
    if os.path.exists(local_venv_bin):
        bin_dirs.append(local_venv_bin)
        logger.debug(f"Found local .venv bin directory: {local_venv_bin}")

    # 3. User-specific directories
    home_dir = os.path.expanduser("~")
    user_bin_dirs = []

    if SYSTEM != "windows":
        user_bin_dirs = [
            os.path.join(home_dir, ".local", "bin"),
            os.path.join(home_dir, "bin"),
            os.path.join(home_dir, ".bin"),
        ]
    else:
        # Windows user directories
        user_bin_dirs = [
            os.path.join(home_dir, "AppData", "Local", "Programs", "Python", "Scripts"),
            os.path.join(home_dir, "AppData", "Roaming", "Python", "Scripts"),
        ]

    for user_bin in user_bin_dirs:
        if os.path.exists(user_bin) and os.access(user_bin, os.W_OK):
            bin_dirs.append(user_bin)
            logger.debug(f"Found user bin directory: {user_bin}")
        elif not os.path.exists(user_bin):
            try:
                os.makedirs(user_bin, exist_ok=True)
                bin_dirs.append(user_bin)
                logger.debug(f"Created user bin directory: {user_bin}")
            except (OSError, PermissionError) as e:
                logger.debug(f"Could not create user bin directory {user_bin}: {e}")

    # 4. Check for root user and add system directories
    is_root = os.geteuid() == 0 if hasattr(os, "geteuid") else False
    if is_root:
        logger.debug("Running as root user, checking system bin directories")
        for system_bin in ["/usr/local/bin", "/usr/bin"]:
            if os.path.exists(system_bin) and os.access(system_bin, os.W_OK):
                bin_dirs.append(system_bin)
                logger.debug(f"Found writable system bin directory: {system_bin}")

    # 5. Script directory as last resort
    script_dir = os.path.dirname(os.path.abspath(__file__))
    bin_dirs.append(script_dir)
    logger.debug(f"Added script directory as fallback: {script_dir}")

    # Try each bin directory in order
    for bin_dir in bin_dirs:
        # Determine target path
        target_path = os.path.join(
            bin_dir, "node.exe" if SYSTEM == "windows" else "node"
        )
        logger.debug(f"Attempting to create symlink at: {target_path}")

        try:
            # Remove existing symlink if it exists
            if os.path.exists(target_path):
                if SYSTEM != "windows" and os.path.islink(target_path):
                    os.unlink(target_path)
                else:
                    os.remove(target_path)
                logger.debug(f"Removed existing node binary at {target_path}")

            # Create symlink or copy the binary
            if SYSTEM == "windows":
                # Windows: copy the binary instead of symlink
                shutil.copy2(node_binary, target_path)
                logger.debug(f"Copied Node.js binary to {target_path}")
            else:
                # Unix: create a symlink
                os.symlink(node_binary, target_path)
                # Set executable permissions
                os.chmod(target_path, 0o755)
                logger.debug(f"Created symlink from {node_binary} to {target_path}")

            # Verify that the binary exists and is executable
            if os.path.exists(target_path) and (
                SYSTEM == "windows" or os.access(target_path, os.X_OK)
            ):
                logger.info(f"Node.js symlink created at {target_path}")
                return True
        except (OSError, PermissionError, shutil.Error) as e:
            logger.debug(f"Failed to create Node.js symlink in {bin_dir}: {e}")
            continue  # Try the next directory

    logger.error("Failed to create Node.js symlink in any directory")
    return False


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

    # Add JavaScript runtime control arguments
    runtime_control = parser.add_argument_group("JavaScript Runtime Options")
    runtime_control.add_argument(
        "--use-system-node",
        action="store_true",
        help="Use system Node.js installation if available and compatible",
    )
    runtime_control.add_argument(
        "--use-bun",
        action="store_true",
        help="Use Bun as the JavaScript runtime (requires Bun v1.1.0+)",
    )
    runtime_control.add_argument(
        "--use-downloaded-node",
        action="store_true",
        help="Use the downloaded Node.js instead of system Node.js",
    )
    runtime_control.add_argument(
        "--show-node-warnings",
        action="store_true",
        help="Show Node.js version compatibility warnings (hidden by default)",
    )
    runtime_control.add_argument(
        "--create-node-symlink",
        action="store_true",
        help="Create a symlink to the Node.js binary in a suitable directory",
    )

    # Add verbose mode
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show verbose output",
    )

    # Parse known arguments, the rest will be passed to CDK CLI
    args, remaining = parser.parse_known_args()

    # Setup logging level
    if args.verbose:
        logging.root.setLevel(logging.DEBUG)
        logging.getLogger("aws_cdk_cli").setLevel(logging.DEBUG)
    else:
        # When not in verbose mode, set to WARNING level to hide runtime selection messages
        logging.root.setLevel(logging.WARNING)
        logging.getLogger("aws_cdk_cli").setLevel(logging.WARNING)

    # Handle --wrapper-version
    if args.wrapper_version:
        print(f"AWS CDK Python Wrapper v{version.__version__}")
        print(f"Downloaded CDK v{version.__cdk_version__}")
        print(f"Downloaded Node.js v{version.__node_version__}")
        return 0

    # If runtime control options are provided, set them as environment vars
    # so they can be passed to the installer/runtime modules
    if args.use_system_node:
        os.environ["AWS_CDK_CLI_USE_SYSTEM_NODE"] = "1"
        logger.debug("Using system Node.js if available")

    if args.use_bun:
        os.environ["AWS_CDK_CLI_USE_BUN"] = "1"
        logger.debug("Using Bun as JavaScript runtime if available")

    if args.use_downloaded_node:
        os.environ["AWS_CDK_CLI_USE_DOWNLOADED_NODE"] = "1"
        logger.debug("Using downloaded Node.js")

    if args.show_node_warnings:
        os.environ["AWS_CDK_CLI_SHOW_NODE_WARNINGS"] = "1"
        logger.debug("Showing Node.js version compatibility warnings")

    # Handle explicit Node.js symlink creation
    if (
        args.create_node_symlink
        or os.environ.get("AWS_CDK_CLI_CREATE_NODE_SYMLINK") == "1"
    ):
        if create_node_symlink():
            print("Node.js symlink created successfully")
        else:
            print("Failed to create Node.js symlink")
            return 1

        # If only creating symlink, return here
        if args.create_node_symlink and len(remaining) == 0:
            return 0

    # Check for incompatible combinations
    if args.use_system_node and args.use_downloaded_node:
        logger.warning(
            "Both --use-system-node and --use-downloaded-node specified. Using system Node.js takes precedence."
        )

    if args.use_bun and args.use_downloaded_node:
        logger.warning(
            "Both --use-bun and --use-downloaded-node specified. Bun will be tried first."
        )

    if args.use_bun and args.use_system_node:
        logger.warning(
            "Both --use-bun and --use-system-node specified. Bun will be tried first."
        )

    # Run the CDK CLI with the remaining arguments
    return runtime.run_cdk(remaining)


if __name__ == "__main__":
    sys.exit(main())
