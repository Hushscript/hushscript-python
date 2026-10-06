from __future__ import annotations

import os

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
