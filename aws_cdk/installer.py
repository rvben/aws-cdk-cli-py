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
        "arm64": "82c7bb4869419ce7338669e6739a786dfc7e72f276ffbed663f85ffc905dcdb4",
    },
    "linux": {
        "x86_64": "fc83046a93d2189d919005a348db3b2372b598a145d84eb9781a3a4b0f032e95",
        "aarch64": "b72f6711d010fffe3ccccdb1f1e152046235a2b5d6aac252e74f1922ecdad1e4",
    },
    "windows": {
        "x86_64": "f7ddcc40a4f9602acf22143000be501e19a3f1494c9f487316124c0c3f30a57e",
    }
}

# Cache directory for downloads
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "aws-cdk-wrapper")

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
    # Skip verification in CI environment if configured
    if os.environ.get('CI') == 'true' and os.environ.get('SKIP_CHECKSUM_VERIFICATION') == 'true':
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
            logger.error(f"Checksum verification failed. Expected: {expected_checksum}, Got: {file_hash}")
            return False
    except Exception as e:
        logger.error(f"Error verifying checksum: {e}")
        return False

def download_node():
    """Download Node.js binaries for the current platform."""
    try:
        node_url = NODE_URLS[SYSTEM][MACHINE]
    except KeyError:
        logger.error(f"Unsupported platform: {SYSTEM}-{MACHINE}")
        return False
    
    logger.info(f"Downloading Node.js v{NODE_VERSION} for {SYSTEM}-{MACHINE}...")
    
    # Create node_binaries directory if it doesn't exist
    os.makedirs(NODE_PLATFORM_DIR, exist_ok=True)
    
    # Create cache directory if it doesn't exist
    os.makedirs(CACHE_DIR, exist_ok=True)
    
    # Determine the archive filename (zip for Windows, tar.gz for others)
    archive_ext = "zip" if SYSTEM == "windows" else "tar.gz"
    archive_name = f"node-v{NODE_VERSION}-{SYSTEM}-{MACHINE}.{archive_ext}"
    cached_archive = os.path.join(CACHE_DIR, archive_name)
    
    def download_fresh_copy():
        """Download a fresh copy and cache it."""
        logger.debug("Downloading a fresh copy of Node.js")
        temp_file = tempfile.NamedTemporaryFile(delete=False).name
        try:
            # Try to import tqdm for progress bar
            try:
                from tqdm import tqdm
                
                # Get the file size
                with urllib.request.urlopen(node_url) as response:
                    file_size = int(response.headers.get('Content-Length', 0))
                
                # Download with progress bar
                with tqdm(total=file_size, unit='B', unit_scale=True, 
                          desc=f"Downloading Node.js v{NODE_VERSION}") as progress_bar:
                    
                    def report_progress(block_count, block_size, total_size):
                        progress_bar.update(block_size)
                    
                    urllib.request.urlretrieve(node_url, temp_file, reporthook=report_progress)
            
            except ImportError:
                # Fallback to simple download without progress bar
                logger.info("Progress bar not available. Downloading...")
                with urllib.request.urlopen(node_url) as response, open(temp_file, 'wb') as out_file:
                    shutil.copyfileobj(response, out_file)
            
            # Cache the downloaded archive for future use
            shutil.copy(temp_file, cached_archive)
            logger.info(f"Cached Node.js binaries to: {cached_archive}")
            return temp_file
            
        except Exception as e:
            logger.error(f"Failed to download Node.js: {e}")
            if os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except Exception:
                    pass
            return None
    
    def is_valid_archive(file_path):
        """Check if the file is a valid archive."""
        try:
            if file_path.endswith('.zip'):
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    # Just check if it's a valid zip by listing files
                    zip_ref.namelist()
            else:  # .tar.gz
                with tarfile.open(file_path, 'r:gz') as tar_ref:
                    # Just check if it's a valid tarball by listing files
                    tar_ref.getnames()
            return True
        except Exception:
            return False
    
    # Check if we have a cached archive
    use_cached = False
    if os.path.exists(cached_archive):
        logger.info(f"Using cached Node.js binaries: {cached_archive}")
        # Validate cached archive before using it
        if is_valid_archive(cached_archive):
            temp_file = cached_archive
            use_cached = True
        else:
            logger.warning(f"Cached file is invalid or corrupted, removing: {cached_archive}")
            try:
                os.unlink(cached_archive)
            except Exception as e:
                logger.warning(f"Failed to delete invalid cache file: {e}")
            
            # Download a fresh copy
            temp_file = download_fresh_copy()
            if not temp_file:
                return False
    else:
        # Download a fresh copy
        temp_file = download_fresh_copy()
        if not temp_file:
            return False
    
    try:
        # Extract the Node.js binaries
        if archive_ext == 'zip':
            with zipfile.ZipFile(temp_file, 'r') as zip_ref:
                zip_ref.extractall(NODE_PLATFORM_DIR, filter='data')
        else:  # .tar.gz
            with tarfile.open(temp_file, 'r:gz') as tar_ref:
                # Use 'data' filter to avoid the deprecation warning in Python 3.14+
                tar_ref.extractall(NODE_PLATFORM_DIR, filter='data')
        
        logger.info(f"Node.js binaries extracted to {NODE_PLATFORM_DIR}")
        
        # If we used a temporary file (not a cached one), delete it
        if temp_file != cached_archive and os.path.exists(temp_file):
            try:
                os.unlink(temp_file)
            except Exception as e:
                logger.warning(f"Could not delete temporary file {temp_file}: {e}")
        
        return True
    except Exception as e:
        logger.error(f"Failed to extract Node.js binaries: {e}")
        return False

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
    
    def download_fresh_cdk_copy():
        """Download a fresh copy of CDK and cache it."""
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
            return tar_file
            
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
                    logger.info(f"Downloaded AWS CDK package directly to: {cached_tar}")
                    return cached_tar
                else:
                    logger.error(f"Failed to download AWS CDK: HTTP {response.status_code}")
                    return None
            except Exception as e:
                logger.error(f"Failed to download AWS CDK directly: {e}")
                return None
    
    def is_valid_tarball(file_path):
        """Check if the file is a valid tarball."""
        try:
            with tarfile.open(file_path, 'r:gz') as tar_ref:
                # Just check if it's a valid tarball by listing files
                tar_ref.getnames()
            return True
        except Exception:
            return False
    
    # Try to use cached copy if it exists
    use_cached = False
    if os.path.exists(cached_tar):
        logger.info(f"Using cached AWS CDK package: {cached_tar}")
        # Validate cached tarball before using it
        if is_valid_tarball(cached_tar):
            tar_file = cached_tar
            use_cached = True
        else:
            logger.warning(f"Cached CDK tarball is invalid or corrupted, removing: {cached_tar}")
            try:
                os.unlink(cached_tar)
            except Exception as e:
                logger.warning(f"Failed to delete invalid cache file: {e}")
            
            # Download a fresh copy
            tar_file = download_fresh_cdk_copy()
            if not tar_file:
                return False
    else:
        # Download a fresh copy
        tar_file = download_fresh_cdk_copy()
        if not tar_file:
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
            tar_ref.extractall(temp_dir, filter='data')
            
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

def main():
    """Main function for installer script."""
    import argparse
    
    parser = argparse.ArgumentParser(description="AWS CDK Installer")
    parser.add_argument("--download-node", action="store_true", help="Download Node.js binaries")
    parser.add_argument("--install-cdk", action="store_true", help="Install AWS CDK")
    parser.add_argument("--update-cdk", action="store_true", help="Update AWS CDK to the latest version")
    parser.add_argument("--check", action="store_true", help="Check if Node.js and AWS CDK are installed")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Enable verbose logging if requested
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        # Enable debug logs for urllib
        urllib_logger = logging.getLogger("urllib3")
        urllib_logger.setLevel(logging.DEBUG)
        
    # Default behavior: if no arguments are provided, install both Node.js and CDK
    if not any([args.download_node, args.install_cdk, args.update_cdk, args.check]):
        logger.info("No arguments provided, installing both Node.js and AWS CDK...")
        
        if not download_node():
            logger.error("Failed to download Node.js")
            return 1
        
        if not install_cdk():
            logger.error("Failed to install AWS CDK")
            return 1
        
        logger.info("Node.js and AWS CDK installed successfully")
        return 0
    
    # Execute the requested actions
    if args.check:
        node_installed = is_node_installed()
        cdk_installed = is_cdk_installed()
        
        logger.info(f"Node.js is {'installed' if node_installed else 'not installed'}")
        logger.info(f"AWS CDK is {'installed' if cdk_installed else 'not installed'}")
        
        return 0 if node_installed and cdk_installed else 1
    
    if args.download_node:
        if not download_node():
            logger.error("Failed to download Node.js")
            return 1
    
    if args.install_cdk:
        if not install_cdk():
            logger.error("Failed to install AWS CDK")
            return 1
    
    if args.update_cdk:
        if not update_cdk():
            logger.error("Failed to update AWS CDK")
            return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 