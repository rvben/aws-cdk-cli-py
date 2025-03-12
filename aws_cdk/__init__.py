"""
AWS CDK Python Wrapper - A Python package for AWS CDK CLI with bundled Node.js.

This package provides a Python wrapper around the AWS CDK CLI tool (normally installed via npm),
allowing Python developers to install and use the AWS CDK via pip/uv without requiring npm.

It bundles a minimal Node.js distribution and the AWS CDK JavaScript code, eliminating
the need for a separate npm/Node.js installation.

License:
    This package contains both:
    - AWS CDK (Apache License 2.0) - https://github.com/aws/aws-cdk
    - Node.js (MIT License) - https://github.com/nodejs/node
    
    All copyright notices and license texts are included in the distribution.
"""

import os
import sys
import platform
import subprocess
import json
from pathlib import Path
import logging
import importlib.resources

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Try to load version from version.py
try:
    from .version import __version__
except ImportError:
    # Try to get version from npm package
    try:
        __version__ = subprocess.check_output(
            ["npm", "view", "aws-cdk", "version"], 
            text=True
        ).strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        # Default version if npm check fails
        __version__ = "0.0.1"

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
        machine = "aarch64" if system == "linux" else "arm64"
    
    return system, machine

# Get normalized platform values
SYSTEM, MACHINE = detect_platform()

# Paths
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
NODE_MODULES_DIR = os.path.join(PACKAGE_DIR, "node_modules")
NODE_BINARIES_DIR = os.path.join(PACKAGE_DIR, "node_binaries")

# Platform-specific paths
NODE_PLATFORM_DIR = os.path.join(NODE_BINARIES_DIR, SYSTEM, MACHINE)

# Node.js binary path
if SYSTEM == "windows":
    NODE_BIN_PATH = os.path.join(NODE_PLATFORM_DIR, "node.exe")
else:
    NODE_BIN_PATH = os.path.join(NODE_PLATFORM_DIR, "bin", "node")

# CDK script path
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
    return os.path.exists(NODE_BIN_PATH)

def get_cdk_version():
    """Get the installed CDK version."""
    if not is_cdk_installed():
        return None
    
    # Try to get version from metadata file first
    metadata_path = os.path.join(NODE_MODULES_DIR, "aws-cdk", "metadata.json")
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
                return metadata.get("cdk_version")
        except Exception:
            pass
    
    # Fallback to package.json
    try:
        package_json_path = os.path.join(NODE_MODULES_DIR, "aws-cdk", "package.json")
        if os.path.exists(package_json_path):
            with open(package_json_path, 'r') as f:
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
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
                return metadata.get("node_version")
        except Exception:
            pass
    
    # Fallback to running node --version
    try:
        if os.path.exists(NODE_BIN_PATH):
            version = subprocess.check_output(
                [NODE_BIN_PATH, "--version"], 
                text=True
            ).strip()
            # Remove the 'v' prefix if present
            if version.startswith('v'):
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
            with open(license_path, 'r', encoding='utf-8') as f:
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