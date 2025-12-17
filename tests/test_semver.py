"""
Unit tests for the semver_helper module.

Tests cover version parsing, comparison, and requirement satisfaction.
"""

import pytest

from aws_cdk_cli.semver_helper import (
    parse_version,
    is_valid,
    compare,
    satisfies,
    _check_single_requirement,
)


class TestParseVersion:
    """Tests for version string parsing."""

    def test_parse_basic_version(self):
        """Test parsing a basic semver version."""
        result = parse_version("1.2.3")
        assert result == (1, 2, 3, "", "")

    def test_parse_version_with_v_prefix(self):
        """Test parsing a version with v prefix."""
        result = parse_version("v1.2.3")
        assert result == (1, 2, 3, "", "")

    def test_parse_version_with_prerelease(self):
        """Test parsing a version with prerelease tag."""
        result = parse_version("1.2.3-alpha")
        assert result == (1, 2, 3, "alpha", "")

        result = parse_version("1.2.3-beta.1")
        assert result == (1, 2, 3, "beta.1", "")

        result = parse_version("1.2.3-rc.1")
        assert result == (1, 2, 3, "rc.1", "")

    def test_parse_version_with_build_metadata(self):
        """Test parsing a version with build metadata."""
        result = parse_version("1.2.3+build.123")
        assert result == (1, 2, 3, "", "build.123")

    def test_parse_version_with_prerelease_and_build(self):
        """Test parsing a version with both prerelease and build metadata."""
        result = parse_version("1.2.3-alpha+build.456")
        assert result == (1, 2, 3, "alpha", "build.456")

    def test_parse_zero_versions(self):
        """Test parsing versions with zero components."""
        assert parse_version("0.0.0") == (0, 0, 0, "", "")
        assert parse_version("0.1.0") == (0, 1, 0, "", "")
        assert parse_version("1.0.0") == (1, 0, 0, "", "")

    def test_parse_large_version_numbers(self):
        """Test parsing versions with large numbers."""
        result = parse_version("20.15.123")
        assert result == (20, 15, 123, "", "")

    def test_parse_invalid_version(self):
        """Test parsing invalid version strings."""
        assert parse_version("invalid") is None
        assert parse_version("1.2") is None
        assert parse_version("1.2.3.4") is None
        assert parse_version("a.b.c") is None
        assert parse_version("") is None


class TestIsValid:
    """Tests for version validation."""

    def test_valid_versions(self):
        """Test that valid versions return True."""
        assert is_valid("1.0.0") is True
        assert is_valid("0.0.1") is True
        assert is_valid("1.2.3-alpha") is True
        assert is_valid("v2.0.0") is True

    def test_invalid_versions(self):
        """Test that invalid versions return False."""
        assert is_valid("invalid") is False
        assert is_valid("1.2") is False
        assert is_valid("") is False


class TestCompare:
    """Tests for version comparison."""

    def test_compare_equal_versions(self):
        """Test comparing equal versions."""
        assert compare("1.0.0", "1.0.0") == 0
        assert compare("v1.0.0", "1.0.0") == 0  # v prefix should be stripped
        assert compare("0.0.1", "0.0.1") == 0

    def test_compare_major_version(self):
        """Test comparing major versions."""
        assert compare("2.0.0", "1.0.0") == 1
        assert compare("1.0.0", "2.0.0") == -1

    def test_compare_minor_version(self):
        """Test comparing minor versions."""
        assert compare("1.2.0", "1.1.0") == 1
        assert compare("1.1.0", "1.2.0") == -1

    def test_compare_patch_version(self):
        """Test comparing patch versions."""
        assert compare("1.0.2", "1.0.1") == 1
        assert compare("1.0.1", "1.0.2") == -1

    def test_compare_prerelease_precedence(self):
        """Test that prerelease versions have lower precedence."""
        # Version without prerelease is greater than version with prerelease
        assert compare("1.0.0", "1.0.0-alpha") == 1
        assert compare("1.0.0-alpha", "1.0.0") == -1

    def test_compare_prerelease_strings(self):
        """Test comparing prerelease strings."""
        # String comparison for prereleases
        assert compare("1.0.0-beta", "1.0.0-alpha") == 1
        assert compare("1.0.0-alpha", "1.0.0-beta") == -1

    def test_compare_build_metadata_ignored(self):
        """Test that build metadata is ignored in comparisons."""
        assert compare("1.0.0+build1", "1.0.0+build2") == 0
        assert compare("1.0.0+abc", "1.0.0") == 0

    def test_compare_invalid_version_raises(self):
        """Test that comparing invalid versions raises ValueError."""
        with pytest.raises(ValueError):
            compare("invalid", "1.0.0")
        with pytest.raises(ValueError):
            compare("1.0.0", "invalid")


class TestSatisfies:
    """Tests for requirement satisfaction."""

    def test_exact_version_match(self):
        """Test exact version matching."""
        assert satisfies("1.0.0", "1.0.0") is True
        assert satisfies("1.0.0", "1.0.1") is False

    def test_greater_than(self):
        """Test greater than comparison."""
        assert satisfies("2.0.0", ">1.0.0") is True
        assert satisfies("1.0.0", ">1.0.0") is False
        assert satisfies("0.9.0", ">1.0.0") is False

    def test_less_than(self):
        """Test less than comparison."""
        assert satisfies("0.9.0", "<1.0.0") is True
        assert satisfies("1.0.0", "<1.0.0") is False
        assert satisfies("2.0.0", "<1.0.0") is False

    def test_greater_than_or_equal(self):
        """Test greater than or equal comparison."""
        assert satisfies("2.0.0", ">=1.0.0") is True
        assert satisfies("1.0.0", ">=1.0.0") is True
        assert satisfies("0.9.0", ">=1.0.0") is False

    def test_less_than_or_equal(self):
        """Test less than or equal comparison."""
        assert satisfies("0.9.0", "<=1.0.0") is True
        assert satisfies("1.0.0", "<=1.0.0") is True
        assert satisfies("2.0.0", "<=1.0.0") is False

    def test_equals_operator(self):
        """Test explicit equals operator."""
        assert satisfies("1.0.0", "=1.0.0") is True
        assert satisfies("1.0.1", "=1.0.0") is False

    def test_caret_range(self):
        """Test caret (^) range - compatible with version."""
        # ^1.2.3 allows >=1.2.3 <2.0.0
        assert satisfies("1.2.3", "^1.2.3") is True
        assert satisfies("1.9.9", "^1.2.3") is True
        assert satisfies("1.2.4", "^1.2.3") is True
        assert satisfies("2.0.0", "^1.2.3") is False
        assert satisfies("1.2.2", "^1.2.3") is False

    def test_caret_range_zero_major(self):
        """Test caret range with 0.x versions."""
        # ^0.2.3 allows >=0.2.3 <0.3.0 when major is 0
        assert satisfies("0.2.3", "^0.2.3") is True
        assert satisfies("0.2.9", "^0.2.3") is True
        assert satisfies("0.3.0", "^0.2.3") is False
        assert satisfies("0.2.2", "^0.2.3") is False

    def test_caret_range_zero_major_and_minor(self):
        """Test caret range with 0.0.x versions."""
        # ^0.0.3 allows only 0.0.3
        assert satisfies("0.0.3", "^0.0.3") is True
        assert satisfies("0.0.4", "^0.0.3") is False
        assert satisfies("0.0.2", "^0.0.3") is False

    def test_tilde_range(self):
        """Test tilde (~) range - approximately equivalent to."""
        # ~1.2.3 allows >=1.2.3 <1.3.0
        assert satisfies("1.2.3", "~1.2.3") is True
        assert satisfies("1.2.9", "~1.2.3") is True
        assert satisfies("1.3.0", "~1.2.3") is False
        assert satisfies("1.2.2", "~1.2.3") is False

    def test_or_conditions(self):
        """Test OR (||) conditions."""
        # Either 1.x or 2.x
        assert satisfies("1.5.0", "^1.0.0 || ^2.0.0") is True
        assert satisfies("2.5.0", "^1.0.0 || ^2.0.0") is True
        assert satisfies("3.0.0", "^1.0.0 || ^2.0.0") is False

    def test_and_conditions(self):
        """Test AND (space-separated) conditions."""
        # Between 1.0.0 and 2.0.0
        assert satisfies("1.5.0", ">=1.0.0 <2.0.0") is True
        assert satisfies("1.0.0", ">=1.0.0 <2.0.0") is True
        assert satisfies("2.0.0", ">=1.0.0 <2.0.0") is False
        assert satisfies("0.9.0", ">=1.0.0 <2.0.0") is False


class TestCheckSingleRequirement:
    """Tests for internal single requirement checking."""

    def test_invalid_caret_requirement(self):
        """Test caret with invalid version."""
        assert _check_single_requirement("1.0.0", "^invalid") is False

    def test_invalid_tilde_requirement(self):
        """Test tilde with invalid version."""
        assert _check_single_requirement("1.0.0", "~invalid") is False

    def test_invalid_version(self):
        """Test checking invalid version against requirement."""
        assert _check_single_requirement("invalid", "^1.0.0") is False
        assert _check_single_requirement("invalid", "~1.0.0") is False


class TestNodeVersionCompatibility:
    """Tests for real-world Node.js version compatibility scenarios."""

    def test_node_version_requirements(self):
        """Test Node.js version requirement patterns used in CDK."""
        # CDK typically requires Node.js >=18.0.0
        requirement = ">=18.0.0"

        assert satisfies("20.0.0", requirement) is True
        assert satisfies("18.0.0", requirement) is True
        assert satisfies("16.0.0", requirement) is False
        assert satisfies("22.11.0", requirement) is True  # Current Node.js LTS

    def test_node_version_with_prerelease(self):
        """Test Node.js prerelease version handling."""
        # Node.js sometimes has nightly/canary releases
        assert satisfies("20.0.0-nightly", ">=20.0.0") is False  # Prerelease has lower precedence
        assert satisfies("20.0.0", ">=20.0.0") is True
