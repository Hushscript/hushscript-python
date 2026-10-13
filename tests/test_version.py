from __future__ import annotations

import json
import sys
from pathlib import Path

from hushscript import __version__

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

ROOT = Path(__file__).resolve().parent.parent


def test_the_version_matches_pyproject_and_the_release_manifest() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / ".release-please-manifest.json").read_text(encoding="utf-8"))
    assert __version__ == pyproject["project"]["version"] == manifest["."]
