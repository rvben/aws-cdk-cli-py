"""
Unit tests for the Node.js version helpers in scripts/update_node_version.py.

These cover the logic that previously lived as fragile inline shell in the
"Check for AWS CDK Updates" workflow (a `grep -oP` over the nodejs.org dist
index and a `sed` over constants.py).
"""

import pytest

from scripts.update_node_version import (
    detect_latest_patch,
    parse_latest_patch,
    read_node_version,
)


class TestReadNodeVersion:
    """Reading the currently bundled Node.js version from constants.py text."""

    def test_extracts_node_version(self):
        text = 'SYSTEM = "x"\nNODE_VERSION = "22.22.2"\nFOO = 1\n'
        assert read_node_version(text) == "22.22.2"

    def test_missing_node_version_raises(self):
        with pytest.raises(ValueError):
            read_node_version("NO_VERSION_HERE = 1\n")


class TestParseLatestPatch:
    """Extracting the latest patch from a nodejs.org dist directory listing."""

    def test_extracts_version_from_dist_index(self):
        """The latest-vXX.x directory lists files like node-v22.22.3-<plat>.tar.gz."""
        index_html = (
            '<a href="node-v22.22.3-darwin-arm64.tar.gz">...</a>\n'
            '<a href="node-v22.22.3-linux-x64.tar.gz">...</a>\n'
            '<a href="node-v22.22.3-win-x64.zip">...</a>\n'
        )
        assert parse_latest_patch(index_html) == "22.22.3"

    def test_picks_highest_when_multiple_versions_present(self):
        """Defensive: if several versions appear, return the highest by semver."""
        index_html = (
            "node-v22.9.0-linux-x64.tar.gz\n"
            "node-v22.22.3-linux-x64.tar.gz\n"
            "node-v22.10.1-linux-x64.tar.gz\n"
        )
        assert parse_latest_patch(index_html) == "22.22.3"

    def test_no_version_raises(self):
        """A page whose format changed (no node-vX.Y.Z) must raise, not return ''."""
        with pytest.raises(ValueError):
            parse_latest_patch("<html>nothing useful here</html>")


class TestDetectLatestPatch:
    """Fetching + parsing the dist index for a given major (no real network)."""

    def test_fetches_major_index_and_parses(self):
        class FakeResponse:
            def read(self):
                return b'<a href="node-v22.22.3-linux-x64.tar.gz">x</a>'

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        captured = {}

        def fake_opener(url, timeout=None):
            captured["url"] = url
            return FakeResponse()

        assert detect_latest_patch(22, opener=fake_opener) == "22.22.3"
        assert "latest-v22.x" in captured["url"]
