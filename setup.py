#!/usr/bin/env python
"""Setup script for aws-cdk package."""

import os
import sys
import platform
import subprocess
import urllib.request
import tempfile
import zipfile
import tarfile
import shutil
from setuptools import setup, find_packages
from setuptools.command.install import install
from setuptools.command.develop import develop
from setuptools.command.build_py import build_py

# Constants
NODE_VERSION = "18.16.0"  # LTS version
CDK_PACKAGE_NAME = "aws-cdk"
NODE_BINARIES_DIR = os.path.join("aws_cdk", "node_binaries")

# Platform detection
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
        "aarch64": f"https://nodejs.org/dist/v{NODE_VERSION}/node-v{NODE_VERSION}-linux-arm64.tar.gz",
    },
    "windows": {
        "x86_64": f"https://nodejs.org/dist/v{NODE_VERSION}/node-v{NODE_VERSION}-win-x64.zip",
    }
}

# Normalize machine architecture
if MACHINE in ("amd64", "x86_64"):
    MACHINE = "x86_64"
elif MACHINE in ("arm64", "aarch64"):
    MACHINE = "aarch64" if SYSTEM == "linux" else "arm64"

# Get version from npm package if available, otherwise use a default
try:
    npm_version = subprocess.check_output(
        ["npm", "view", CDK_PACKAGE_NAME, "version"], 
        text=True
    ).strip()
    version = npm_version
except (subprocess.SubprocessError, FileNotFoundError):
    version = "0.0.1"  # Default version if npm check fails

# Read the long description from README.md
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

def download_node():
    """Download Node.js binaries for the current platform."""
    try:
        node_url = NODE_URLS[SYSTEM][MACHINE]
    except KeyError:
        print(f"Unsupported platform: {SYSTEM}-{MACHINE}")
        return False
    
    print(f"Downloading Node.js v{NODE_VERSION} for {SYSTEM}-{MACHINE}...")
    
    # Create node_binaries directory if it doesn't exist
    os.makedirs(NODE_BINARIES_DIR, exist_ok=True)
    
    # Download the Node.js binaries
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    try:
        with urllib.request.urlopen(node_url) as response, open(temp_file.name, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
        
        # Extract the Node.js binaries
        extract_dir = os.path.join(NODE_BINARIES_DIR, SYSTEM, MACHINE)
        os.makedirs(extract_dir, exist_ok=True)
        
        if node_url.endswith('.zip'):
            with zipfile.ZipFile(temp_file.name, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
        else:  # .tar.gz
            with tarfile.open(temp_file.name, 'r:gz') as tar_ref:
                tar_ref.extractall(extract_dir)
        
        print(f"Node.js binaries downloaded and extracted to {extract_dir}")
        return True
    except Exception as e:
        print(f"Failed to download Node.js: {e}")
        return False
    finally:
        os.unlink(temp_file.name)

def download_cdk():
    """Download and bundle the AWS CDK code."""
    node_modules_dir = os.path.join("aws_cdk", "node_modules")
    os.makedirs(node_modules_dir, exist_ok=True)
    
    try:
        # Download CDK using npm
        subprocess.run(
            ["npm", "pack", CDK_PACKAGE_NAME], 
            check=True,
            stdout=subprocess.PIPE
        )
        
        # Get the name of the packed file
        tar_file = f"{CDK_PACKAGE_NAME}-{version}.tgz"
        
        # Extract the package
        with tarfile.open(tar_file, 'r:gz') as tar_ref:
            tar_ref.extractall(node_modules_dir)
        
        # Cleanup
        os.remove(tar_file)
        
        # Rename the directory
        package_dir = os.path.join(node_modules_dir, "package")
        cdk_dir = os.path.join(node_modules_dir, CDK_PACKAGE_NAME)
        if os.path.exists(package_dir):
            if os.path.exists(cdk_dir):
                shutil.rmtree(cdk_dir)
            os.rename(package_dir, cdk_dir)
        
        print(f"AWS CDK {version} downloaded and bundled")
        return True
    except Exception as e:
        print(f"Failed to download AWS CDK: {e}")
        return False

class CustomBuildPy(build_py):
    """Custom build command to download Node.js and CDK during build."""
    def run(self):
        # Download Node.js and CDK before building
        download_node()
        download_cdk()
        build_py.run(self)

# Custom install command that runs post-install script
class PostInstallCommand(install):
    """Post-installation steps for install mode."""
    def run(self):
        install.run(self)
        self.execute(self._post_install, [], msg="Running post-installation script...")
    
    def _post_install(self):
        # Instead of importing aws_cdk directly, run the post_install script directly
        # This avoids the chicken-and-egg problem during installation
        post_install_script = os.path.join(self.install_lib, "aws_cdk", "post_install.py")
        if os.path.exists(post_install_script):
            # Make the script executable
            os.chmod(post_install_script, 0o755)
            # Run the script with the current Python interpreter
            subprocess.check_call([sys.executable, post_install_script])
        else:
            print(f"Warning: Post-installation script not found at {post_install_script}")

# Custom develop command that runs post-install script
class PostDevelopCommand(develop):
    """Post-installation steps for develop mode."""
    def run(self):
        develop.run(self)
        self.execute(self._post_install, [], msg="Running post-installation script...")
    
    def _post_install(self):
        # Same approach as in PostInstallCommand
        post_install_script = os.path.join(self.install_lib, "aws_cdk", "post_install.py")
        if os.path.exists(post_install_script):
            os.chmod(post_install_script, 0o755)
            subprocess.check_call([sys.executable, post_install_script])
        else:
            print(f"Warning: Post-installation script not found at {post_install_script}")

setup(
    name=CDK_PACKAGE_NAME,
    version=version,
    description="Python wrapper for AWS CDK CLI with bundled Node.js runtime",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="AWS CDK Python Wrapper Team",
    author_email="example@example.com",
    url="https://github.com/your-username/aws-cdk",
    packages=find_packages(),
    package_data={
        'aws_cdk': ['node_binaries/**/*', 'node_modules/**/*'],
    },
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "cdk=aws_cdk.cli:main",
        ],
    },
    install_requires=[
        "setuptools",
        "requests",
        "importlib_resources; python_version < '3.9'",
    ],
    python_requires=">=3.7",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    cmdclass={
        'build_py': CustomBuildPy,
        'install': PostInstallCommand,
        'develop': PostDevelopCommand,
    },
) 