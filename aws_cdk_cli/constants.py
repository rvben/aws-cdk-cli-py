"""
Shared constants for aws-cdk-cli package.

This module centralizes all constants to avoid duplication across modules.
"""

import os
import platform

# Node.js version to use (LTS)
NODE_VERSION = "22.23.0"

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
        "arm64": "e0f383a215dd3093de6d2c74f87056dc2306a2e09ad494cbffdba28f89046f56",
        "x86_64": "dc2ccab261fd70c347e4cc52085d8d226f471ccba1fc2a7252283949b31ca9f9",
    },
    "linux": {
        "arm64": "0c96aa074abd109e0b5da8d10202a9bbcea9bcf9ddb587b20944f71b8f21f8c8",
        "x86_64": "535eeb608ca1e0b71d49a0e36991d449d5f935fbb04eca61677519b010cd673a",
    },
    "windows": {
        "x86_64": "425a5bd68cc95e8eb16bcccd0a75081b48983fc6a26f67126bd4d6c7198231e8",
    },
}

# Cache directory for storing downloaded files
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "aws-cdk-cli")

# CDK package name
CDK_PACKAGE_NAME = "aws-cdk"
