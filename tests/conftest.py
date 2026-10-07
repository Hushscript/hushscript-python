from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from hypothesis import settings

TOKEN = "hsr1:eu:pat." + "0123456789abcdef" * 2 + "." + "fedcba9876543210" * 4

settings.register_profile("default", max_examples=100, database=None, deadline=None)
settings.register_profile("nightly", max_examples=1000, database=None, deadline=None)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "default"))


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("HUSHSCRIPT_TOKEN", "HUSHSCRIPT_BASE_URL", "HUSHSCRIPT_LOG"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def conformance_media() -> Path:
    """The conformance repository's media fixtures; a hard failure when they are missing, as the
    hint fixture is (`just test` mounts the checkout at CONFORMANCE_DIR)."""
    directory = os.environ.get("CONFORMANCE_DIR")
    if not directory or not (Path(directory) / "fixtures/media").is_dir():
        pytest.fail("CONFORMANCE_DIR must point at a hushscript-sdk-conformance checkout")
    return Path(directory) / "fixtures/media"


@pytest.fixture
def media_dir() -> Path:
    return conformance_media()


@pytest.fixture
def durations(media_dir: Path) -> dict[str, float]:
    parsed: dict[str, float] = json.loads((media_dir / "durations.json").read_text())
    return parsed
