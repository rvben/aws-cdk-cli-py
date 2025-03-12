#!/usr/bin/env python
"""Setup script for aws-cdk-wrapper package."""

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
from setuptools.command.sdist import sdist

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
except (subprocess.SubprocessError, FileNotFoundError) as e:
    raise RuntimeError(
        "Failed to get AWS CDK version from npm. "
        "Please ensure npm is installed and accessible. "
        f"Error: {str(e)}"
    )

# Read the long description from README.md
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

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

def update_version_file(version):
    """Update version.py with the current version."""
    version_file = os.path.join("aws_cdk", "version.py")
    if os.path.exists(version_file):
        with open(version_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Update version
        content = content.replace(
            '__version__ = "0.0.0"',  # Placeholder
            f'__version__ = "{version}"'
        )
        
        with open(version_file, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Updated version.py with version {version}")

class CustomBuildPy(build_py):
    """Custom build command to download CDK during build."""
    def run(self):
        # Update version.py with the current version
        update_version_file(version)
        
        # Download CDK
        download_cdk()
        
        # Create node_binaries directory structure without the actual binaries
        for system in NODE_URLS:
            for machine in NODE_URLS[system]:
                os.makedirs(os.path.join(NODE_BINARIES_DIR, system, machine), exist_ok=True)
                
        build_py.run(self)

# Custom sdist command to exclude node_modules from source distribution
class CustomSdist(sdist):
    """Custom sdist command to exclude node_modules."""
    def make_release_tree(self, base_dir, files):
        # Call the original method
        sdist.make_release_tree(self, base_dir, files)
        
        # Remove node_modules directory from the release tree
        node_modules_dir = os.path.join(base_dir, "aws_cdk", "node_modules")
        if os.path.exists(node_modules_dir):
            print(f"Removing {node_modules_dir} from source distribution")
            shutil.rmtree(node_modules_dir)

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
    name="aws-cdk-wrapper",
    version=version,
    description="Python wrapper for AWS CDK CLI with bundled Node.js runtime",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Ruben J. Jongejan",
    author_email="ruben.jongejan@gmail.com",
    url="https://github.com/rvben/aws-cdk-wrapper",
    packages=find_packages(),
    package_data={
        'aws_cdk': ['node_modules/**/*'],
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
        "tqdm",  # Progress bar support
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
        'sdist': CustomSdist,
    },
) 