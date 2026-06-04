#!/usr/bin/env python3
"""Check whether a newer AWS CDK version is available on npm.

This is the production code path for the "Check for AWS CDK Updates" workflow.
It deliberately fails loudly: any error (network, malformed response, invalid
version) raises instead of being swallowed into a "no update" result, so a
broken check surfaces as a red CI run rather than weeks of silent drift.
"""

import json
import os
import subprocess
import sys
import urllib.request

from aws_cdk_cli.semver_helper import compare, is_valid

NPM_REGISTRY_URL = "https://registry.npmjs.org/aws-cdk/latest"


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


def select_current_version(tags: list[str]) -> str:
    """Return the highest semver-valid version among ``tags``.

    Tags are the published CDK release tags (e.g. ``v2.1117.0``). Non-semver
    tags such as PEP 440 post-releases (``v2.1117.0.post1``) are ignored so a
    re-publish never poisons the baseline used to compare against npm.

    Returns ``"0.0.0"`` when no semver-valid tag is present.
    """
    best = "0.0.0"
    for tag in tags:
        version = tag[1:] if tag.startswith("v") else tag
        if not is_valid(version):
            continue
        if compare(version, best) > 0:
            best = version
    return best


def is_update_available(current: str, latest: str) -> bool:
    """Return ``True`` if ``latest`` is a newer version than ``current``.

    Raises ``ValueError`` (via ``compare``) when either version is invalid, so
    a bad baseline or response can never be misread as "no update available".
    """
    return compare(latest, current) > 0


def decide(tags: list[str], npm_payload: str) -> dict:
    """Decide whether a CDK update is available.

    Composes the pieces the workflow depends on into a single result so tests
    can exercise the exact production decision. Any failure (malformed payload,
    invalid version) propagates as an exception rather than a false negative.
    """
    current = select_current_version(tags)
    latest = parse_npm_version(npm_payload)
    return {
        "current_version": current,
        "latest_version": latest,
        "has_new_version": is_update_available(current, latest),
    }


def list_git_tags() -> list[str]:
    """Return every tag in the repository (the published CDK release tags)."""
    completed = subprocess.run(
        ["git", "tag", "--list"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


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
    tags_provider=list_git_tags,
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

    result = decide(tags_provider(), payload_fetcher())

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
