"""
Packaging-configuration guards.

These lock in decisions about what the built distribution declares as
shippable data, independent of any one build environment.
"""

import sys
from pathlib import Path

import pytest

if sys.version_info >= (3, 11):
    import tomllib
else:  # tomllib is stdlib only from 3.11; the guard still runs on newer CI legs
    pytest.skip("tomllib requires Python 3.11+", allow_module_level=True)


def _package_data() -> list[str]:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text())
    return pyproject["tool"]["setuptools"]["package-data"]["aws_cdk_cli"]


def test_node_binaries_not_declared_as_package_data():
    """The Node.js runtime is downloaded on first run, never bundled (the
    published sdist contains zero node_binaries entries). Declaring
    node_binaries as package-data ships nothing, but in an editable install it
    materializes a site-packages/aws_cdk_cli/ data directory with no
    __init__.py, which shadows the real package and breaks imports. Keep it out.
    """
    globs = _package_data()
    offending = [g for g in globs if "node_binaries" in g]
    assert not offending, (
        f"node_binaries must not be package-data (it is downloaded at runtime, "
        f"not shipped, and shadows editable installs): {offending}"
    )


def test_bundled_cdk_remains_package_data():
    """The AWS CDK JavaScript (node_modules) IS bundled and must stay shipped."""
    globs = _package_data()
    assert any("node_modules" in g for g in globs), globs
