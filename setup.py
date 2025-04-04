#!/usr/bin/env python
"""Setup script for aws-cdk-cli package."""

import os
import sys
import platform
import subprocess
import shutil
import json
import re
from setuptools import setup, find_packages
from setuptools.command.install import install
from setuptools.command.develop import develop
from setuptools.command.build_py import build_py
from setuptools.command.sdist import sdist

# Constants
NODE_VERSION = "22.14.0"  # LTS version
NODE_BINARIES_DIR = os.path.join("aws_cdk_cli", "node_binaries")

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
    },
}

# Normalize machine architecture
if MACHINE in ("amd64", "x86_64"):
    MACHINE = "x86_64"
elif MACHINE in ("arm64", "aarch64"):
    MACHINE = "aarch64" if SYSTEM == "linux" else "arm64"


# Read the long description from README.md
def read_long_description():
    """Read the long description from README.md."""
    with open("README.md", "r", encoding="utf-8") as fh:
        return fh.read()


def get_version():
    """Get the CDK version from version.py."""
    # Read version from version.py, no fallbacks
    try:
        with open(os.path.join("aws_cdk_cli", "version.py"), "r") as f:
            version_content = f.read()
            version_match = re.search(
                r'__version__\s*=\s*["\']([^"\']+)["\']', version_content
            )
            if version_match:
                return version_match.group(1)
            else:
                raise ValueError("Could not find __version__ in version.py")
    except (IOError, FileNotFoundError) as e:
        raise RuntimeError(f"Could not read version from version.py: {e}")


def create_readme_for_node_binaries():
    """Create a README.txt file in the node_binaries directory."""
    node_binaries_dir = os.path.join("aws_cdk_cli", "node_binaries")
    os.makedirs(node_binaries_dir, exist_ok=True)

    readme_path = os.path.join(node_binaries_dir, "README.txt")
    with open(readme_path, "w") as f:
        f.write("Node.js binaries will be downloaded during package installation\n")
        f.write("for the specific platform.\n")
        f.write("This approach reduces package size and ensures compatibility.\n")


class CustomBuildPy(build_py):
    """Custom build command to validate CDK is available and setup node_binaries directory."""

    def run(self):
        # Get version from our helper function
        target_cdk_version = get_version()

        print(f"Building with CDK version: {target_cdk_version}")

        # Validate CDK is present (should be downloaded by Makefile before build)
        cdk_dir = os.path.join("aws_cdk_cli", "node_modules", "aws-cdk")

        if not os.path.exists(cdk_dir):
            raise RuntimeError(
                f"AWS CDK directory not found at {cdk_dir}. "
                "CDK should be downloaded before running build. "
                "Please run 'make download-cdk' first."
            )

        # Verify the installed version matches target
        package_json_path = os.path.join(cdk_dir, "package.json")
        if not os.path.exists(package_json_path):
            raise RuntimeError(
                f"AWS CDK package.json not found at {package_json_path}. "
                "CDK installation appears to be incomplete."
            )

        with open(package_json_path, "r") as f:
            package_data = json.load(f)
            installed_version = package_data.get("version")
            print(f"Found CDK version: {installed_version}")

            if installed_version != target_cdk_version:
                print(
                    f"WARNING: Installed CDK version {installed_version} doesn't match target {target_cdk_version}"
                )

        # Check if CDK binaries are present
        bin_dir = os.path.join(cdk_dir, "bin")
        if not os.path.exists(bin_dir):
            raise RuntimeError(
                f"AWS CDK bin directory not found at {bin_dir}. CDK installation appears to be incomplete."
            )

        # Check for the CDK script files
        found_script = False
        for script_name in ["cdk", "cdk.js", "cdk.cmd"]:
            script_path = os.path.join(bin_dir, script_name)
            if os.path.exists(script_path):
                print(f"Found CDK script: {script_path}")
                found_script = True
                break

        if not found_script:
            raise RuntimeError(
                "No CDK scripts found in bin directory. CDK installation appears to be incomplete."
            )

        # Create empty node_binaries directory structure
        # No need to download platform-specific binaries during build
        # They will be downloaded during post-install
        node_binaries_dir = os.path.join("aws_cdk_cli", "node_binaries")
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
        node_modules_dir = os.path.join(base_dir, "aws_cdk_cli", "node_modules")
        if os.path.exists(node_modules_dir):
            print("Keeping aws-cdk in node_modules for source distribution")
            # No longer removing the aws-cdk directory

        # Remove node_binaries directory from the release tree
        node_binaries_dir = os.path.join(base_dir, "aws_cdk_cli", "node_binaries")
        if os.path.exists(node_binaries_dir):
            print(f"Removing {node_binaries_dir} from source distribution")
            shutil.rmtree(node_binaries_dir)
            # Create empty node_binaries directory structure
            os.makedirs(node_binaries_dir, exist_ok=True)

            # Add a README.txt to explain how the nodes are handled
            readme_path = os.path.join(node_binaries_dir, "README.txt")
            with open(readme_path, "w") as f:
                f.write(
                    "Node.js binaries will be downloaded during package installation\n"
                )
                f.write("for the specific platform.\n")
                f.write(
                    "This approach reduces package size and ensures compatibility.\n"
                )


# Custom install command that runs post-install script
class PostInstallCommand(install):
    """Post-installation steps for install mode."""

    def run(self):
        install.run(self)
        self.execute(self._post_install, [], msg="Running post-installation script...")

    def _post_install(self):
        # Instead of importing aws_cdk directly, run the post_install script directly
        # This avoids the chicken-and-egg problem during installation
        post_install_script = os.path.join(
            self.install_lib, "aws_cdk_cli", "post_install.py"
        )
        if os.path.exists(post_install_script):
            # Make the script executable
            os.chmod(post_install_script, 0o755)
            # Run the script with the current Python interpreter
            # Set PYTHONPATH to include the installation directory
            env = os.environ.copy()
            env["PYTHONPATH"] = self.install_lib
            subprocess.check_call([sys.executable, post_install_script], env=env)
        else:
            print(
                f"Warning: Post-installation script not found at {post_install_script}"
            )


# Custom develop command that runs post-install script
class PostDevelopCommand(develop):
    """Post-installation steps for develop mode."""

    def run(self):
        develop.run(self)
        self.execute(self._post_install, [], msg="Running post-installation script...")

    def _post_install(self):
        # Run the post_install script directly
        try:
            import aws_cdk_cli.post_install

            aws_cdk_cli.post_install.main()
        except ImportError as e:
            print(f"Warning: Failed to import post_install module: {e}")
            post_install_script = os.path.join("aws_cdk_cli", "post_install.py")
            if os.path.exists(post_install_script):
                # Make the script executable
                os.chmod(post_install_script, 0o755)
                # Run the script with the current Python interpreter
                subprocess.check_call([sys.executable, post_install_script])
            else:
                print(
                    f"Warning: Post-installation script not found at {post_install_script}"
                )


# This setup function is used in legacy mode, but the main configuration is in pyproject.toml
if __name__ == "__main__":
    # Get version from version.py with fallbacks
    cdk_version = get_version()

    setup(
        name="aws-cdk-cli",
        version=cdk_version,
        description="Python wrapper for AWS CDK CLI with smart Node.js runtime management",
        long_description=read_long_description(),
        long_description_content_type="text/markdown",
        url="https://github.com/rvben/aws-cdk-cli-py",
        packages=find_packages(),
        package_data={
            "aws_cdk_cli": [
                "node_modules/**/*",
                "licenses/**/*",
                # Include empty node_binaries directory structure
                "node_binaries/.gitkeep",
                "node_binaries/README.txt",
            ],
        },
        include_package_data=True,
        entry_points={
            "console_scripts": [
                "cdk=aws_cdk_cli.cli:main",
            ],
        },
        install_requires=[
            'importlib_resources; python_version < "3.9"',  # For resource management
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
            "build_py": CustomBuildPy,
            "install": PostInstallCommand,
            "develop": PostDevelopCommand,
            "sdist": CustomSdist,
        },
    )
else:
    # When imported (rather than executed), expose the custom classes for pyproject.toml
    __all__ = [
        "CustomBuildPy",
        "PostInstallCommand",
        "PostDevelopCommand",
        "CustomSdist",
    ]
