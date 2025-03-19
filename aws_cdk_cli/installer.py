"""
Module for installing AWS CDK npm package and Node.js runtime.
"""

import os
import sys
import subprocess
import logging
import shutil
import tempfile
import zipfile
import tarfile
import json
import hashlib
import re
import urllib.request
import urllib.error
import datetime

# Import our custom modules instead of external dependencies
from . import semver_helper as semver
from . import download

from aws_cdk_cli import (
    NODE_MODULES_DIR,
    NODE_PLATFORM_DIR,
    NODE_BIN_PATH,
    SYSTEM,
    MACHINE,
    is_cdk_installed,
    is_node_installed,
)

logger = logging.getLogger(__name__)

# Node.js version to use
NODE_VERSION = "18.16.0"  # LTS version

# Minimum Bun version required for --eval support
MIN_BUN_VERSION = "1.1.0"

# Map system and machine to Node.js download URLs
NODE_URLS = {
    "darwin": {
        "x86_64": f"https://nodejs.org/dist/v{NODE_VERSION}/node-v{NODE_VERSION}-darwin-x64.tar.gz",
        "arm64": f"https://nodejs.org/dist/v{NODE_VERSION}/node-v{NODE_VERSION}-darwin-arm64.tar.gz",
    },
    "linux": {
        "x86_64": f"https://nodejs.org/dist/v{NODE_VERSION}/node-v{NODE_VERSION}-linux-x64.tar.gz",
        "aarch64": f"https://nodejs.org/dist/v{NODE_VERSION}/node-v{NODE_VERSION}-linux-arm64.tar.gz",
    },
    "windows": {
        "x86_64": f"https://nodejs.org/dist/v{NODE_VERSION}/node-v{NODE_VERSION}-win-x64.zip",
    },
}

# Known checksums for Node.js binaries - for verification
NODE_CHECKSUMS = {
    "darwin": {
        "x86_64": "6659dab5035e3e0fba29c4f8eb1e0367b38823fe8901bd9aa633f5dbb7863148",
        "arm64": "82c7bb4869419ce7338669e6739a786dfc7e72f276ffbed663f85ffc905dcdb4",
    },
    "linux": {
        "x86_64": "fc83046a93d2189d919005a348db3b2372b598a145d84eb9781a3a4b0f032e95",
        "aarch64": "b72f6711d010fffe3ccccdb1f1e152046235a2b5d6aac252e74f1922ecdad1e4",
    },
    "windows": {
        "x86_64": "f7ddcc40a4f9602acf22143000be501e19a3f1494c9f487316124c0c3f30a57e",
    },
}

# Define cache directory for storing downloaded files
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "aws-cdk-cli")


def check_npm_available():
    """Check if npm is available on the system."""
    try:
        subprocess.run(
            ["npm", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def get_latest_cdk_version():
    """Get the latest AWS CDK version from npm registry."""
    try:
        # First try to get it from npm
        version = subprocess.check_output(
            ["npm", "view", "aws-cdk", "version"], text=True
        ).strip()
        return version
    except (subprocess.SubprocessError, FileNotFoundError):
        try:
            # Fallback to using the bundled Node.js if available
            if is_node_installed():
                version = subprocess.check_output(
                    [
                        NODE_BIN_PATH,
                        "-e",
                        "console.log(require('child_process').execSync('npm view aws-cdk version').toString().trim())",
                    ],
                    text=True,
                ).strip()
                return version
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

        # Last resort: try to fetch from npm registry using urllib
        try:
            with urllib.request.urlopen("https://registry.npmjs.org/aws-cdk/latest") as response:
                data = json.loads(response.read().decode('utf-8'))
                return data.get("version")
        except (urllib.error.HTTPError, Exception):
            pass

    logger.error("Failed to get latest AWS CDK version from npm")
    return None


def verify_node_binary(file_path, expected_checksum):
    """Verify the downloaded Node.js binary against expected checksum."""
    # Skip verification in CI environment if configured
    if (
        os.environ.get("CI") == "true"
        and os.environ.get("SKIP_CHECKSUM_VERIFICATION") == "true"
    ):
        logger.warning("Skipping checksum verification in CI environment")
        return True

    if not expected_checksum:
        logger.warning("No checksum provided for verification, skipping")
        return True

    try:
        with open(file_path, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()

        if file_hash == expected_checksum:
            logger.info("Checksum verification passed")
            return True
        else:
            logger.error(
                f"Checksum verification failed. Expected: {expected_checksum}, Got: {file_hash}"
            )
            return False
    except Exception as e:
        logger.error(f"Error verifying checksum: {e}")
        return False


def download_node():
    """Download Node.js binaries for the current platform."""
    try:
        node_url = NODE_URLS[SYSTEM][MACHINE]
        expected_checksum = NODE_CHECKSUMS.get(SYSTEM, {}).get(MACHINE)
    except KeyError:
        error_msg = f"Unsupported platform: {SYSTEM}-{MACHINE}"
        logger.error(error_msg)
        return False, error_msg

    logger.info(f"Downloading Node.js v{NODE_VERSION} for {SYSTEM}-{MACHINE}...")

    # Create node_binaries directory if it doesn't exist
    os.makedirs(NODE_PLATFORM_DIR, exist_ok=True)

    # Create cache directory if it doesn't exist
    os.makedirs(CACHE_DIR, exist_ok=True)

    # Determine the archive filename (zip for Windows, tar.gz for others)
    archive_ext = "zip" if SYSTEM == "windows" else "tar.gz"
    archive_name = f"node-v{NODE_VERSION}-{SYSTEM}-{MACHINE if MACHINE != 'aarch64' else 'arm64'}.{archive_ext}"

    # For linux, the architecture in the filename might be x64 instead of x86_64
    if SYSTEM == "linux" and MACHINE == "x86_64":
        archive_name = f"node-v{NODE_VERSION}-linux-x64.{archive_ext}"
    elif SYSTEM == "linux" and MACHINE == "aarch64":
        archive_name = f"node-v{NODE_VERSION}-linux-arm64.{archive_ext}"

    cached_archive = os.path.join(CACHE_DIR, archive_name)

    def download_fresh_copy():
        """Download a fresh copy and cache it."""
        logger.debug("Downloading a fresh copy of Node.js")
        temp_file = tempfile.NamedTemporaryFile(delete=False).name
        try:
            # Download with progress bar using our custom module
            download.download_file(url=node_url, file_path=temp_file)

            # Verify the download
            if not is_valid_archive(temp_file):
                raise ValueError("Downloaded file is not a valid archive")

            # Cache the downloaded file
            os.makedirs(os.path.dirname(cached_archive), exist_ok=True)
            shutil.copy2(temp_file, cached_archive)
            logger.debug(f"Cached Node.js archive at {cached_archive}")
            return cached_archive
        except Exception as e:
            logger.error(f"Error downloading Node.js: {e}")
            if os.path.exists(temp_file):
                os.unlink(temp_file)
            raise
        finally:
            # Clean up the temporary file
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def is_valid_archive(file_path):
        """Check if the file is a valid archive."""
        try:
            if file_path.endswith(".zip"):
                with zipfile.ZipFile(file_path, "r") as zip_ref:
                    # Just check if it's a valid zip by listing files
                    zip_ref.namelist()
            else:  # .tar.gz
                with tarfile.open(file_path, "r:gz") as tar_ref:
                    # Just check if it's a valid tarball by listing files
                    tar_ref.getnames()
            return True
        except Exception:
            return False

    # Try to download a fresh copy if needed
    if os.path.exists(cached_archive):
        logger.debug(f"Using cached Node.js archive: {cached_archive}")
        download_path = cached_archive
    else:
        try:
            download_path = download_fresh_copy()
        except Exception as e:
            return False, f"Failed to download Node.js: {e}"

    # Extract the archive
    try:
        extract_dir = os.path.dirname(NODE_PLATFORM_DIR)
        os.makedirs(extract_dir, exist_ok=True)

        logger.debug(f"Extracting Node.js archive to {extract_dir}")
        if cached_archive.endswith(".zip"):
            with zipfile.ZipFile(download_path, "r") as zip_ref:
                zip_ref.extractall(extract_dir)
        else:
            with tarfile.open(download_path, "r:*") as tar_ref:

                def is_within_directory(directory, target):
                    abs_directory = os.path.abspath(directory)
                    abs_target = os.path.abspath(target)
                    prefix = os.path.commonprefix([abs_directory, abs_target])
                    return prefix == abs_directory

                def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
                    for member in tar.getmembers():
                        member_path = os.path.join(path, member.name)
                        if not is_within_directory(path, member_path):
                            raise Exception("Attempted Path Traversal in Tar File")
                    tar.extractall(path, members, numeric_owner=numeric_owner)

                safe_extract(tar_ref, extract_dir)

        logger.info(f"Node.js binaries extracted to {NODE_PLATFORM_DIR}")

        # If we used a temporary file (not a cached one), delete it
        if download_path != cached_archive and os.path.exists(download_path):
            try:
                os.unlink(download_path)
            except Exception as e:
                logger.warning(f"Could not delete temporary file {download_path}: {e}")

        # Get node binary path from runtime helper instead of direct path
        from aws_cdk_cli.runtime import get_node_path

        node_path = get_node_path()

        # Verify the binary exists
        if not node_path or not os.path.exists(node_path):
            # Check the directory structure to help diagnose the issue
            logger.debug(f"Contents of {NODE_PLATFORM_DIR}:")
            if os.path.exists(NODE_PLATFORM_DIR):
                for root, dirs, files in os.walk(NODE_PLATFORM_DIR):
                    logger.debug(f"Directory: {root}")
                    for d in dirs:
                        logger.debug(f"  Subdir: {d}")
                    for f in files:
                        logger.debug(f"  File: {f}")

            # For Unix systems, check if the binary is in the expected tarball directory structure
            if SYSTEM != "windows":
                # Node.js tarballs contain a directory like "node-v18.16.0-linux-x64"
                expected_dir_name = f"node-v{NODE_VERSION}-{SYSTEM}-{'x64' if MACHINE == 'x86_64' else 'arm64'}"
                expected_dir_path = os.path.join(NODE_PLATFORM_DIR, expected_dir_name)
                expected_bin_path = os.path.join(expected_dir_path, "bin", "node")

                if os.path.exists(expected_bin_path):
                    logger.info(f"Found Node.js binary at {expected_bin_path}")
                    return True, None

            error_msg = f"Node binary not found after extraction. Checked NODE_BIN_PATH: {NODE_BIN_PATH} and runtime path: {node_path}"
            logger.error(error_msg)
            return False, error_msg

        return True, None
    except Exception as e:
        error_msg = f"Failed to extract Node.js binaries: {e}"
        logger.error(error_msg)
        return False, error_msg


def find_system_nodejs():
    """
    Find the Node.js executable on the system PATH and return its path.

    Returns:
        str: Path to the Node.js executable, or None if not found
    """
    try:
        # Check if node is in PATH
        if SYSTEM == "windows":
            node_cmd = "where.exe node"
        else:
            node_cmd = "which node"

        result = subprocess.run(node_cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            node_path = result.stdout.strip().split("\n")[
                0
            ]  # Take the first one if multiple
            if os.path.exists(node_path) and os.access(node_path, os.X_OK):
                return node_path
    except Exception as e:
        logger.debug(f"Error finding system Node.js: {e}")

    return None


def get_nodejs_version(node_path):
    """
    Get the version of Node.js from the given executable path.

    Args:
        node_path (str): Path to the Node.js executable

    Returns:
        str: Version string (without v prefix), or None if failed
    """
    try:
        result = subprocess.run(
            [node_path, "--version"], capture_output=True, text=True
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            # Remove the 'v' prefix if present
            if version.startswith("v"):
                version = version[1:]
            return version
    except Exception as e:
        logger.debug(f"Error getting Node.js version: {e}")

    return None


def get_cdk_node_requirements():
    """
    Extract the Node.js version requirements from CDK's package.json.

    Returns:
        str: Node.js version requirement string (e.g. ">= 14.15.0"), or None if not found
    """
    try:
        package_json_path = os.path.join(NODE_MODULES_DIR, "aws-cdk", "package.json")
        if not os.path.exists(package_json_path):
            logger.debug("AWS CDK package.json not found")
            return None

        with open(package_json_path, "r") as f:
            package_data = json.load(f)

        # Extract Node.js version requirements from the engines field
        node_requirement = package_data.get("engines", {}).get("node")
        if node_requirement:
            return node_requirement
    except Exception as e:
        logger.debug(f"Error reading CDK Node.js requirements: {e}")

    # Default fallback requirement if we can't determine
    return ">= 14.15.0"  # Conservative default based on recent CDK versions


def get_supported_nodejs_versions():
    """
    Get the minimum supported Node.js version directly from CDK's package.json or a conservative estimate.

    Returns:
        str: The minimum supported Node.js version
    """
    # First try to get requirements from package.json
    node_req = get_cdk_node_requirements()

    if node_req:
        # Extract minimum from requirement string
        min_version = None

        try:
            # Handle multiple requirements separated by ||
            if "||" in node_req:
                # Take the lowest min from all options
                reqs = node_req.split("||")
                min_versions = []

                for req in reqs:
                    req = req.strip()
                    curr_min = extract_min_from_req(req)
                    if curr_min:
                        min_versions.append(curr_min)

                if min_versions:
                    min_version = min(
                        min_versions, key=lambda v: [int(x) for x in v.split(".")]
                    )
            else:
                # Single requirement
                min_version = extract_min_from_req(node_req)
        except Exception as e:
            logger.debug(f"Error parsing Node.js requirement '{node_req}': {e}")

    # Conservative default based on current CDK support
    if not min_version:
        min_version = "14.15.0"  # Minimum supported by recent CDK

    return min_version


def extract_min_from_req(req):
    """
    Extract minimum version from a requirement string.

    Args:
        req (str): Requirement string (e.g. ">= 14.15.0" or "^18.0.0")

    Returns:
        str: extracted minimum version or None if couldn't extract
    """
    req = req.strip()
    min_version = None

    # Handle >= or >
    if req.startswith(">="):
        min_version = req.replace(">=", "").strip()
    elif req.startswith(">"):
        # Increment the last digit to make it inclusive
        base_version = req.replace(">", "").strip()
        version_parts = base_version.split(".")
        version_parts[-1] = str(int(version_parts[-1]) + 1)
        min_version = ".".join(version_parts)

    # Handle ^
    elif req.startswith("^"):
        min_version = req.replace("^", "").strip()

    # Handle range with hyphen (x.y.z - a.b.c)
    elif " - " in req:
        parts = req.split(" - ")
        min_version = parts[0].strip()

    # Handle exact version
    elif re.match(r"^\d+\.\d+\.\d+$", req):
        min_version = req

    return min_version


def is_nodejs_compatible(version, requirement_str):
    """
    Check if the Node.js version is compatible with the requirement.

    Args:
        version (str): Node.js version to check (e.g. "16.14.2")
        requirement_str (str): Requirement string (e.g. ">= 14.15.0")

    Returns:
        bool: True if compatible, False otherwise
    """
    try:
        # Try using semver.satisfies if available (best option)
        if hasattr(semver, "satisfies"):
            try:
                return semver.satisfies(version, requirement_str)
            except Exception:
                # If satisfies fails, fall back to other methods
                pass

        # Handle various requirement formats manually
        req = requirement_str.strip()

        # Get min version from the requirement
        min_version = extract_min_from_req(req)

        # Check if version meets minimum requirement
        if min_version:
            return semver.compare(version, min_version) >= 0

        # Basic pattern matching for common version requirement formats
        if req.startswith(">="):
            min_version = req.replace(">=", "").strip()
            return semver.compare(version, min_version) >= 0
        elif req.startswith(">"):
            min_version = req.replace(">", "").strip()
            return semver.compare(version, min_version) > 0
        elif req.startswith("<="):
            max_version = req.replace("<=", "").strip()
            return semver.compare(version, max_version) <= 0
        elif req.startswith("<"):
            max_version = req.replace("<", "").strip()
            return semver.compare(version, max_version) < 0
        elif req.startswith("^"):
            # Caret range - compatible with same major version and >= base version
            base_version = req.replace("^", "").strip()
            return semver.compare(version, base_version) >= 0
        elif " - " in req:
            # Range with hyphen
            parts = req.split(" - ")
            min_version = parts[0].strip()
            max_version = parts[1].strip()
            return (
                semver.compare(version, min_version) >= 0
                and semver.compare(version, max_version) <= 0
            )
        elif re.match(r"^\d+\.\d+\.\d+$", req):
            # Exact version match
            return semver.compare(version, req) == 0

        # If we can't parse the requirement, be conservative
        logger.warning(
            f"Could not parse Node.js version requirement: {requirement_str}"
        )
        return False

    except Exception as e:
        logger.debug(f"Error checking Node.js compatibility: {e}")
        return False


def setup_nodejs():
    """
    Find or download a suitable Node.js runtime.

    Order of preference:
    1. Bun (if AWS_CDK_CLI_USE_BUN is set)
    2. System Node.js (if compatible with CDK requirements or AWS_CDK_CLI_USE_SYSTEM_NODE is set)
    3. Bundled Node.js (downloaded if not present)

    Environment variables:
    - AWS_CDK_CLI_USE_BUN: If set, try to use Bun as the JavaScript runtime
    - AWS_CDK_CLI_USE_SYSTEM_NODE: If set, prefer using system Node.js over bundled
    - AWS_CDK_CLI_USE_BUNDLED_NODE: If set, use bundled Node.js rather than system Node.js
    - AWS_CDK_CLI_SHOW_NODE_WARNINGS: If set, show Node.js version compatibility warnings

    Returns:
        Tuple of (success, result) where:
            success: Boolean indicating if a suitable JavaScript runtime was found
            result: Path to JavaScript runtime or error message if not found
    """
    # Get CDK Node.js requirements
    node_req = get_cdk_node_requirements()

    # Check if we should just download Node.js directly
    force_download = os.environ.get("AWS_CDK_CLI_USE_BUNDLED_NODE") is not None
    if force_download:
        logger.info("Using bundled Node.js")
        success, result = download_node()
        if success:
            logger.debug(f"Successfully downloaded Node.js to {NODE_BIN_PATH}")
            return True, NODE_BIN_PATH
        else:
            logger.error(f"Failed to download Node.js: {result}")
            return False, result

    # Try Bun only if explicitly requested
    use_bun = os.environ.get("AWS_CDK_CLI_USE_BUN") is not None
    if use_bun:
        bun_path = find_system_bun()
        if bun_path:
            try:
                bun_version = get_bun_version(bun_path)
                reported_version = get_bun_reported_nodejs_version(bun_path)
                is_compatible = is_bun_compatible_with_cdk(bun_path, node_req)

                if is_compatible:
                    logger.debug(f"Using Bun v{bun_version} at {bun_path}")
                    logger.debug(
                        f"Bun reports as Node.js v{reported_version}, compatible with AWS CDK requirements: {node_req}"
                    )
                    return True, bun_path
                else:
                    logger.debug(
                        f"Bun v{bun_version} reports as Node.js v{reported_version}, which is not compatible with AWS CDK requirements: {node_req}"
                    )
            except Exception:
                logger.debug(
                    f"Bun v{bun_version} is less than minimum required version {MIN_BUN_VERSION}"
                )
        else:
            logger.debug("Bun not found on the system")
        logger.debug("Could not use Bun as runtime, falling back to system Node.js")

    # Try to use system Node.js if it's compatible or explicitly requested
    force_system_node = os.environ.get("AWS_CDK_CLI_USE_SYSTEM_NODE") is not None
    system_node = find_system_nodejs()

    if system_node:
        node_version = get_nodejs_version(system_node)
        if node_version:
            # Check if this version is compatible with CDK's requirements
            is_compatible = is_nodejs_compatible(node_version, node_req)

            if is_compatible or force_system_node:
                if is_compatible:
                    logger.debug(
                        f"Using system Node.js v{node_version} at {system_node}"
                    )
                    logger.debug(f"Compatible with AWS CDK requirements: {node_req}")
                else:
                    logger.warning(
                        f"System Node.js v{node_version} may not be compatible with AWS CDK requirements: {node_req}"
                    )
                    logger.warning(
                        "Using anyway because AWS_CDK_CLI_USE_SYSTEM_NODE is set"
                    )
                return True, system_node
            else:
                logger.debug(
                    f"System Node.js v{node_version} is not compatible with AWS CDK requirements: {node_req}"
                )
    else:
        if force_system_node:
            logger.error("System Node.js requested but not found. Cannot continue.")
            return False, "System Node.js not found"
        else:
            logger.debug("No system Node.js found")

    # Finally, check if we already have a bundled Node.js
    if is_node_installed():
        logger.debug(f"Using bundled Node.js at {NODE_BIN_PATH}")
        return True, NODE_BIN_PATH

    # If no suitable runtime found yet, download Node.js
    logger.info("No suitable JavaScript runtime found. Downloading bundled Node.js...")
    success, result = download_node()
    if success:
        logger.debug(f"Successfully downloaded Node.js to {NODE_BIN_PATH}")
        return True, NODE_BIN_PATH
    else:
        logger.error(f"Failed to download Node.js: {result}")
        return False, result


def find_system_bun():
    """
    Find the Bun executable on the system PATH and return its path.

    Returns:
        str: Path to the Bun executable, or None if not found
    """
    try:
        # Check if bun is in PATH
        if SYSTEM == "windows":
            bun_cmd = "where.exe bun"
        else:
            bun_cmd = "which bun"

        result = subprocess.run(bun_cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            bun_path = result.stdout.strip().split("\n")[
                0
            ]  # Take the first one if multiple
            if os.path.exists(bun_path) and os.access(bun_path, os.X_OK):
                return bun_path
    except Exception as e:
        logger.debug(f"Error finding system Bun: {e}")

    return None


def get_bun_version(bun_path):
    """
    Get the version of Bun from the given executable path.

    Args:
        bun_path (str): Path to the Bun executable

    Returns:
        str: Version string (without v prefix), or None if failed
    """
    try:
        result = subprocess.run([bun_path, "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            version = result.stdout.strip()
            # Remove the 'v' prefix if present
            if version.startswith("v"):
                version = version[1:]
            # Handle potential extra output by extracting just the version
            match = re.search(r"(\d+\.\d+\.\d+)", version)
            if match:
                return match.group(1)
            return version
    except Exception as e:
        logger.debug(f"Error getting Bun version: {e}")

    return None


def get_bun_reported_nodejs_version(bun_path):
    """
    Get the Node.js version that Bun reports itself as.

    Args:
        bun_path (str): Path to the Bun executable

    Returns:
        str: Node.js version string, or None if failed
    """
    try:
        # Use --eval flag to get process.version
        result = subprocess.run(
            [bun_path, "--eval", "console.log(process.version)"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            # Remove the 'v' prefix if present
            if version.startswith("v"):
                version = version[1:]
            return version
    except Exception as e:
        logger.debug(f"Error getting Bun's reported Node.js version: {e}")

    return None


def is_bun_compatible_with_cdk(bun_path, node_req):
    """
    Check if Bun is compatible with AWS CDK based on its reported Node.js version.

    Args:
        bun_path (str): Path to the Bun executable
        node_req (str): Node.js version requirement string from CDK

    Returns:
        tuple: (is_compatible, reported_nodejs_version)
    """
    # First check if Bun version is at least 1.1.0 (needed for --eval support)
    bun_version = get_bun_version(bun_path)
    if not bun_version or semver.compare(bun_version, MIN_BUN_VERSION) < 0:
        logger.info(
            f"Bun version {bun_version} is less than minimum required {MIN_BUN_VERSION}"
        )
        return False, None

    # Get the Node.js version that Bun reports
    reported_version = get_bun_reported_nodejs_version(bun_path)
    if not reported_version:
        logger.info("Could not determine Bun's reported Node.js version")
        return False, None

    # Check if this reported version is compatible with CDK requirements
    is_compatible = is_nodejs_compatible(reported_version, node_req)
    return is_compatible, reported_version


def main():
    """Main function for installer script."""
    import argparse

    parser = argparse.ArgumentParser(description="AWS CDK Installer")
    parser.add_argument(
        "--download-node", action="store_true", help="Download Node.js binaries"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if Node.js and AWS CDK are installed",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Enable verbose logging if requested
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        # Enable debug logs for urllib
        urllib_logger = logging.getLogger("urllib3")
        urllib_logger.setLevel(logging.DEBUG)

    # Default behavior: if no arguments are provided, download Node.js only
    if not any([args.download_node, args.check]):
        logger.info("No arguments provided, downloading Node.js...")

        success, error = download_node()
        if not success:
            logger.error(f"Failed to download Node.js: {error}")
            return 1

        logger.info("Node.js installed successfully")
        return 0

    # Execute the requested actions
    if args.check:
        node_installed = is_node_installed()
        cdk_installed = is_cdk_installed()

        logger.info(f"Node.js is {'installed' if node_installed else 'not installed'}")
        logger.info(f"AWS CDK is {'installed' if cdk_installed else 'not installed'}")

        return 0 if node_installed and cdk_installed else 1

    if args.download_node:
        success, error = download_node()
        if not success:
            logger.error(f"Failed to download Node.js: {error}")
            return 1
        
        logger.info("Node.js downloaded successfully")

    return 0


if __name__ == "__main__":
    sys.exit(main())
