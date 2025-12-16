#!/usr/bin/env python3
"""
Update Node.js version and checksums in constants.py.

This script fetches the SHA256 checksums from nodejs.org and updates
constants.py with both the new version and matching checksums atomically.

Usage:
    python scripts/update_node_version.py 22.15.0
    python scripts/update_node_version.py v22.15.0  # 'v' prefix is stripped
"""

import sys
import re
import urllib.request
import urllib.error

# Platforms we support (maps to Node.js filename patterns)
PLATFORMS = {
    ("darwin", "x86_64"): "darwin-x64",
    ("darwin", "arm64"): "darwin-arm64",
    ("linux", "x86_64"): "linux-x64",
    ("linux", "arm64"): "linux-arm64",
    ("windows", "x86_64"): "win-x64",
}

CONSTANTS_FILE = "aws_cdk_cli/constants.py"


def fetch_checksums(version: str) -> dict:
    """Fetch SHA256 checksums from nodejs.org for the given version."""
    url = f"https://nodejs.org/dist/v{version}/SHASUMS256.txt"
    print(f"Fetching checksums from {url}")

    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            content = response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"Error: Node.js version {version} not found")
            print(f"Check available versions at https://nodejs.org/dist/")
            sys.exit(1)
        raise

    checksums = {}
    for line in content.strip().split("\n"):
        if not line.strip():
            continue
        # Format: "checksum  filename"
        parts = line.split()
        if len(parts) >= 2:
            checksum, filename = parts[0], parts[1]
            checksums[filename] = checksum

    return checksums


def extract_platform_checksums(checksums: dict, version: str) -> dict:
    """Extract checksums for our supported platforms."""
    result = {
        "darwin": {},
        "linux": {},
        "windows": {},
    }

    missing = []
    for (system, machine), node_platform in PLATFORMS.items():
        if system == "windows":
            filename = f"node-v{version}-{node_platform}.zip"
        else:
            filename = f"node-v{version}-{node_platform}.tar.gz"

        if filename in checksums:
            result[system][machine] = checksums[filename]
        else:
            missing.append(f"{system}-{machine} ({filename})")

    if missing:
        print(f"Error: Missing checksums for platforms: {', '.join(missing)}")
        print("Available files:")
        for f in sorted(checksums.keys()):
            if "node-v" in f:
                print(f"  {f}")
        sys.exit(1)

    return result


def update_constants_file(version: str, checksums: dict) -> None:
    """Update constants.py with new version and checksums."""
    with open(CONSTANTS_FILE, "r") as f:
        content = f.read()

    # Update NODE_VERSION
    content = re.sub(
        r'^NODE_VERSION = "[^"]+"',
        f'NODE_VERSION = "{version}"',
        content,
        flags=re.MULTILINE,
    )

    # Build new checksums dict string
    checksums_str = "NODE_CHECKSUMS = {\n"
    for system in ["darwin", "linux", "windows"]:
        checksums_str += f'    "{system}": {{\n'
        for machine, checksum in sorted(checksums[system].items()):
            checksums_str += f'        "{machine}": "{checksum}",\n'
        checksums_str += "    },\n"
    checksums_str += "}"

    # Replace NODE_CHECKSUMS block (matches nested dict structure)
    content = re.sub(
        r"^NODE_CHECKSUMS = \{.*?\n\}",
        checksums_str,
        content,
        flags=re.MULTILINE | re.DOTALL,
    )

    with open(CONSTANTS_FILE, "w") as f:
        f.write(content)


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/update_node_version.py <version>")
        print("Example: python scripts/update_node_version.py 22.15.0")
        sys.exit(1)

    version = sys.argv[1]

    # Strip 'v' prefix if present
    if version.startswith("v"):
        version = version[1:]

    # Validate version format
    if not re.match(r"^\d+\.\d+\.\d+$", version):
        print(f"Error: Invalid version format: {version}")
        print("Version must be in format X.Y.Z (e.g., 22.15.0)")
        sys.exit(1)

    print(f"Updating Node.js to version {version}")

    # Fetch checksums from nodejs.org
    all_checksums = fetch_checksums(version)

    # Extract checksums for our platforms
    platform_checksums = extract_platform_checksums(all_checksums, version)

    # Update constants.py
    update_constants_file(version, platform_checksums)

    print(f"Updated {CONSTANTS_FILE} with:")
    print(f"  NODE_VERSION = \"{version}\"")
    print("  NODE_CHECKSUMS for all platforms")
    print()
    print("Next steps:")
    print("  1. Run 'make build' to rebuild with new Node.js version")
    print("  2. Test the package")
    print("  3. Commit the changes")


if __name__ == "__main__":
    main()
