"""
Post-installation script for AWS CDK Python wrapper.

This script is executed after the Python package is installed.
It downloads Node.js binaries for the current platform if needed.
"""

import os
import sys
import logging
import platform
import tempfile
import zipfile
import tarfile
import aws_cdk_cli.download as download

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Constants
NODE_VERSION = "22.14.0"  # LTS version
NODE_BINARIES_DIR = os.path.join(os.path.dirname(__file__), "node_binaries")

# Platform detection (duplicated from aws_cdk.__init__)
SYSTEM = platform.system().lower()
MACHINE = platform.machine().lower()

# Map system and machine to Node.js download URLs
NODE_URLS = {
    "darwin": {
        "x86_64": f"https://nodejs.org/dist/v{NODE_VERSION}/node-v{NODE_VERSION}-darwin-x64.tar.gz",
        "arm64": f"https://nodejs.org/dist/v{NODE_VERSION}/node-v{NODE_VERSION}-darwin-arm64.tar.gz",
    },
    "linux": {
        "x86_64": f"https://nodejs.org/dist/v{NODE_VERSION}/node-v{NODE_VERSION}-linux-x64.tar.gz",
        "arm64": f"https://nodejs.org/dist/v{NODE_VERSION}/node-v{NODE_VERSION}-linux-arm64.tar.gz",
    },
    "windows": {
        "x86_64": f"https://nodejs.org/dist/v{NODE_VERSION}/node-v{NODE_VERSION}-win-x64.zip",
    },
}

# Normalize machine architecture
if MACHINE in ("amd64", "x86_64"):
    MACHINE = "x86_64"
elif MACHINE in ("arm64", "aarch64"):
    # Always use arm64 for consistency with Node.js
    MACHINE = "arm64"

# Get package directory
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))

# Define license paths as fallback
LICENSES = {
    "aws_cdk": os.path.join(PACKAGE_DIR, "licenses", "aws_cdk", "LICENSE"),
    "node": os.path.join(PACKAGE_DIR, "licenses", "node", "LICENSE"),
}


def create_license_notices():
    """
    Create license notice files in the installation directory.
    This ensures license texts are available even if they weren't included in the distribution.
    """
    try:
        # Try to import from aws_cdk_cli first, then fall back to local definitions
        try:
            from aws_cdk_cli import LICENSES
        except ImportError:
            # Already defined above as fallback
            pass

        # AWS CDK License - Apache 2.0
        cdk_license_path = LICENSES.get("aws_cdk")
        if not os.path.exists(cdk_license_path):
            cdk_license_dir = os.path.dirname(cdk_license_path)
            os.makedirs(cdk_license_dir, exist_ok=True)

            with open(cdk_license_path, "w", encoding="utf-8") as f:
                f.write(
                    """
                    Apache License
                    Version 2.0, January 2004
                    http://www.apache.org/licenses/
                    
                    Copyright (c) Amazon.com, Inc. or its affiliates. All Rights Reserved.
                    
                    Licensed under the Apache License, Version 2.0 (the "License");
                    you may not use this file except in compliance with the License.
                    You may obtain a copy of the License at
                    
                        http://www.apache.org/licenses/LICENSE-2.0
                    
                    Unless required by applicable law or agreed to in writing, software
                    distributed under the License is distributed on an "AS IS" BASIS,
                    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
                    See the License for the specific language governing permissions and
                    limitations under the License.
                """.strip()
                )

        # Node.js License - MIT
        node_license_path = LICENSES.get("node")
        if not os.path.exists(node_license_path):
            node_license_dir = os.path.dirname(node_license_path)
            os.makedirs(node_license_dir, exist_ok=True)

            with open(node_license_path, "w", encoding="utf-8") as f:
                f.write(
                    """
                    The MIT License
                    
                    Copyright Node.js contributors. All rights reserved.
                    
                    Permission is hereby granted, free of charge, to any person obtaining a copy
                    of this software and associated documentation files (the "Software"), to
                    deal in the Software without restriction, including without limitation the
                    rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
                    sell copies of the Software, and to permit persons to whom the Software is
                    furnished to do so, subject to the following conditions:
                    
                    The above copyright notice and this permission notice shall be included in
                    all copies or substantial portions of the Software.
                    
                    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
                    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
                    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
                    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
                    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
                    FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
                    IN THE SOFTWARE.
                """.strip()
                )
    except Exception as e:
        logger.warning(f"Failed to create license notices: {e}")


def is_node_installed():
    """Check if Node.js is already downloaded for the current platform."""
    extract_dir = os.path.join(NODE_BINARIES_DIR, SYSTEM, MACHINE)
    if not os.path.exists(extract_dir) or not os.listdir(extract_dir):
        return False

    node_dir = next((d for d in os.listdir(extract_dir) if d.startswith("node-")), None)

    if not node_dir:
        return False

    node_path = os.path.join(
        extract_dir,
        node_dir,
        "bin" if SYSTEM != "windows" else "",
        "node" + (".exe" if SYSTEM == "windows" else ""),
    )
    return os.path.exists(node_path)


def download_node():
    """Download Node.js binaries for the current platform."""
    try:
        node_url = NODE_URLS[SYSTEM][MACHINE]
    except KeyError:
        logger.error(f"Unsupported platform: {SYSTEM}-{MACHINE}")
        return False

    logger.info(f"Downloading Node.js v{NODE_VERSION} for {SYSTEM}-{MACHINE}...")

    # Create node_binaries directory if it doesn't exist
    extract_dir = os.path.join(NODE_BINARIES_DIR, SYSTEM, MACHINE)
    os.makedirs(extract_dir, exist_ok=True)

    # Download the Node.js binaries with progress bar
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    try:
        # Download with progress bar
        download.download_file(url=node_url, file_path=temp_file.name)

        # Close the file before extracting (important for Windows)
        temp_file.close()

        # Extract the Node.js binaries
        if node_url.endswith(".zip"):
            with zipfile.ZipFile(temp_file.name, "r") as zip_ref:
                # The filter parameter was added in Python 3.12
                if sys.version_info >= (3, 12):
                    zip_ref.extractall(extract_dir, filter="data")
                else:
                    # For older Python versions, just use regular extractall
                    zip_ref.extractall(extract_dir)
        else:  # .tar.gz
            with tarfile.open(temp_file.name, "r:gz") as tar_ref:
                # The filter parameter was added in Python 3.12
                if sys.version_info >= (3, 12):
                    # Use 'data' filter to avoid the deprecation warning in Python 3.14+
                    tar_ref.extractall(extract_dir, filter="data")
                else:
                    # For older Python versions, just use regular extractall
                    tar_ref.extractall(extract_dir)

        logger.info(f"Node.js binaries downloaded and extracted to {extract_dir}")
        return True
    except Exception as e:
        logger.error(f"Failed to download Node.js: {e}")
        return False
    finally:
        # Make sure the file is closed before trying to delete it
        if not temp_file.closed:
            temp_file.close()

        # On Windows, the file might still be in use, so try to delete it but don't fail if we can't
        try:
            os.unlink(temp_file.name)
        except Exception as e:
            logger.warning(f"Could not delete temporary file {temp_file.name}: {e}")
            # This is not a critical error, so we can continue

    if "AWS_CDK_DEBUG" in os.environ or "AWS_CDK_VERBOSE" in os.environ:
        logger.setLevel(logging.DEBUG)
        # Make installer log more verbose as well
        logging.getLogger("aws_cdk.installer").setLevel(logging.DEBUG)


def is_cdk_installed():
    """Fallback function to check if AWS CDK is installed."""
    try:
        from aws_cdk_cli import is_cdk_installed

        return is_cdk_installed()
    except ImportError:
        # Fallback implementation
        cdk_script_path = get_cdk_script_path()
        return os.path.exists(cdk_script_path)


def get_cdk_script_path():
    """Fallback function to get CDK script path."""
    try:
        from aws_cdk_cli import CDK_SCRIPT_PATH

        return CDK_SCRIPT_PATH
    except ImportError:
        # Fallback implementation
        return os.path.join(PACKAGE_DIR, "node_modules", "aws-cdk", "bin", "cdk.js")


def main():
    """Main entry point for the post-installation script."""
    try:
        # Create license notices
        create_license_notices()

        # Always download Node.js binaries since they are not bundled with the package
        logger.info("Downloading Node.js binaries for the current platform...")
        download_success = download_node()
        if download_success:
            logger.info("Node.js binaries downloaded successfully.")
        else:
            logger.warning(
                "Failed to download Node.js binaries. CDK commands may not work."
            )

        logger.info("Post-installation completed successfully.")
        return 0
    except Exception as e:
        logger.error(f"Post-installation failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
