#!/usr/bin/env python3
"""
Update the version.py file with the provided CDK version.
This script is used during the build process to ensure the Python package
version matches the CDK version it wraps.
"""

import os
import sys
import re
import datetime


def validate_version(version: str, name: str) -> None:
    """Validate version string as x.y.z or x.y.z.n; exit on failure."""
    pattern = r"^\d+\.\d+\.\d+(?:\.\d+)?$"
    example = "x.y.z or x.y.z.n"
    if not re.match(pattern, version):
        print(f"Error: Invalid {name} format: {version}")
        print(f"{name.capitalize()} must be in the format {example}")
        sys.exit(1)


# Get the CDK version from the command-line argument or environment variable
cdk_version = None

# First try command line argument
if len(sys.argv) > 1:
    cdk_version = sys.argv[1]
    print(f"Using CDK version from command line: {cdk_version}")

# Then try environment variable
if not cdk_version and "CDK_VERSION" in os.environ:
    cdk_version = os.environ["CDK_VERSION"]
    print(f"Using CDK version from CDK_VERSION environment variable: {cdk_version}")

# Make sure we have a CDK version
if not cdk_version:
    print("Error: No CDK version specified")
    print("Usage: python update_version.py <cdk_version>")
    print("   or: export CDK_VERSION=<cdk_version> && python update_version.py")
    sys.exit(1)

# Strip leading 'v' if present
if cdk_version.startswith("v"):
    cdk_version = cdk_version[1:]

validate_version(cdk_version, "CDK version")

# Get the wrapper version - either from environment variable or use CDK version
wrapper_version = os.environ.get("WRAPPER_VERSION", cdk_version)
print(f"Using wrapper version: {wrapper_version}")

# Strip leading 'v' if present
if wrapper_version.startswith("v"):
    wrapper_version = wrapper_version[1:]

validate_version(wrapper_version, "wrapper version")

# Extract the Node.js version from constants.py
node_version = None
with open("aws_cdk_cli/constants.py", "r") as f:
    for line in f:
        if line.startswith("NODE_VERSION ="):
            node_version = line.split("=")[1].strip().strip("\"'")
            break

if not node_version:
    print("Error: Could not extract Node.js version from constants.py")
    sys.exit(1)

# Get current date information for build metadata
build_date = datetime.datetime.now().strftime("%Y-%m-%d")
build_timestamp = datetime.datetime.now().timestamp()

# Try to get Git commit if available
build_commit = None
try:
    import subprocess

    build_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True
    ).strip()
except (subprocess.SubprocessError, FileNotFoundError):
    pass

# Create the version.py file with all original attributes
version_content = f'''"""Version information for aws-cdk-cli package.

This file is auto-generated during the build process.
It contains the AWS CDK version information.
"""

__version__ = "{wrapper_version}"  # Python package version

# Build information
__build_date__ = "{build_date}"
__build_timestamp__ = "{build_timestamp}"
__build_commit__ = "{build_commit}" if "{build_commit}" else None

# Bundled software versions
__node_version__ = "{node_version}"  # Version of Node.js downloaded during installation
__cdk_version__ = "{cdk_version}"  # Version of AWS CDK bundled

# Component licenses
__license__ = "MIT"  # License for the Python wrapper package
__cdk_license__ = "Apache-2.0"  # License for AWS CDK
__node_license__ = "MIT"  # License for Node.js

def get_version_info():
    """Return version information as a dictionary."""
    return {{
        "version": __version__,
        "build_date": __build_date__,
        "build_timestamp": __build_timestamp__,
        "build_commit": __build_commit__,
        "node_version": __node_version__,
        "cdk_version": __cdk_version__,
        "license": __license__,
        "cdk_license": __cdk_license__,
        "node_license": __node_license__
    }}
'''

# Write to version.py
with open("aws_cdk_cli/version.py", "w") as f:
    f.write(version_content)

print(
    f"Updated version.py with CDK version {cdk_version}, wrapper version {wrapper_version}, and Node.js version {node_version}"
)
print(f"Build date: {build_date}")
if build_commit:
    print(f"Build commit: {build_commit}")
