"""Runtime utilities for aws-cdk-cli package."""

import os
import platform
import subprocess
import logging
import shutil

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("aws-cdk-runtime")

# Constants
NODE_VERSION = "18.16.0"  # LTS version
CDK_PACKAGE_NAME = "aws-cdk"

# Platform detection
SYSTEM = platform.system().lower()
MACHINE = platform.machine().lower()

# Normalize machine architecture
if MACHINE in ("amd64", "x86_64"):
    MACHINE = "x86_64"
elif MACHINE in ("arm64", "aarch64"):
    MACHINE = "aarch64" if SYSTEM == "linux" else "arm64"


def get_package_dir():
    """Get the directory where the aws-cdk-cli package is installed."""
    return os.path.dirname(os.path.abspath(__file__))


def get_node_path():
    """Get the path to the bundled Node.js executable."""
    package_dir = get_package_dir()
    node_binaries_dir = os.path.join(package_dir, "node_binaries", SYSTEM, MACHINE)

    # Find the Node.js directory
    if not os.path.exists(node_binaries_dir):
        return None

    # Look for node-vX.Y.Z directories
    for item in os.listdir(node_binaries_dir):
        if item.startswith("node-v") and os.path.isdir(
            os.path.join(node_binaries_dir, item)
        ):
            # We found a Node.js version directory
            if SYSTEM == "windows":
                # On Windows, node.exe is in the root of the extracted directory
                node_exe = os.path.join(node_binaries_dir, item, "node.exe")
                if os.path.exists(node_exe):
                    return node_exe
            else:
                # On Unix systems, node is in the bin subdirectory
                node_bin = os.path.join(node_binaries_dir, item, "bin", "node")
                if os.path.exists(node_bin):
                    return node_bin

    # If we couldn't find a version directory, check for the binary directly
    if SYSTEM == "windows":
        node_exe = os.path.join(node_binaries_dir, "node.exe")
        if os.path.exists(node_exe):
            return node_exe

        # As a last resort, search for node.exe in the directory tree
        for root, dirs, files in os.walk(node_binaries_dir):
            if "node.exe" in files:
                return os.path.join(root, "node.exe")
    else:
        node_bin = os.path.join(node_binaries_dir, "bin", "node")
        if os.path.exists(node_bin):
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
    Ensure that a suitable JavaScript runtime (Node.js or Bun) is installed and available.

    Returns the path to the JavaScript runtime if available, or None if not.

    Environment variables:
    - AWS_CDK_CLI_USE_SYSTEM_NODE: If set, prefer using system Node.js
    - AWS_CDK_CLI_USE_BUN: If set, try to use Bun as the JavaScript runtime
    - AWS_CDK_CLI_USE_BUNDLED_NODE: If set, use bundled Node.js rather than system Node.js

    Default behavior is to use system Node.js if available and compatible, then fall back to bundled Node.js.
    """
    # We always use the installer's setup_nodejs function to handle runtime selection
    # It will prioritize system Node.js, then bundled Node.js by default
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

    # Run the command
    try:
        return subprocess.call(cmd, env=env)
    except Exception as e:
        logger.error(f"Error running CDK command: {e}")
        return 1
