"""Runtime utilities for aws-cdk package."""

import os
import sys
import platform
import subprocess
import logging
import shutil
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('aws-cdk-runtime')

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
    """Get the directory where the aws-cdk package is installed."""
    return os.path.dirname(os.path.abspath(__file__))

def get_node_path():
    """Get the path to the bundled Node.js executable."""
    package_dir = get_package_dir()
    node_binaries_dir = os.path.join(package_dir, "node_binaries", SYSTEM, MACHINE)
    
    # Find the Node.js directory
    if not os.path.exists(node_binaries_dir):
        return None
    
    node_dirs = [d for d in os.listdir(node_binaries_dir) if d.startswith("node-")]
    if not node_dirs:
        return None
    
    node_dir = node_dirs[0]  # Take the first Node.js directory
    
    # Determine the path to the node executable
    if SYSTEM == "windows":
        node_path = os.path.join(node_binaries_dir, node_dir, "node.exe")
    else:
        node_path = os.path.join(node_binaries_dir, node_dir, "bin", "node")
    
    return node_path if os.path.exists(node_path) else None

def get_system_node_path():
    """Get the path to the system Node.js executable."""
    executable = "node.exe" if SYSTEM == "windows" else "node"
    return shutil.which(executable)

def get_cdk_path():
    """Get the path to the bundled CDK CLI executable."""
    package_dir = get_package_dir()
    node_modules_dir = os.path.join(package_dir, "node_modules")
    
    # Determine the path to the CDK CLI executable
    if SYSTEM == "windows":
        cdk_path = os.path.join(node_modules_dir, CDK_PACKAGE_NAME, "bin", "cdk.js")
    else:
        cdk_path = os.path.join(node_modules_dir, CDK_PACKAGE_NAME, "bin", "cdk")
    
    return cdk_path if os.path.exists(cdk_path) else None

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
    
    logger.error("Node.js not found and could not be downloaded. CDK commands will not work.")
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