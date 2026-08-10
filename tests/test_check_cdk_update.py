"""
Unit tests for the CDK update checker (scripts/check_cdk_update.py).

These tests exercise the exact production code path used by the
"Check for AWS CDK Updates" workflow, so they guard against the class of
silent failure that previously let the checker report "no update" for weeks.
"""

import urllib.error

import pytest

from scripts.check_cdk_update import (
    decide,
    fetch_npm_payload,
    fetch_pypi_payload,
    is_update_available,
    main,
    parse_npm_version,
    parse_pypi_version,
    write_github_output,
)


class FakeResponse:
    """Minimal stand-in for the object ``urlopen`` yields."""

    def __init__(self, body: bytes):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def http_error(code: int):
    return urllib.error.HTTPError(
        url="https://pypi.org/pypi/aws-cdk-cli/json",
        code=code,
        msg="error",
        hdrs=None,
        fp=None,
    )


class TestParsePypiVersion:
    """Reading the already-released version from the PyPI project document."""

    def test_extracts_info_version(self):
        payload = '{"info": {"version": "2.1117.0"}, "releases": {}}'
        assert parse_pypi_version(payload) == "2.1117.0"

    def test_strips_post_release_suffix(self):
        """A .postN release republishes the same upstream CDK version, so the
        baseline is the upstream version underneath it.
        """
        payload = '{"info": {"version": "2.1117.0.post1"}}'
        assert parse_pypi_version(payload) == "2.1117.0"

    def test_absent_project_is_the_unpublished_baseline(self):
        """A 404 (mapped to None by the fetcher) means nothing is published
        yet, which is the correct first-release path.
        """
        assert parse_pypi_version(None) == "0.0.0"

    def test_malformed_json_raises(self):
        """A truncated/empty body must raise, never read as 'nothing published'."""
        with pytest.raises(ValueError):
            parse_pypi_version("")
        with pytest.raises(ValueError):
            parse_pypi_version("not json")

    def test_missing_info_or_version_raises(self):
        with pytest.raises(ValueError):
            parse_pypi_version('{"releases": {}}')
        with pytest.raises(ValueError):
            parse_pypi_version('{"info": {}}')
        with pytest.raises(ValueError):
            parse_pypi_version('{"info": {"version": ""}}')

    def test_non_semver_version_raises(self):
        """A version PyPI reports that cannot be compared must fail loudly
        rather than silently become the baseline.
        """
        with pytest.raises(ValueError):
            parse_pypi_version('{"info": {"version": "not-a-version"}}')


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

    def test_compares_numerically_not_lexically(self):
        """2.1117.0 > 2.199.0 numerically, though '199' sorts after '1117' as a
        string. Lexical comparison would skip 918 releases.
        """
        assert is_update_available("2.199.0", "2.1117.0") is True
        assert is_update_available("2.1117.0", "2.199.0") is False

    def test_invalid_version_raises(self):
        """Garbage in must raise (loud), not be treated as 'no update'."""
        with pytest.raises(ValueError):
            is_update_available("2.1117.0.post1", "2.1126.0")


class TestFetchPypiPayload:
    """Only a 404 may be read as "not published"."""

    def test_returns_body(self):
        captured = {}

        def fake_opener(url, timeout=None):
            captured["url"] = url
            return FakeResponse(b'{"info": {"version": "2.1117.0"}}')

        assert fetch_pypi_payload(opener=fake_opener) == (
            '{"info": {"version": "2.1117.0"}}'
        )
        assert "aws-cdk-cli" in captured["url"]

    def test_404_means_not_published(self):
        def fake_opener(url, timeout=None):
            raise http_error(404)

        assert fetch_pypi_payload(opener=fake_opener) is None

    def test_server_error_propagates(self):
        """A PyPI outage must fail the run. Collapsing it to "not published"
        would make the baseline 0.0.0 and misreport every live release as
        missing.
        """
        def fake_opener(url, timeout=None):
            raise http_error(503)

        with pytest.raises(urllib.error.HTTPError):
            fetch_pypi_payload(opener=fake_opener)


class TestDecide:
    """The end-to-end decision the workflow consumes."""

    def test_regression_release_missing_from_pypi_is_retried(self):
        """The exact bug this check exists to prevent: a version that was
        tagged but never published must still be offered for release. The
        decision reads PyPI only, so a tag cannot record "done" on its behalf.
        """
        pypi_payload = '{"info": {"version": "2.1007.1"}}'
        npm_payload = '{"version": "2.1010.0"}'
        result = decide(pypi_payload, npm_payload)
        assert result == {
            "current_version": "2.1007.1",
            "latest_version": "2.1010.0",
            "has_new_version": True,
        }

    def test_post_release_does_not_mask_new_upstream_version(self):
        """A .post1 republish on PyPI must not hide that npm moved on."""
        pypi_payload = '{"info": {"version": "2.1117.0.post1"}}'
        npm_payload = '{"version": "2.1126.0"}'
        result = decide(pypi_payload, npm_payload)
        assert result["current_version"] == "2.1117.0"
        assert result["has_new_version"] is True

    def test_first_release_when_nothing_published(self):
        result = decide(None, '{"version": "2.1126.0"}')
        assert result["current_version"] == "0.0.0"
        assert result["has_new_version"] is True

    def test_up_to_date(self):
        pypi_payload = '{"info": {"version": "2.1126.0"}}'
        npm_payload = '{"version": "2.1126.0"}'
        result = decide(pypi_payload, npm_payload)
        assert result["has_new_version"] is False
        assert result["current_version"] == "2.1126.0"
        assert result["latest_version"] == "2.1126.0"

    def test_post_release_of_current_version_is_not_an_update(self):
        """A .post1 of the newest upstream version is up to date, not a
        downgrade and not a new release.
        """
        pypi_payload = '{"info": {"version": "2.1126.0.post2"}}'
        npm_payload = '{"version": "2.1126.0"}'
        assert decide(pypi_payload, npm_payload)["has_new_version"] is False

    def test_malformed_npm_payload_propagates(self):
        """decide() must not swallow a malformed npm response into 'no update'."""
        with pytest.raises(ValueError):
            decide('{"info": {"version": "2.1117.0"}}', "")

    def test_malformed_pypi_payload_propagates(self):
        with pytest.raises(ValueError):
            decide("", '{"version": "2.1126.0"}')


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
        captured = {}

        def fake_opener(url, timeout=None):
            captured["url"] = url
            return FakeResponse(b'{"version": "2.1126.0"}')

        body = fetch_npm_payload(opener=fake_opener)
        assert body == '{"version": "2.1126.0"}'
        assert "aws-cdk" in captured["url"]


class TestMain:
    """The composed entry point used by `make check-cdk-update`."""

    def test_writes_outputs_and_returns_decision(self, tmp_path):
        out = tmp_path / "github_output"
        result = main(
            pypi_fetcher=lambda: '{"info": {"version": "2.1117.0.post1"}}',
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
            pypi_fetcher=lambda: '{"info": {"version": "2.1126.0"}}',
            payload_fetcher=lambda: '{"version": "2.1126.0"}',
            github_output=None,
        )
        assert result["has_new_version"] is False

    def test_malformed_payload_raises(self, tmp_path):
        """A broken fetch must raise out of main (red CI), never write false."""
        out = tmp_path / "github_output"
        with pytest.raises(ValueError):
            main(
                pypi_fetcher=lambda: '{"info": {"version": "2.1117.0"}}',
                payload_fetcher=lambda: "",
                github_output=str(out),
            )
