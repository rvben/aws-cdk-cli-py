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
NODE_DIST_INDEX_URL = "https://nodejs.org/dist/latest-v{major}.x/"


def read_node_version(constants_text: str) -> str:
    """Return the ``NODE_VERSION`` value defined in constants.py source text.

    Raises ``ValueError`` if the assignment is absent, so a renamed/moved
    constant fails loudly instead of silently yielding an empty version.
    """
    match = re.search(r'^NODE_VERSION\s*=\s*"([^"]+)"', constants_text, re.MULTILINE)
    if not match:
        raise ValueError("NODE_VERSION assignment not found in constants.py")
    return match.group(1)


def parse_latest_patch(index_html: str) -> str:
    """Return the highest ``node-vX.Y.Z`` version listed in a dist directory index.

    The nodejs.org ``latest-vXX.x/`` page links files like
    ``node-v22.22.3-linux-x64.tar.gz``. Raises ``ValueError`` if no such entry is
    present, so a changed page format surfaces as an error rather than a silent
    "no update".
    """
    versions = re.findall(r"node-v(\d+)\.(\d+)\.(\d+)", index_html)
    if not versions:
        raise ValueError("No node-vX.Y.Z entries found in the dist index")
    major, minor, patch = max((int(a), int(b), int(c)) for a, b, c in versions)
    return f"{major}.{minor}.{patch}"


def detect_latest_patch(major: int, opener=urllib.request.urlopen) -> str:
    """Return the latest Node.js patch for ``major`` from nodejs.org.

    ``opener`` is injectable so the network call can be exercised in tests.
    """
    url = NODE_DIST_INDEX_URL.format(major=major)
    with opener(url, timeout=30) as response:
        index_html = response.read().decode("utf-8")
    return parse_latest_patch(index_html)


def read_current_node_version() -> str:
    """Return the currently bundled Node.js version from constants.py on disk."""
    with open(CONSTANTS_FILE) as f:
        return read_node_version(f.read())


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
            print("Check available versions at https://nodejs.org/dist/")
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
    args = sys.argv[1:]

    # Query modes print a single version to stdout so callers (make targets, the
    # workflow) can capture it directly. Errors propagate so a failure is visible
    # rather than yielding an empty string.
    if args == ["--current"]:
        print(read_current_node_version())
        return
    if args == ["--latest"]:
        major = int(read_current_node_version().split(".")[0])
        print(detect_latest_patch(major))
        return

    if len(args) != 1:
        print("Usage: python scripts/update_node_version.py <version>")
        print("       python scripts/update_node_version.py --current")
        print("       python scripts/update_node_version.py --latest")
        print("Example: python scripts/update_node_version.py 22.15.0")
        sys.exit(1)

    version = args[0]

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
    print(f'  NODE_VERSION = "{version}"')
    print("  NODE_CHECKSUMS for all platforms")
    print()
    print("Next steps:")
    print("  1. Run 'make build' to rebuild with new Node.js version")
    print("  2. Test the package")
    print("  3. Commit the changes")


if __name__ == "__main__":
    main()
