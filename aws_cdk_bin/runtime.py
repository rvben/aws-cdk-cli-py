"""Runtime utilities for aws-cdk-bin package."""

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
    """Get the directory where the aws-cdk-bin package is installed."""
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
    """Ensure Node.js is installed and available."""
    node_path = get_node_path()
    if node_path is not None:
        return node_path

    # If bundled Node.js is not found, try to download it
    logger.info("Bundled Node.js not found. Attempting to download...")
    from .post_install import download_node

    if download_node():
        logger.info("Node.js downloaded successfully.")
        node_path = get_node_path()
        if node_path is not None:
            return node_path

    # If download failed or path still not found, try system Node.js
    system_node_path = get_system_node_path()
    if system_node_path is not None:
        logger.info(f"Using system Node.js: {system_node_path}")
        return system_node_path

    logger.error(
        "Node.js not found and could not be downloaded. CDK commands will not work."
    )
    return None


def run_cdk(args):
    """Run the CDK CLI with the given arguments."""
    node_path = ensure_node_installed()
    if node_path is None:
        logger.error("Cannot run CDK command: Node.js is not available.")
        return 1

    cdk_path = get_cdk_path()
    if cdk_path is None:
        logger.error("CDK CLI not found in the package.")
        return 1

    # Prepare the command
    cmd = [node_path, cdk_path] + args

    # Run the command
    try:
        return subprocess.call(cmd)
    except Exception as e:
        logger.error(f"Error running CDK command: {e}")
        return 1
