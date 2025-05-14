"""Runtime utilities for aws-cdk-cli package."""

import os
import platform
import subprocess
import logging
import shutil
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("aws-cdk-runtime")

# Constants
NODE_VERSION = "22.14.0"  # LTS version
CDK_PACKAGE_NAME = "aws-cdk"

# Platform detection
SYSTEM = platform.system().lower()
MACHINE = platform.machine().lower()

# Normalize machine architecture
if MACHINE in ("amd64", "x86_64"):
    MACHINE = "x86_64"
elif MACHINE in ("arm64", "aarch64"):
    # Always use arm64 for consistency with Node.js
    MACHINE = "arm64"


def get_package_dir():
    """Get the directory where the aws-cdk-cli package is installed."""
    return os.path.dirname(os.path.abspath(__file__))


def get_node_path() -> Optional[str]:
    """
    Get the path to the node binary. This function will check for the node binary
    in the following locations:
    1. NODE_BIN_PATH environment variable
    2. NODE_PLATFORM_DIR environment variable (will append bin/node or node.exe)
    3. cdk node_modules directory (if CDK_PATH is set)
    4. System PATH

    Returns:
        The path to the node binary or None if it can't be found
    """
    node_path = os.environ.get("NODE_BIN_PATH")
    if node_path:
        if os.path.exists(node_path) and (
            SYSTEM != "unix" or os.access(node_path, os.X_OK)
        ):
            return node_path

    node_platform_dir = os.environ.get("NODE_PLATFORM_DIR")
    if node_platform_dir:
        potential_paths = []
        node_file = "node.exe" if SYSTEM == "windows" else "node"

        # Direct binary path (expected in Docker containers)
        if SYSTEM == "windows":
            direct_path = os.path.join(node_platform_dir, node_file)
        else:
            direct_path = os.path.join(node_platform_dir, "bin", node_file)

        if os.path.exists(direct_path) and (
            SYSTEM == "windows" or os.access(direct_path, os.X_OK)
        ):
            potential_paths.append(direct_path)

        # Check for node-v* directories (original node distribution structure)
        try:
            for item in os.listdir(node_platform_dir):
                if item.startswith("node-v") and os.path.isdir(
                    os.path.join(node_platform_dir, item)
                ):
                    bin_path = os.path.join(
                        node_platform_dir,
                        item,
                        "bin" if SYSTEM != "windows" else "",
                        node_file,
                    )
                    if os.path.exists(bin_path) and (
                        SYSTEM == "windows" or os.access(bin_path, os.X_OK)
                    ):
                        potential_paths.append(bin_path)
        except (FileNotFoundError, PermissionError):
            pass

        # Return the first valid binary found
        if potential_paths:
            return potential_paths[0]

        # Fallback: search recursively
        for root, dirs, files in os.walk(node_platform_dir):
            if node_file in files:
                full_path = os.path.join(root, node_file)
                if os.path.exists(full_path) and (
                    SYSTEM == "windows" or os.access(full_path, os.X_OK)
                ):
                    return full_path

    # Try to find it in the CDK path
    cdk_path = os.environ.get("CDK_PATH")
    if cdk_path:
        node_modules_path = os.path.join(cdk_path, "node_modules")
        # Try to find node in node_modules/.bin directory
        node_bin = os.path.join(node_modules_path, ".bin", "node")
        if os.path.exists(node_bin) and (
            SYSTEM != "unix" or os.access(node_bin, os.X_OK)
        ):
            return node_bin

    return None


def get_system_node_path():
    """Get the path to the system Node.js executable."""
    executable = "node.exe" if SYSTEM == "windows" else "node"
    return shutil.which(executable)


def get_cdk_path():
    """Get the path to the CDK executable."""
    package_dir = get_package_dir()
    cdk_dir = os.path.join(package_dir, "node_modules", CDK_PACKAGE_NAME)

    if not os.path.exists(cdk_dir):
        return None

    # Check for the CDK executable
    if SYSTEM == "windows":
        # On Windows, check for cdk.cmd first, then cdk
        cdk_cmd = os.path.join(cdk_dir, "bin", "cdk.cmd")
        if os.path.exists(cdk_cmd):
            return cdk_cmd

        # Also check for cdk.js and cdk in case of different packaging
        for cdk_name in ["cdk", "cdk.js"]:
            cdk_path = os.path.join(cdk_dir, "bin", cdk_name)
            if os.path.exists(cdk_path):
                return cdk_path
    else:
        # On Unix systems, check for cdk
        cdk_path = os.path.join(cdk_dir, "bin", "cdk")
        if os.path.exists(cdk_path):
            return cdk_path

    return None


def ensure_node_installed():
    """
    Ensure that Node.js is installed and available.

    This function tries to find a JavaScript runtime in the following order:
    1. System Node.js (if USE_SYSTEM_NODE is specified)
    2. Bun (if USE_BUN is specified)
    3. Downloaded Node.js (downloaded if not present)

    Environment variables that control behavior:
    - AWS_CDK_CLI_USE_SYSTEM_NODE: If set, use system Node.js rather than downloaded Node.js
    - AWS_CDK_CLI_USE_BUN: If set, use Bun runtime instead of Node.js

    Default behavior is to use system Node.js if available and compatible, then fall back to downloaded Node.js.
    """
    # We always use the installer's setup_nodejs function to handle runtime selection
    # It will prioritize system Node.js, then downloaded Node.js by default
    from .installer import setup_nodejs

    logger.debug("Setting up JavaScript runtime")
    success, result = setup_nodejs()

    if success:
        logger.debug(f"Using JavaScript runtime: {result}")
        return result
    else:
        logger.error(f"Failed to set up JavaScript runtime: {result}")
        logger.error(
            "CDK commands will not work without a compatible JavaScript runtime"
        )
        return None


def run_cdk(args):
    """Run the CDK CLI with the given arguments."""
    js_runtime_path = ensure_node_installed()
    if js_runtime_path is None:
        logger.error("Cannot run CDK command: No JavaScript runtime available.")
        return 1

    cdk_path = get_cdk_path()
    if cdk_path is None:
        logger.error("CDK CLI not found in the package.")
        return 1

    # Create symlink to Node.js:
    # 1. Always when using downloaded Node.js (not system Node.js)
    # 2. When explicitly requested via environment variable
    system_node_path = get_system_node_path()
    using_system_nodejs = system_node_path and os.path.samefile(
        js_runtime_path, system_node_path
    )
    explicitly_requested = os.environ.get("AWS_CDK_CLI_CREATE_NODE_SYMLINK") == "1"

    if (not using_system_nodejs) or explicitly_requested:
        try:
            from aws_cdk_cli.cli import create_node_symlink

            create_node_symlink()
        except ImportError:
            logger.debug("Could not create Node.js symlink: CLI module not available")
        except Exception as e:
            logger.debug(f"Failed to create Node.js symlink: {e}")

    # Prepare the command
    cmd = [js_runtime_path, cdk_path] + args

    # Create environment with suppressed Node.js version warnings
    env = os.environ.copy()

    # Check if warnings should be shown (explicit env var or CLI flag)
    show_warnings = os.environ.get("AWS_CDK_CLI_SHOW_NODE_WARNINGS") == "1"

    # By default, silence Node.js version warnings unless explicitly requested
    if not show_warnings and "JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION" not in env:
        env["JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION"] = "1"
        logger.debug("Silencing Node.js version compatibility warnings")

    # Always disable CDK version check unless user explicitly overrides
    if "CDK_DISABLE_VERSION_CHECK" not in env:
        env["CDK_DISABLE_VERSION_CHECK"] = "1"

    # Run the command
    try:
        return subprocess.call(cmd, env=env)
    except Exception as e:
        logger.error(f"Error running CDK command: {e}")
        return 1
