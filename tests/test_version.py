"""Version-source consistency check."""

import json
import re
import sys
from pathlib import Path

import flyan

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib


def test_version_resolves_from_installed_metadata() -> None:
    assert flyan.__version__
    assert flyan.__version__ != "0.0.0+unknown"
    assert re.fullmatch(r"\d+\.\d+\.\d+.*", flyan.__version__)


def test_pyproject_and_manifest_versions_match() -> None:
    """pyproject.toml and .release-please-manifest.json are the two release-please writes."""
    root = Path(__file__).resolve().parents[1]
    pyproject = tomllib.loads((root / "pyproject.toml").read_text())
    manifest = json.loads((root / ".release-please-manifest.json").read_text())

    assert pyproject["project"]["version"] == manifest["."]
