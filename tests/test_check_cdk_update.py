"""
Unit tests for the CDK update checker (scripts/check_cdk_update.py).

These tests exercise the exact production code path used by the
"Check for AWS CDK Updates" workflow, so they guard against the class of
silent failure that previously let the checker report "no update" for weeks.
"""

import pytest

from scripts.check_cdk_update import (
    decide,
    fetch_npm_payload,
    is_update_available,
    main,
    parse_npm_version,
    select_current_version,
    write_github_output,
)


class TestSelectCurrentVersion:
    """Selecting the current published CDK version from git tags."""

    def test_ignores_pep440_post_release_tags(self):
        """A PEP 440 post-release tag (e.g. v2.1117.0.post1) is not valid semver
        and must not become the baseline, or every comparison against npm breaks.
        """
        tags = ["v2.1116.0", "v2.1117.0", "v2.1117.0.post1"]
        assert select_current_version(tags) == "2.1117.0"

    def test_picks_highest_by_semver_not_lexically(self):
        """v2.1117.0 > v2.199.0 numerically, even though '199' sorts after '1117'
        as a string. Lexical sorting would pick the wrong tag.
        """
        tags = ["v2.199.0", "v2.1117.0", "v2.1110.0"]
        assert select_current_version(tags) == "2.1117.0"

    def test_unsorted_input(self):
        """Tag order from git is not guaranteed; selection must not depend on it."""
        tags = ["v2.1110.0", "v2.1117.0", "v2.1116.0", "v2.1115.1"]
        assert select_current_version(tags) == "2.1117.0"

    def test_no_valid_tags_returns_zero_version(self):
        """With no semver-valid tags, fall back to 0.0.0 so the first real
        CDK version is always detected as an update.
        """
        assert select_current_version([]) == "0.0.0"
        assert select_current_version(["not-a-version", "v2.0.0.post3"]) == "0.0.0"


class TestParseNpmVersion:
    """Extracting the latest version from the npm registry response."""

    def test_extracts_version_field(self):
        """The npm registry 'latest' document carries the version under 'version'."""
        payload = '{"name": "aws-cdk", "version": "2.1126.0", "dist": {}}'
        assert parse_npm_version(payload) == "2.1126.0"

    def test_malformed_json_raises(self):
        """A truncated/empty body must raise, never silently mean 'no update'."""
        with pytest.raises(ValueError):
            parse_npm_version("")
        with pytest.raises(ValueError):
            parse_npm_version("not json")

    def test_missing_version_key_raises(self):
        """Valid JSON without a usable 'version' must raise, not return None."""
        with pytest.raises(ValueError):
            parse_npm_version('{"name": "aws-cdk"}')
        with pytest.raises(ValueError):
            parse_npm_version('{"version": ""}')

    def test_non_object_payload_raises(self):
        """A JSON array/string is not a registry document and must raise."""
        with pytest.raises(ValueError):
            parse_npm_version('["2.1126.0"]')


class TestIsUpdateAvailable:
    """Comparing the current baseline against the latest npm version."""

    def test_newer_latest_is_an_update(self):
        assert is_update_available("2.1117.0", "2.1126.0") is True

    def test_equal_is_not_an_update(self):
        assert is_update_available("2.1126.0", "2.1126.0") is False

    def test_older_latest_is_not_an_update(self):
        assert is_update_available("2.1126.0", "2.1117.0") is False

    def test_invalid_version_raises(self):
        """Garbage in must raise (loud), not be treated as 'no update'."""
        with pytest.raises(ValueError):
            is_update_available("2.1117.0.post1", "2.1126.0")


class TestDecide:
    """The end-to-end decision the workflow consumes."""

    def test_regression_post_tag_does_not_mask_new_release(self):
        """The exact bug: a v2.1117.0.post1 tag must not hide that npm has
        moved on to 2.1126.0. decide() must report the update.
        """
        tags = ["v2.1116.0", "v2.1117.0", "v2.1117.0.post1"]
        npm_payload = '{"version": "2.1126.0"}'
        result = decide(tags, npm_payload)
        assert result == {
            "current_version": "2.1117.0",
            "latest_version": "2.1126.0",
            "has_new_version": True,
        }

    def test_up_to_date(self):
        tags = ["v2.1126.0"]
        npm_payload = '{"version": "2.1126.0"}'
        result = decide(tags, npm_payload)
        assert result["has_new_version"] is False
        assert result["current_version"] == "2.1126.0"
        assert result["latest_version"] == "2.1126.0"

    def test_malformed_npm_payload_propagates(self):
        """decide() must not swallow a malformed npm response into 'no update'."""
        with pytest.raises(ValueError):
            decide(["v2.1117.0"], "")


class TestWriteGithubOutput:
    """Rendering the GitHub Actions step outputs."""

    def test_writes_actions_output_format(self, tmp_path):
        """has_new_version must be the lowercase string the workflow compares
        against ('true'/'false'), one `name=value` line per output.
        """
        out = tmp_path / "github_output"
        write_github_output(
            {
                "current_version": "2.1117.0",
                "latest_version": "2.1126.0",
                "has_new_version": True,
            },
            str(out),
        )
        lines = out.read_text().splitlines()
        assert "current_version=2.1117.0" in lines
        assert "latest_version=2.1126.0" in lines
        assert "has_new_version=true" in lines

    def test_false_is_lowercase_string(self, tmp_path):
        out = tmp_path / "github_output"
        write_github_output(
            {
                "current_version": "2.1126.0",
                "latest_version": "2.1126.0",
                "has_new_version": False,
            },
            str(out),
        )
        assert "has_new_version=false" in out.read_text().splitlines()

    def test_appends_rather_than_truncates(self, tmp_path):
        """GITHUB_OUTPUT accumulates across steps; we must not clobber it."""
        out = tmp_path / "github_output"
        out.write_text("preexisting=1\n")
        write_github_output(
            {
                "current_version": "1.0.0",
                "latest_version": "1.0.0",
                "has_new_version": False,
            },
            str(out),
        )
        assert "preexisting=1" in out.read_text().splitlines()


class TestFetchNpmPayload:
    """Fetching the registry document over HTTP (no real network in tests)."""

    def test_decodes_response_body(self):
        class FakeResponse:
            def read(self):
                return b'{"version": "2.1126.0"}'

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        captured = {}

        def fake_opener(url, timeout=None):
            captured["url"] = url
            return FakeResponse()

        body = fetch_npm_payload(opener=fake_opener)
        assert body == '{"version": "2.1126.0"}'
        assert "aws-cdk" in captured["url"]


class TestMain:
    """The composed entry point used by `make check-cdk-update`."""

    def test_writes_outputs_and_returns_decision(self, tmp_path):
        out = tmp_path / "github_output"
        result = main(
            tags_provider=lambda: ["v2.1116.0", "v2.1117.0", "v2.1117.0.post1"],
            payload_fetcher=lambda: '{"version": "2.1126.0"}',
            github_output=str(out),
        )
        assert result["has_new_version"] is True
        assert result["current_version"] == "2.1117.0"
        assert result["latest_version"] == "2.1126.0"
        assert "has_new_version=true" in out.read_text().splitlines()

    def test_no_github_output_still_returns_decision(self):
        """Run locally (no GITHUB_OUTPUT) must not crash on file writing."""
        result = main(
            tags_provider=lambda: ["v2.1126.0"],
            payload_fetcher=lambda: '{"version": "2.1126.0"}',
            github_output=None,
        )
        assert result["has_new_version"] is False

    def test_malformed_payload_raises(self, tmp_path):
        """A broken fetch must raise out of main (red CI), never write false."""
        out = tmp_path / "github_output"
        with pytest.raises(ValueError):
            main(
                tags_provider=lambda: ["v2.1117.0"],
                payload_fetcher=lambda: "",
                github_output=str(out),
            )
