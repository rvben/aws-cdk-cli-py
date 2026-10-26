"""
Shared constants for aws-cdk-cli package.

This module centralizes all constants to avoid duplication across modules.
"""

import os
import platform

# Node.js version to use (LTS)
NODE_VERSION = "22.23.4"

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
        "arm64": "c9e1dbc748b33ed2d14f42445191ecaf14c56259c7a9a26d0042c49ec2b66428",
        "x86_64": "efcc2b0db6f94bf53eddb038fe2b370277a042bd29e4f19b8f8e23598795b819",
    },
    "linux": {
        "arm64": "f7a1e486dbc8b286847815b477d4fb5e9fb963ed4489c3e1588853d685f589f9",
        "x86_64": "b8492284c76a54baf58d61668dd0e41ee0fc98adabf9503d30f05d08f55b4406",
    },
    "windows": {
        "x86_64": "cbc74b5e0982c9dbb41525fd8fb5dcd32fbee237863f7829072f4639a1ce5f20",
    },
}

# Cache directory for storing downloaded files
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "aws-cdk-cli")

# CDK package name
CDK_PACKAGE_NAME = "aws-cdk"
