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
import json
from setuptools import setup, find_packages
from setuptools.command.install import install
from setuptools.command.develop import develop
from setuptools.command.build_py import build_py
from setuptools.command.sdist import sdist

# Constants
NODE_VERSION = "18.16.0"  # LTS version
CDK_PACKAGE_NAME = "aws-cdk"
NODE_BINARIES_DIR = os.path.join("aws_cdk_wrapper", "node_binaries")

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

# Get version from npm package if available
try:
    if "CDK_VERSION" in os.environ:
        version = os.environ["CDK_VERSION"]
        print(f"Using AWS CDK version {version} from environment variable")
    else:
        npm_version = subprocess.check_output(
            ["npm", "view", CDK_PACKAGE_NAME, "version"], 
            text=True
        ).strip()
        version = npm_version
        print(f"Using AWS CDK version {version} from npm")
except (subprocess.SubprocessError, FileNotFoundError) as e:
    raise RuntimeError(
        f"Failed to get AWS CDK version from npm for package '{CDK_PACKAGE_NAME}'. "
        "Please ensure npm is installed and accessible, or set CDK_VERSION environment variable. "
        f"Error: {str(e)}"
    )

# Read the long description from README.md
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

def download_cdk():
    """Download and bundle the AWS CDK code."""
    node_modules_dir = os.path.join("aws_cdk_wrapper", "node_modules")
    
    # Clean up any existing installations
    if os.path.exists(node_modules_dir):
        shutil.rmtree(node_modules_dir)
    
    os.makedirs(node_modules_dir, exist_ok=True)
    
    try:
        # First try using npm if available
        try:
            # Download CDK using npm with specific version
            result = subprocess.run(
                ["npm", "pack", f"{CDK_PACKAGE_NAME}@{version}"], 
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Get the name of the packed file
            tar_file = f"{CDK_PACKAGE_NAME}-{version}.tgz"
            
            # Check if the file was created
            if not os.path.exists(tar_file):
                raise FileNotFoundError(f"npm pack did not create {tar_file}")
                
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            # If npm fails, download directly from npm registry
            print("Falling back to direct download from npm registry...")
            tar_file = f"{CDK_PACKAGE_NAME}-{version}.tgz"
            registry_url = f"https://registry.npmjs.org/{CDK_PACKAGE_NAME}/-/{CDK_PACKAGE_NAME}-{version}.tgz"
            
            # Download the tarball
            with urllib.request.urlopen(registry_url) as response:
                with open(tar_file, 'wb') as out_file:
                    out_file.write(response.read())
        
        # Extract the package
        with tarfile.open(tar_file, 'r:gz') as tar_ref:
            tar_ref.extractall(node_modules_dir, filter='data')
        
        # Cleanup
        os.remove(tar_file)
        
        # Rename the directory
        package_dir = os.path.join(node_modules_dir, "package")
        cdk_dir = os.path.join(node_modules_dir, CDK_PACKAGE_NAME)
        
        if os.path.exists(package_dir):
            if os.path.exists(cdk_dir):
                shutil.rmtree(cdk_dir)
            os.rename(package_dir, cdk_dir)
        
        # Verify the installed version
        package_json = os.path.join(cdk_dir, "package.json")
        if os.path.exists(package_json):
            with open(package_json, 'r') as f:
                data = json.loads(f.read())
                installed_version = data.get('version')
                if installed_version != version:
                    raise RuntimeError(f"Installed CDK version {installed_version} does not match requested version {version}")
        
        print(f"AWS CDK {version} downloaded and bundled")
        return True
    except Exception as e:
        print(f"Failed to download AWS CDK: {e}")
        return False

def update_version_file(version):
    """Update version.py with the current version."""
    version_file = os.path.join("aws_cdk_wrapper", "version.py")
    if os.path.exists(version_file):
        with open(version_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Use regex to replace version strings
        import re
        # Update the __version__ variable
        content = re.sub(
            r'__version__ = "[^"]+"',
            f'__version__ = "{version}"',
            content
        )

        with open(version_file, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Updated version.py with version {version}")

def create_readme_for_node_binaries():
    """Create a README.txt file in the node_binaries directory."""
    node_binaries_dir = os.path.join("aws_cdk_wrapper", "node_binaries")
    os.makedirs(node_binaries_dir, exist_ok=True)
    
    readme_path = os.path.join(node_binaries_dir, "README.txt")
    with open(readme_path, "w") as f:
        f.write("Node.js binaries will be downloaded during package installation\n")
        f.write("for the specific platform.\n")
        f.write("This approach reduces package size and ensures compatibility.\n")

class CustomBuildPy(build_py):
    """Custom build command to download CDK during build."""
    def run(self):
        # Update version.py with the current version
        update_version_file(version)
        
        # Download CDK
        if not download_cdk():
            raise RuntimeError("Failed to download AWS CDK")
        
        # Create empty node_binaries directory structure
        # No need to download platform-specific binaries during build
        # They will be downloaded during post-install
        node_binaries_dir = os.path.join("aws_cdk_wrapper", "node_binaries")
        os.makedirs(node_binaries_dir, exist_ok=True)
        
        # Create README.txt in node_binaries directory
        create_readme_for_node_binaries()
                
        build_py.run(self)

# Custom sdist command to exclude node_modules from source distribution
class CustomSdist(sdist):
    """Custom sdist command for source distribution."""
    def make_release_tree(self, base_dir, files):
        # Call the original method
        sdist.make_release_tree(self, base_dir, files)
        
        # Remove node_modules directory from the release tree
        node_modules_dir = os.path.join(base_dir, "aws_cdk_wrapper", "node_modules")
        if os.path.exists(node_modules_dir):
            print(f"Removing {node_modules_dir} from source distribution")
            shutil.rmtree(node_modules_dir)
            # Create empty node_modules directory to maintain structure
            os.makedirs(node_modules_dir, exist_ok=True)
            
        # Remove node_binaries directory from the release tree
        node_binaries_dir = os.path.join(base_dir, "aws_cdk_wrapper", "node_binaries")
        if os.path.exists(node_binaries_dir):
            print(f"Removing {node_binaries_dir} from source distribution")
            shutil.rmtree(node_binaries_dir)
            # Create empty node_binaries directory structure
            os.makedirs(node_binaries_dir, exist_ok=True)
            
            # Add a README.txt to explain how the nodes are handled
            readme_path = os.path.join(node_binaries_dir, "README.txt")
            with open(readme_path, "w") as f:
                f.write("Node.js binaries will be downloaded during package installation\n")
                f.write("for the specific platform.\n")
                f.write("This approach reduces package size and ensures compatibility.\n")

# Custom install command that runs post-install script
class PostInstallCommand(install):
    """Post-installation steps for install mode."""
    def run(self):
        install.run(self)
        self.execute(self._post_install, [], msg="Running post-installation script...")
    
    def _post_install(self):
        # Instead of importing aws_cdk directly, run the post_install script directly
        # This avoids the chicken-and-egg problem during installation
        post_install_script = os.path.join(self.install_lib, "aws_cdk_wrapper", "post_install.py")
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
        post_install_script = os.path.join(self.install_lib, "aws_cdk_wrapper", "post_install.py")
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
        'aws_cdk_wrapper': [
            'node_modules/**/*', 
            'licenses/**/*',
            # Include empty node_binaries directory structure
            'node_binaries/.gitkeep',
            'node_binaries/README.txt',
        ],
    },
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'cdk=aws_cdk_wrapper.cli:main',
        ],
    },
    install_requires=[
        'setuptools',
        'requests',  # For downloading Node.js binaries
        'tqdm',      # For download progress bars
        'importlib_resources; python_version < "3.9"',  # For resource management
    ],
    python_requires='>=3.7',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
    cmdclass={
        'build_py': CustomBuildPy,
        'sdist': CustomSdist,
        'install': PostInstallCommand,
        'develop': PostDevelopCommand,
    },
) 