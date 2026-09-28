"""
Shared constants for aws-cdk-cli package.

This module centralizes all constants to avoid duplication across modules.
"""

import os
import platform

# Node.js version to use (LTS)
NODE_VERSION = "22.23.3"

# Minimum Bun version required for --eval support
MIN_BUN_VERSION = "1.1.0"

# Platform detection
SYSTEM = platform.system().lower()
MACHINE = platform.machine().lower()

# Normalize machine architecture
if MACHINE in ("amd64", "x86_64"):
    MACHINE = "x86_64"
elif MACHINE in ("arm64", "aarch64"):
    # Always use arm64 for consistency with Node.js
    MACHINE = "arm64"


def get_node_urls(node_version: str = NODE_VERSION) -> dict:
    """
    Get Node.js download URLs for all platforms.

    Args:
        node_version: The Node.js version to use in URLs

    Returns:
        Dictionary mapping system -> machine -> URL
    """
    return {
        "darwin": {
            "x86_64": f"https://nodejs.org/dist/v{node_version}/node-v{node_version}-darwin-x64.tar.gz",
            "arm64": f"https://nodejs.org/dist/v{node_version}/node-v{node_version}-darwin-arm64.tar.gz",
        },
        "linux": {
            "x86_64": f"https://nodejs.org/dist/v{node_version}/node-v{node_version}-linux-x64.tar.gz",
            "arm64": f"https://nodejs.org/dist/v{node_version}/node-v{node_version}-linux-arm64.tar.gz",
        },
        "windows": {
            "x86_64": f"https://nodejs.org/dist/v{node_version}/node-v{node_version}-win-x64.zip",
        },
    }


# Pre-computed URLs for the default version
NODE_URLS = get_node_urls()

# Known checksums for Node.js binaries - for verification
# These must be updated when NODE_VERSION changes
NODE_CHECKSUMS = {
    "darwin": {
        "arm64": "23b25245dcfb9af7262f8ff142e9e2e0af025368117329e7a7458a51e5922f53",
        "x86_64": "8a677b0219178efd6eb0e475457c4afb452b521a92f6e67845a73bd85727f2a8",
    },
    "linux": {
        "arm64": "5ced2d48d1d7198739b7f86804de0171aefb6823b684b12341d3321afc3cb0b2",
        "x86_64": "1084aa36196bba4c3a5e69a1ee388a6e4ff729dad09445fbcd434b28fe3c24af",
    },
    "windows": {
        "x86_64": "2b0ff57b049cda1bbcea2240eec20467018713c1efe1f7360c2681859b90ed71",
    },
}

# Cache directory for storing downloaded files
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "aws-cdk-cli")

# CDK package name
CDK_PACKAGE_NAME = "aws-cdk"
