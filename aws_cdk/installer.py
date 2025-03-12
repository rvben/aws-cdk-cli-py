"""
Module for installing AWS CDK npm package and Node.js runtime.
"""

import os
import sys
import platform
import subprocess
import logging
import shutil
import urllib.request
import tempfile
import zipfile
import tarfile
import json
from pathlib import Path
import hashlib
import datetime

from aws_cdk import (
    PACKAGE_DIR, NODE_MODULES_DIR, NODE_BINARIES_DIR, NODE_PLATFORM_DIR,
    NODE_BIN_PATH, CDK_SCRIPT_PATH, SYSTEM, MACHINE,
    is_cdk_installed, is_node_installed
)

logger = logging.getLogger(__name__)

# Node.js version to use
NODE_VERSION = "18.16.0"  # LTS version

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
    }
}

# Known checksums for Node.js binaries - for verification
NODE_CHECKSUMS = {
    "darwin": {
        "x86_64": "6659dab5035e3e0fba29c4f8eb1e0367b38823fe8901bd9aa633f5dbb7863148",
        "arm64": "8a464ddec219de5602ca0e89da4db4f34c3828a83a04177e968e8499257641a3",
    },
    "linux": {
        "x86_64": "96728d3bdc1139cd15520242e6bb5599ff259617b5cdcfd124e094d7ecb51612",
        "aarch64": "b72f6711d010fffe3ccccdb1f1e152046235a2b5d6aac252e74f1922ecdad1e4",
    },
    "windows": {
        "x86_64": "f7ddcc40a4f9602acf22143000be501e19a3f1494c9f487316124c0c3f30a57e",
    }
}

# Cache directory for downloads
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".aws-cdk-wrapper", "cache")

def check_npm_available():
    """Check if npm is available on the system."""
    try:
        subprocess.run(
            ["npm", "--version"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            check=True
        )
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False

def get_latest_cdk_version():
    """Get the latest AWS CDK version from npm registry."""
    try:
        # First try to get it from npm
        version = subprocess.check_output(
            ["npm", "view", "aws-cdk", "version"], 
            text=True
        ).strip()
        return version
    except (subprocess.SubprocessError, FileNotFoundError):
        try:
            # Fallback to using the bundled Node.js if available
            if is_node_installed():
                version = subprocess.check_output(
                    [NODE_BIN_PATH, "-e", "console.log(require('child_process').execSync('npm view aws-cdk version').toString().trim())"],
                    text=True
                ).strip()
                return version
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

        # Last resort: try to fetch from npm registry using requests
        try:
            import requests
            response = requests.get("https://registry.npmjs.org/aws-cdk/latest")
            if response.status_code == 200:
                data = response.json()
                return data.get("version")
        except Exception:
            pass

        logger.error("Failed to get latest AWS CDK version from npm")
        return None

def verify_node_binary(file_path, expected_checksum):
    """Verify the downloaded Node.js binary against expected checksum."""
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
            logger.error(f"Checksum verification failed. Expected: {expected_checksum}, Got: {file_hash}")
            return False
    except Exception as e:
        logger.error(f"Error verifying checksum: {e}")
        return False

def download_node():
    """Download Node.js binaries for the current platform."""
    if is_node_installed():
        logger.info("Node.js is already installed")
        return True
    
    try:
        node_url = NODE_URLS[SYSTEM][MACHINE]
        expected_checksum = NODE_CHECKSUMS.get(SYSTEM, {}).get(MACHINE)
    except KeyError:
        logger.error(f"Unsupported platform: {SYSTEM}-{MACHINE}")
        
        # Try to find a fallback that might work
        if SYSTEM == "linux" and MACHINE not in NODE_URLS["linux"]:
            logger.warning(f"Attempting fallback to x86_64 binaries for Linux")
            MACHINE = "x86_64"
            try:
                node_url = NODE_URLS[SYSTEM][MACHINE]
                expected_checksum = NODE_CHECKSUMS.get(SYSTEM, {}).get(MACHINE)
            except KeyError:
                return False
        else:
            return False
    
    logger.info(f"Downloading Node.js v{NODE_VERSION} for {SYSTEM}-{MACHINE}...")
    
    # Create cache directory if it doesn't exist
    os.makedirs(CACHE_DIR, exist_ok=True)
    
    # Check if we have a cached copy
    filename = os.path.basename(node_url)
    cached_file = os.path.join(CACHE_DIR, filename)
    
    if os.path.exists(cached_file):
        logger.info(f"Using cached Node.js binary: {cached_file}")
        if expected_checksum and verify_node_binary(cached_file, expected_checksum):
            temp_file = cached_file
        else:
            # If verification fails or no checksum, download again
            os.remove(cached_file)
            temp_file = None
    else:
        temp_file = None
    
    # Download if not using cached file
    if not temp_file:
        temp_file = tempfile.NamedTemporaryFile(delete=False).name
        try:
            logger.info(f"Downloading from: {node_url}")
            with urllib.request.urlopen(node_url) as response, open(temp_file, 'wb') as out_file:
                shutil.copyfileobj(response, out_file)
            
            # Verify the downloaded file
            if expected_checksum and not verify_node_binary(temp_file, expected_checksum):
                logger.error("Downloaded file failed checksum verification")
                return False
            
            # Cache the file for future use
            shutil.copy(temp_file, cached_file)
            logger.info(f"Cached Node.js binary to: {cached_file}")
            
        except Exception as e:
            logger.error(f"Failed to download Node.js: {e}")
            return False
    
    try:
        # Create node_binaries directory if it doesn't exist
        os.makedirs(NODE_BINARIES_DIR, exist_ok=True)
        
        # Extract the Node.js binaries
        os.makedirs(NODE_PLATFORM_DIR, exist_ok=True)
        
        if node_url.endswith('.zip'):
            with zipfile.ZipFile(temp_file, 'r') as zip_ref:
                zip_ref.extractall(NODE_PLATFORM_DIR)
        else:  # .tar.gz
            with tarfile.open(temp_file, 'r:gz') as tar_ref:
                # Get the top-level directory name in the tarball
                top_level_dirs = [name for name in tar_ref.getnames() if '/' not in name and name.endswith('/')]
                if top_level_dirs:
                    top_dir = top_level_dirs[0]
                    # Extract all files, but we'll need to fix the directory structure
                    tar_ref.extractall(NODE_PLATFORM_DIR)
                    
                    # Move files from the top-level directory to NODE_PLATFORM_DIR
                    extracted_dir = os.path.join(NODE_PLATFORM_DIR, top_dir.rstrip('/'))
                    if os.path.exists(extracted_dir):
                        for item in os.listdir(extracted_dir):
                            source = os.path.join(extracted_dir, item)
                            target = os.path.join(NODE_PLATFORM_DIR, item)
                            if os.path.exists(target):
                                if os.path.isdir(target):
                                    shutil.rmtree(target)
                                else:
                                    os.remove(target)
                            shutil.move(source, NODE_PLATFORM_DIR)
                        
                        # Remove the empty directory
                        if os.path.exists(extracted_dir):
                            shutil.rmtree(extracted_dir)
                else:
                    # No top-level directory, extract directly
                    tar_ref.extractall(NODE_PLATFORM_DIR)
        
        # Make node executable on Unix-like systems
        if SYSTEM != "windows" and os.path.exists(NODE_BIN_PATH):
            os.chmod(NODE_BIN_PATH, 0o755)
        
        # Create a metadata file for tracking the installed version
        metadata = {
            "node_version": NODE_VERSION,
            "platform": SYSTEM,
            "architecture": MACHINE,
            "installation_date": datetime.datetime.now().isoformat(),
        }
        
        metadata_path = os.path.join(NODE_PLATFORM_DIR, "metadata.json")
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Node.js binaries installed to {NODE_PLATFORM_DIR}")
        return True
    except Exception as e:
        logger.error(f"Failed to extract Node.js binaries: {e}")
        return False
    finally:
        if temp_file != cached_file and os.path.exists(temp_file):
            os.unlink(temp_file)

def download_cdk():
    """Download and bundle the AWS CDK code."""
    if is_cdk_installed():
        logger.info("AWS CDK is already installed")
        return True
    
    if not is_node_installed():
        if not download_node():
            logger.error("Failed to download Node.js. Cannot install CDK.")
            return False
    
    logger.info("Downloading AWS CDK...")
    
    # Create cache directory if it doesn't exist
    os.makedirs(CACHE_DIR, exist_ok=True)
    
    # Get latest version
    version = get_latest_cdk_version() or "latest"
    
    # Check if we have a cached copy
    cached_tar = os.path.join(CACHE_DIR, f"aws-cdk-{version}.tgz")
    
    if os.path.exists(cached_tar):
        logger.info(f"Using cached AWS CDK package: {cached_tar}")
        tar_file = cached_tar
    else:
        # Create node_modules directory if it doesn't exist
        os.makedirs(NODE_MODULES_DIR, exist_ok=True)
        
        try:
            # Use npm to download CDK
            if check_npm_available():
                # Use system npm if available
                subprocess.run(
                    ["npm", "pack", "aws-cdk"], 
                    check=True,
                    stdout=subprocess.PIPE
                )
            else:
                # Use bundled Node.js to run npm
                subprocess.run(
                    [NODE_BIN_PATH, "-e", "require('child_process').execSync('npm pack aws-cdk')"],
                    check=True,
                    stdout=subprocess.PIPE
                )
            
            # Get the name of the packed file
            tar_file = f"aws-cdk-{version}.tgz"
            
            # Cache the file for future use
            shutil.copy(tar_file, cached_tar)
            logger.info(f"Cached AWS CDK package to: {cached_tar}")
            
        except Exception as e:
            logger.error(f"Failed to download AWS CDK using npm: {e}")
            
            # Fallback: try to download directly from npm registry
            try:
                import requests
                tarball_url = f"https://registry.npmjs.org/aws-cdk/-/aws-cdk-{version}.tgz"
                logger.info(f"Attempting direct download from: {tarball_url}")
                
                response = requests.get(tarball_url)
                if response.status_code == 200:
                    with open(cached_tar, 'wb') as f:
                        f.write(response.content)
                    tar_file = cached_tar
                    logger.info(f"Downloaded AWS CDK package directly to: {cached_tar}")
                else:
                    logger.error(f"Failed to download AWS CDK: HTTP {response.status_code}")
                    return False
            except Exception as e:
                logger.error(f"Failed to download AWS CDK directly: {e}")
                return False
    
    try:
        # Extract the package
        cdk_dir = os.path.join(NODE_MODULES_DIR, "aws-cdk")
        if os.path.exists(cdk_dir):
            shutil.rmtree(cdk_dir)
        
        with tarfile.open(tar_file, 'r:gz') as tar_ref:
            # First check if it has a 'package' directory
            has_package_dir = any(name.startswith('package/') for name in tar_ref.getnames())
            
            # Extract to a temporary directory first
            temp_dir = tempfile.mkdtemp()
            tar_ref.extractall(temp_dir)
            
            # Now move the files to the right place
            if has_package_dir:
                package_dir = os.path.join(temp_dir, "package")
                if os.path.exists(package_dir):
                    os.makedirs(cdk_dir, exist_ok=True)
                    for item in os.listdir(package_dir):
                        shutil.move(os.path.join(package_dir, item), cdk_dir)
            else:
                # No package directory, move everything
                os.makedirs(cdk_dir, exist_ok=True)
                for item in os.listdir(temp_dir):
                    shutil.move(os.path.join(temp_dir, item), cdk_dir)
            
            # Cleanup
            shutil.rmtree(temp_dir)
        
        # Cleanup the local tarball if we didn't use the cached one
        if tar_file != cached_tar and os.path.exists(tar_file):
            os.remove(tar_file)
        
        # Create a metadata file for tracking the installed version
        metadata = {
            "cdk_version": version,
            "installation_date": datetime.datetime.now().isoformat(),
        }
        
        metadata_path = os.path.join(cdk_dir, "metadata.json")
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"AWS CDK {version} downloaded and installed")
        return True
    except Exception as e:
        logger.error(f"Failed to extract AWS CDK package: {e}")
        return False

def install_cdk():
    """Install AWS CDK using bundled Node.js."""
    if is_cdk_installed():
        logger.info("AWS CDK is already installed")
        return True
    
    # First, ensure Node.js is installed
    if not is_node_installed():
        if not download_node():
            logger.error("Failed to download Node.js. Cannot install CDK.")
            return False
    
    # Then, download and install CDK
    if not download_cdk():
        logger.error("Failed to download AWS CDK")
        return False
    
    logger.info("AWS CDK installed successfully")
    return True

def update_cdk():
    """Update AWS CDK to the latest version."""
    logger.info("Updating AWS CDK...")
    
    # Get the latest version
    latest_version = get_latest_cdk_version()
    if not latest_version:
        logger.error("Failed to determine latest AWS CDK version")
        return False
    
    # Check current version
    current_version = None
    metadata_path = os.path.join(NODE_MODULES_DIR, "aws-cdk", "metadata.json")
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
                current_version = metadata.get("cdk_version")
        except Exception:
            pass
    
    if current_version == latest_version:
        logger.info(f"AWS CDK is already at the latest version ({latest_version})")
        return True
    
    # Remove existing CDK installation
    cdk_dir = os.path.join(NODE_MODULES_DIR, "aws-cdk")
    if os.path.exists(cdk_dir):
        shutil.rmtree(cdk_dir)
    
    # Download and install the latest version
    if download_cdk():
        logger.info(f"AWS CDK updated to version {latest_version}")
        return True
    else:
        logger.error("Failed to update AWS CDK")
        return False 