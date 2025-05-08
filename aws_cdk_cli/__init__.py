"""
AWS CDK CLI - A Python wrapper for AWS CDK CLI with smart Node.js runtime management.

This package provides a Python wrapper around the AWS CDK CLI tool (normally installed via npm),
allowing Python developers to install and use the AWS CDK via pip/uv without requiring npm.

It includes the AWS CDK JavaScript code and downloads a compatible Node.js runtime when needed,
eliminating the need for a separate npm/Node.js installation.

License:
    This package contains both:
    - AWS CDK (Apache License 2.0) - https://github.com/aws/aws-cdk
    - Node.js (MIT License) - https://github.com/nodejs/node

    All copyright notices and license texts are included in the distribution.
"""

import os
import platform
import subprocess
import json
import logging
from .version import __version__

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# Platform detection
SYSTEM = platform.system().lower()
MACHINE = platform.machine().lower()


# More robust platform detection
def detect_platform():
    """Detect the current platform and architecture more robustly."""
    system = SYSTEM
    machine = MACHINE

    # Normalize system names
    if system.startswith("darwin"):
        system = "darwin"
    elif system.startswith("linux"):
        system = "linux"
    elif system.startswith("win"):
        system = "windows"

    # Normalize machine architecture
    if machine in ("amd64", "x86_64", "x64"):
        machine = "x86_64"
    elif machine in ("arm64", "aarch64", "armv8"):
        # Important: Always use 'arm64' for consistency with Node.js distributions
        # This is a critical change to standardize on one directory name
        machine = "arm64"

        # Still store both names in environment for compatibility
        os.environ["AWS_CDK_CLI_ARM64"] = "arm64"
        os.environ["AWS_CDK_CLI_AARCH64"] = "aarch64"

    return system, machine


# Get normalized platform values
SYSTEM, MACHINE = detect_platform()

# Paths
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
NODE_MODULES_DIR = os.path.join(PACKAGE_DIR, "node_modules")
NODE_BINARIES_DIR = os.path.join(PACKAGE_DIR, "node_binaries")

# Platform-specific paths
NODE_PLATFORM_DIR = os.path.join(NODE_BINARIES_DIR, SYSTEM, MACHINE)


# Function to find the Node.js version directory
def _find_node_version_dir():
    """Find the Node.js version directory inside the platform directory."""
    if not os.path.exists(NODE_PLATFORM_DIR):
        return None

    # Look for directories that match the node-v* pattern
    for item in os.listdir(NODE_PLATFORM_DIR):
        if item.startswith("node-v") and os.path.isdir(
            os.path.join(NODE_PLATFORM_DIR, item)
        ):
            return item

    return None


# Node.js binary path
if SYSTEM == "windows":
    _NODE_VERSION_DIR = _find_node_version_dir()
    if _NODE_VERSION_DIR:
        # Windows Node.js ZIP has the executable in the root of the extracted folder
        NODE_BIN_PATH = os.path.join(NODE_PLATFORM_DIR, _NODE_VERSION_DIR, "node.exe")
    else:
        # Check both possible locations for the Windows executable
        direct_path = os.path.join(NODE_PLATFORM_DIR, "node.exe")
        if os.path.exists(direct_path):
            NODE_BIN_PATH = direct_path
        else:
            # We'll need to find the executable in extracted subdirectories
            for root, dirs, files in os.walk(NODE_PLATFORM_DIR):
                if "node.exe" in files:
                    NODE_BIN_PATH = os.path.join(root, "node.exe")
                    break
            else:
                # Fallback to the default location if not found
                NODE_BIN_PATH = os.path.join(NODE_PLATFORM_DIR, "node.exe")
else:
    _NODE_VERSION_DIR = _find_node_version_dir()
    if _NODE_VERSION_DIR:
        NODE_BIN_PATH = os.path.join(
            NODE_PLATFORM_DIR, _NODE_VERSION_DIR, "bin", "node"
        )
    else:
        NODE_BIN_PATH = os.path.join(NODE_PLATFORM_DIR, "bin", "node")

# CDK script path
if SYSTEM == "windows":
    # On Windows, the CDK script is named 'cdk.cmd'
    CDK_SCRIPT_PATH = os.path.join(NODE_MODULES_DIR, "aws-cdk", "bin", "cdk.cmd")
    # If cdk.cmd doesn't exist, fall back to 'cdk'
    if not os.path.exists(CDK_SCRIPT_PATH):
        CDK_SCRIPT_PATH = os.path.join(NODE_MODULES_DIR, "aws-cdk", "bin", "cdk")
else:
    CDK_SCRIPT_PATH = os.path.join(NODE_MODULES_DIR, "aws-cdk", "bin", "cdk")

# License paths
LICENSES = {
    "aws_cdk": os.path.join(NODE_MODULES_DIR, "aws-cdk", "LICENSE"),
    "node": os.path.join(NODE_PLATFORM_DIR, "LICENSE"),
}


def is_cdk_installed():
    """Check if AWS CDK is installed in the package directory."""
    return os.path.exists(CDK_SCRIPT_PATH)


def is_node_installed():
    """Check if Node.js is installed in the package directory."""
    global NODE_BIN_PATH  # Move global declaration to the beginning of the function

    if not os.path.exists(NODE_BIN_PATH):
        # If the path doesn't exist, let's try to find node.exe on Windows
        if SYSTEM == "windows":
            for root, dirs, files in os.walk(NODE_PLATFORM_DIR):
                if "node.exe" in files:
                    NODE_BIN_PATH = os.path.join(root, "node.exe")
                    break

    # Now check if the binary exists and is executable (file exists and has size > 0)
    return os.path.exists(NODE_BIN_PATH) and os.path.getsize(NODE_BIN_PATH) > 0


def get_cdk_version():
    """Get the installed CDK version."""
    if not is_cdk_installed():
        return None

    # Try to get version from metadata file first
    metadata_path = os.path.join(NODE_MODULES_DIR, "aws-cdk", "metadata.json")
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
                return metadata.get("cdk_version")
        except Exception:
            pass

    # Fallback to package.json
    try:
        package_json_path = os.path.join(NODE_MODULES_DIR, "aws-cdk", "package.json")
        if os.path.exists(package_json_path):
            with open(package_json_path, "r") as f:
                data = json.load(f)
                return data.get("version")
    except Exception:
        pass

    return None


def get_node_version():
    """Get the installed Node.js version."""
    if not is_node_installed():
        return None

    # Try to get version from metadata file first
    metadata_path = os.path.join(NODE_PLATFORM_DIR, "metadata.json")
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
                return metadata.get("node_version")
        except Exception:
            pass

    # Fallback to running node --version
    try:
        if os.path.exists(NODE_BIN_PATH):
            version = subprocess.check_output(
                [NODE_BIN_PATH, "--version"], text=True
            ).strip()
            # Remove the 'v' prefix if present
            if version.startswith("v"):
                version = version[1:]
            return version
    except Exception:
        pass

    return None


def get_license_text(component):
    """Get the license text for a component."""
    license_path = LICENSES.get(component)
    if license_path and os.path.exists(license_path):
        try:
            with open(license_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            pass
    return None


# Print diagnostic info in debug mode
if os.environ.get("AWS_CDK_DEBUG") == "1":
    logger.info(f"AWS CDK Python Wrapper v{__version__}")
    logger.info(f"Platform: {SYSTEM}-{MACHINE}")
    if is_node_installed():
        logger.info(f"Node.js: v{get_node_version()} installed")
    else:
        logger.info("Node.js: Not installed")

    if is_cdk_installed():
        logger.info(f"AWS CDK: v{get_cdk_version()} installed")
    else:
        logger.info("AWS CDK: Not installed")
