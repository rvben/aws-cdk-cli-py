"""
Shared constants for aws-cdk-cli package.

This module centralizes all constants to avoid duplication across modules.
"""

import os
import platform

# Node.js version to use (LTS)
NODE_VERSION = "22.14.0"

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
        "arm64": "e9404633bc02a5162c5c573b1e2490f5fb44648345d64a958b17e325729a5e42",
        "x86_64": "6698587713ab565a94a360e091df9f6d91c8fadda6d00f0cf6526e9b40bed250",
    },
    "linux": {
        "arm64": "8cf30ff7250f9463b53c18f89c6c606dfda70378215b2c905d0a9a8b08bd45e0",
        "x86_64": "9d942932535988091034dc94cc5f42b6dc8784d6366df3a36c4c9ccb3996f0c2",
    },
    "windows": {
        "x86_64": "55b639295920b219bb2acbcfa00f90393a2789095b7323f79475c9f34795f217",
    },
}

# Cache directory for storing downloaded files
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "aws-cdk-cli")

# CDK package name
CDK_PACKAGE_NAME = "aws-cdk"
