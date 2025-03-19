"""
Simple semantic versioning utilities without external dependencies.
Provides basic functionality for comparing semver version strings.
"""

import re


def parse_version(version_str):
    """Parse a version string into a tuple of components: (major, minor, patch, prerelease, build)"""
    # Strip leading 'v' if present
    if version_str.startswith("v"):
        version_str = version_str[1:]

    # Basic semver regex pattern
    pattern = r"^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
    match = re.match(pattern, version_str)

    if not match:
        return None

    major, minor, patch, prerelease, build = match.groups()

    # Convert numeric parts to integers
    major = int(major)
    minor = int(minor)
    patch = int(patch)

    return (major, minor, patch, prerelease or "", build or "")


def is_valid(version_str):
    """Check if a string is a valid semver version."""
    return parse_version(version_str) is not None


def compare(version1, version2):
    """
    Compare two version strings.
    Returns:
      -1 if version1 < version2
       0 if version1 == version2
       1 if version1 > version2
    """
    v1 = parse_version(version1)
    v2 = parse_version(version2)

    if v1 is None or v2 is None:
        raise ValueError(
            f"Invalid version format: {version1 if v1 is None else version2}"
        )

    # Compare major.minor.patch
    for i in range(3):
        if v1[i] < v2[i]:
            return -1
        if v1[i] > v2[i]:
            return 1

    # Equal major.minor.patch, check prerelease
    # A version with prerelease has lower precedence than one without
    if v1[3] and not v2[3]:
        return -1
    if not v1[3] and v2[3]:
        return 1

    # Both have prerelease or both don't have prerelease
    if v1[3] != v2[3]:
        # Simple string comparison for prerelease
        return -1 if v1[3] < v2[3] else 1

    # Versions are equal (build metadata doesn't affect precedence)
    return 0


def satisfies(version, requirement):
    """
    Check if a version satisfies a requirement string.
    Supports basic comparison operators: =, >, <, >=, <=, ~, ^
    Also supports range expressions with AND (space) and OR (||)
    """
    # Split OR conditions
    or_parts = requirement.split("||")

    # Check each OR part
    for or_part in or_parts:
        or_part = or_part.strip()

        # Check if all AND conditions are satisfied
        and_satisfied = True

        # Split AND conditions (just spaces between requirements)
        and_parts = or_part.split()

        for and_part in and_parts:
            and_part = and_part.strip()

            if not _check_single_requirement(version, and_part):
                and_satisfied = False
                break

        # If any OR part is fully satisfied, the whole requirement is satisfied
        if and_satisfied:
            return True

    # No OR part was fully satisfied
    return False


def _check_single_requirement(version, req):
    """Check if a version satisfies a single requirement string."""
    # Extract operator and version
    # Handle special range operators first
    if req.startswith("^"):
        # Compatible with: allow changes that don't modify the left-most non-zero digit
        req_version = req[1:]
        req_parsed = parse_version(req_version)
        if req_parsed is None:
            return False

        version_parsed = parse_version(version)
        if version_parsed is None:
            return False

        # Major must match if > 0
        if req_parsed[0] > 0:
            if version_parsed[0] != req_parsed[0]:
                return False
            return (
                compare(version, req_version) >= 0
                and version_parsed[0] == req_parsed[0]
            )

        # Minor must match if major is 0 but minor > 0
        elif req_parsed[1] > 0:
            if version_parsed[0] != 0 or version_parsed[1] != req_parsed[1]:
                return False
            return (
                compare(version, req_version) >= 0
                and version_parsed[0] == 0
                and version_parsed[1] == req_parsed[1]
            )

        # Patch must match if major and minor are 0
        else:
            return compare(version, req_version) == 0

    elif req.startswith("~"):
        # Approximately equivalent to: allow patch-level changes
        req_version = req[1:]
        req_parsed = parse_version(req_version)
        if req_parsed is None:
            return False

        version_parsed = parse_version(version)
        if version_parsed is None:
            return False

        # Major and minor must match
        if version_parsed[0] != req_parsed[0] or version_parsed[1] != req_parsed[1]:
            return False

        # Version must be >= the requirement
        return compare(version, req_version) >= 0

    # Handle comparison operators
    elif req.startswith(">="):
        return compare(version, req[2:].strip()) >= 0
    elif req.startswith("<="):
        return compare(version, req[2:].strip()) <= 0
    elif req.startswith(">"):
        return compare(version, req[1:].strip()) > 0
    elif req.startswith("<"):
        return compare(version, req[1:].strip()) < 0
    elif req.startswith("="):
        return compare(version, req[1:].strip()) == 0
    else:
        # Assume exact version match if no operator
        return compare(version, req) == 0
