#!/usr/bin/env python3
"""
Helper script to download CDK during the build process.
This script is used by the Makefile to ensure CDK is downloaded before building.
"""

import os
import sys
import subprocess
import tempfile
import tarfile
import shutil
import json
import datetime
import urllib.request
import urllib.error

# Constants
CDK_PACKAGE_NAME = "aws-cdk"


def download_cdk():
    """Download and bundle the AWS CDK code."""
    node_modules_dir = os.path.join("aws_cdk_cli", "node_modules")

    # Clean up any existing installations
    if os.path.exists(node_modules_dir):
        print("Cleaning up existing node_modules directory")
        shutil.rmtree(node_modules_dir)

    os.makedirs(node_modules_dir, exist_ok=True)

    # Get the version to use
    version = os.environ.get("CDK_VERSION")

    if not version:
        print("ERROR: CDK_VERSION environment variable not set")
        raise ValueError("CDK_VERSION environment variable must be set")

    print(f"Downloading AWS CDK version {version}")

    try:
        # First try using npm if available
        try:
            # Download CDK using npm with specific version
            print(f"Running: npm pack {CDK_PACKAGE_NAME}@{version}")
            result = subprocess.run(
                ["npm", "pack", f"{CDK_PACKAGE_NAME}@{version}"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Get the name of the packed file from the output
            tar_file = result.stdout.strip()
            print(f"npm pack stdout: '{tar_file}'")

            if not tar_file:
                # Fall back to expected filename pattern
                tar_file = f"{CDK_PACKAGE_NAME}-{version}.tgz"
                print(f"No output from npm pack, using fallback filename: {tar_file}")

            # Check if the file was created
            if not os.path.exists(tar_file):
                raise FileNotFoundError(f"npm pack did not create {tar_file}")

        except (subprocess.SubprocessError, FileNotFoundError) as e:
            # If npm fails, download directly from npm registry
            print(f"npm command failed: {e}")
            print("Falling back to direct download from npm registry...")
            tar_file = f"{CDK_PACKAGE_NAME}-{version}.tgz"
            registry_url = f"https://registry.npmjs.org/{CDK_PACKAGE_NAME}/-/{CDK_PACKAGE_NAME}-{version}.tgz"

            print(f"Downloading from URL: {registry_url}")
            # Download the tarball using urllib instead of requests
            try:
                with urllib.request.urlopen(registry_url) as response:
                    with open(tar_file, "wb") as out_file:
                        out_file.write(response.read())
            except urllib.error.HTTPError as e:
                raise RuntimeError(f"Failed to download AWS CDK: HTTP {e.code}")

            print(f"Successfully downloaded {tar_file}")

        # Extract the package
        print(f"Extracting {tar_file}")
        with tarfile.open(tar_file, "r:gz") as tar_ref:
            # Extract to a temporary directory first
            temp_dir = tempfile.mkdtemp()
            print(f"Extracting to temporary directory: {temp_dir}")

            # The filter parameter was added in Python 3.12
            if sys.version_info >= (3, 12):
                tar_ref.extractall(temp_dir, filter="data")
            else:
                # For older Python versions, just use regular extractall
                tar_ref.extractall(temp_dir)

            # Move the files to the right place
            package_dir = os.path.join(temp_dir, "package")
            cdk_dir = os.path.join(node_modules_dir, CDK_PACKAGE_NAME)
            print(f"Moving files to: {cdk_dir}")

            if os.path.exists(package_dir):
                os.makedirs(cdk_dir, exist_ok=True)
                for item in os.listdir(package_dir):
                    src = os.path.join(package_dir, item)
                    dst = os.path.join(cdk_dir, item)
                    if os.path.isdir(src):
                        shutil.copytree(src, dst)
                    else:
                        shutil.copy2(src, dst)
            else:
                # No package directory, move everything
                os.makedirs(cdk_dir, exist_ok=True)
                for item in os.listdir(temp_dir):
                    src = os.path.join(temp_dir, item)
                    dst = os.path.join(cdk_dir, item)
                    if os.path.isdir(src):
                        shutil.copytree(src, dst)
                    else:
                        shutil.copy2(src, dst)

            # Cleanup
            print(f"Cleaning up temporary directory: {temp_dir}")
            shutil.rmtree(temp_dir)

        # Cleanup
        if os.path.exists(tar_file):
            print(f"Removing tarball: {tar_file}")
            os.remove(tar_file)

        # Create a metadata file for tracking the installed version
        metadata_path = os.path.join(
            node_modules_dir, CDK_PACKAGE_NAME, "metadata.json"
        )
        with open(metadata_path, "w") as f:
            json.dump(
                {
                    "cdk_version": version,
                    "installation_date": datetime.datetime.now().isoformat(),
                    "build_method": "download_cdk.py",
                },
                f,
                indent=2,
            )

        print(f"AWS CDK version {version} successfully downloaded and installed")

        # Verify the installed version
        package_json_path = os.path.join(
            node_modules_dir, CDK_PACKAGE_NAME, "package.json"
        )
        if os.path.exists(package_json_path):
            with open(package_json_path, "r") as f:
                package_data = json.load(f)
                installed_version = package_data.get("version")
                print(f"Verified installed CDK version: {installed_version}")

                if installed_version != version:
                    print(
                        f"WARNING: Installed version {installed_version} doesn't match requested version {version}"
                    )

        # Check if bin directory and CDK script exist
        bin_dir = os.path.join(node_modules_dir, CDK_PACKAGE_NAME, "bin")
        if not os.path.exists(bin_dir):
            print(f"ERROR: AWS CDK bin directory not found at {bin_dir}")
            return False

        # Check for cdk script in the bin directory
        for script_name in ["cdk", "cdk.js", "cdk.cmd"]:
            script_path = os.path.join(bin_dir, script_name)
            if os.path.exists(script_path):
                print(f"Found CDK script: {script_path}")
                break
        else:
            print("ERROR: No CDK scripts found in bin directory")
            return False

        return True

    except Exception as e:
        print(f"ERROR: Failed to download and bundle AWS CDK: {e}")
        import traceback

        traceback.print_exc()
        return False


def update_version_file(version):
    """Update version.py with the current version."""
    version_file = os.path.join("aws_cdk_cli", "version.py")
    if os.path.exists(version_file):
        with open(version_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Use regex to replace version strings
        import re

        # Update the __version__ variable
        content = re.sub(
            r'__version__ = "[^"]+"', f'__version__ = "{version}"', content
        )
        # Update the __cdk_version__ variable
        content = re.sub(
            r'__cdk_version__ = (?:__version__|"[^"]+")',
            f'__cdk_version__ = "{version}"',
            content,
        )

        with open(version_file, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Updated version.py with version {version}")


if __name__ == "__main__":
    # Check if CDK_VERSION is set
    if "CDK_VERSION" not in os.environ:
        print("ERROR: CDK_VERSION environment variable not set")
        print("Please set it before running this script")
        sys.exit(1)

    version = os.environ["CDK_VERSION"]
    print(f"Downloading AWS CDK version {version}")

    # Run the download_cdk function
    success = download_cdk()

    if not success:
        print("ERROR: Failed to download CDK")
        sys.exit(1)

    # Update the version file
    update_version_file(version)

    print(f"Successfully downloaded CDK version {version}")
