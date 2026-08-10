#!/usr/bin/env python3
"""Check whether a newer AWS CDK version is available on npm.

This is the production code path for the "Check for AWS CDK Updates" workflow.
It deliberately fails loudly: any error (network, malformed response, invalid
version) raises instead of being swallowed into a "no update" result, so a
broken check surfaces as a red CI run rather than weeks of silent drift.

The baseline it compares against is the version published on PyPI, not the
newest git tag. A tag records "done" the moment it exists, so a run that tagged
and then failed to publish would make that version invisible to every later
run, permanently. PyPI is the state this package exists to keep in sync with,
so a release that never landed there is simply retried on the next run.
"""

import json
import os
import sys
import urllib.error
import urllib.request

from aws_cdk_cli.semver_helper import compare, is_valid

NPM_REGISTRY_URL = "https://registry.npmjs.org/aws-cdk/latest"
PYPI_URL = "https://pypi.org/pypi/aws-cdk-cli/json"

# The baseline used when PyPI has no release for this project at all.
UNPUBLISHED = "0.0.0"


def parse_npm_version(payload: str) -> str:
    """Return the ``version`` field from an npm registry ``latest`` document.

    Raises ``ValueError`` on any malformed input (not JSON, not an object,
    missing or empty ``version``) so a broken response fails the run loudly
    instead of being mistaken for "no update available".
    """
    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError(f"npm registry response is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("npm registry response is not a JSON object")

    version = data.get("version")
    if not isinstance(version, str) or not version:
        raise ValueError("npm registry response is missing a 'version' field")

    return version


def parse_pypi_version(payload: str | None) -> str:
    """Return the released version from a PyPI ``/pypi/<name>/json`` document.

    ``None`` means PyPI has no such project (a 404), which is the correct
    first-release path and maps to ``0.0.0``. Every other malformed input
    raises, so a broken response can never be mistaken for "nothing published
    yet" and cause a republish of versions that are already live.

    A ``.postN`` suffix marks a re-publish of the same upstream CDK version, so
    it is stripped to leave the upstream version the comparison needs.
    """
    if payload is None:
        return UNPUBLISHED

    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError(f"PyPI response is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("PyPI response is not a JSON object")

    info = data.get("info")
    if not isinstance(info, dict):
        raise ValueError("PyPI response is missing an 'info' object")

    version = info.get("version")
    if not isinstance(version, str) or not version:
        raise ValueError("PyPI response is missing an 'info.version' field")

    version = version.split(".post", 1)[0]
    if not is_valid(version):
        raise ValueError(f"PyPI reported a version that is not semver: {version!r}")

    return version


def is_update_available(current: str, latest: str) -> bool:
    """Return ``True`` if ``latest`` is a newer version than ``current``.

    Raises ``ValueError`` (via ``compare``) when either version is invalid, so
    a bad baseline or response can never be misread as "no update available".
    """
    return compare(latest, current) > 0


def decide(pypi_payload: str | None, npm_payload: str) -> dict:
    """Decide whether a CDK update needs to be released.

    Composes the pieces the workflow depends on into a single result so tests
    can exercise the exact production decision. Any failure (malformed payload,
    invalid version) propagates as an exception rather than a false negative.
    """
    current = parse_pypi_version(pypi_payload)
    latest = parse_npm_version(npm_payload)
    return {
        "current_version": current,
        "latest_version": latest,
        "has_new_version": is_update_available(current, latest),
    }


def fetch_pypi_payload(
    url: str = PYPI_URL, opener=urllib.request.urlopen
) -> str | None:
    """Fetch the PyPI project document, or ``None`` when the project is absent.

    Only a 404 maps to ``None``. Every other HTTP status and network error
    propagates, so a PyPI outage fails the run instead of reading as "nothing
    published yet".

    ``opener`` is injectable so the network call can be exercised in tests.
    """
    try:
        with opener(url, timeout=30) as response:
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def fetch_npm_payload(
    url: str = NPM_REGISTRY_URL, opener=urllib.request.urlopen
) -> str:
    """Fetch the npm registry ``latest`` document for aws-cdk as text.

    ``opener`` is injectable so the network call can be exercised in tests.
    """
    with opener(url, timeout=30) as response:
        return response.read().decode("utf-8")


def write_github_output(result: dict, path: str) -> None:
    """Append the decision as GitHub Actions step outputs (``name=value``)."""
    lines = [
        f"current_version={result['current_version']}",
        f"latest_version={result['latest_version']}",
        f"has_new_version={'true' if result['has_new_version'] else 'false'}",
    ]
    with open(path, "a") as handle:
        handle.write("\n".join(lines) + "\n")


def main(
    *,
    pypi_fetcher=fetch_pypi_payload,
    payload_fetcher=fetch_npm_payload,
    github_output: str | None = None,
) -> dict:
    """Run the check end to end and return the decision.

    Writes GitHub Actions outputs when ``github_output`` (or ``$GITHUB_OUTPUT``)
    is set. Errors propagate so a failed check is a red run, never a false
    "no update".
    """
    if github_output is None:
        github_output = os.environ.get("GITHUB_OUTPUT")

    result = decide(pypi_fetcher(), payload_fetcher())

    if result["has_new_version"]:
        print(
            f"New AWS CDK version available: "
            f"{result['current_version']} -> {result['latest_version']}"
        )
    else:
        print(f"AWS CDK is up to date ({result['current_version']})")

    if github_output:
        write_github_output(result, github_output)

    return result


if __name__ == "__main__":
    main()
    sys.exit(0)
