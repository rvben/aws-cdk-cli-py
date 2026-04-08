"""
Shared constants for aws-cdk-cli package.

This module centralizes all constants to avoid duplication across modules.
"""

import os
import platform

# Node.js version to use (LTS)
NODE_VERSION = "22.22.2"

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
        "arm64": "db4b275b83736df67533529a18cc55de2549a8329ace6c7bcc68f8d22d3c9000",
        "x86_64": "12a6abb9c2902cf48a21120da13f87fde1ed1b71a13330712949e8db818708ba",
    },
    "linux": {
        "arm64": "b2f3a96f31486bfc365192ad65ced14833ad2a3c2e1bcefec4846902f264fa28",
        "x86_64": "978978a635eef872fa68beae09f0aad0bbbae6757e444da80b570964a97e62a3",
    },
    "windows": {
        "x86_64": "7c93e9d92bf68c07182b471aa187e35ee6cd08ef0f24ab060dfff605fcc1c57c",
    },
}

# Cache directory for storing downloaded files
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "aws-cdk-cli")

# CDK package name
CDK_PACKAGE_NAME = "aws-cdk"
