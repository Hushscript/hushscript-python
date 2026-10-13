"""The publish workflow's runner egress allowlist covers what the publish action pulls."""

from __future__ import annotations

import re
from pathlib import Path

WORKFLOW = Path(__file__).parent.parent / ".github/workflows/publish.yml"


def endpoints_of(job: str) -> set[str]:
    text = WORKFLOW.read_text(encoding="utf-8")
    start = text.index(f"\n  {job}:\n")
    following = re.search(r"\n  [a-z-]+:\n", text[start + 1 :])
    block = text[start : start + 1 + following.start()] if following else text[start:]
    match = re.search(r"allowed-endpoints: >\n((?:\s+\S+\n)+)", block)
    assert match is not None
    return set(match.group(1).split())


def test_the_publish_job_may_pull_the_action_image() -> None:
    allowed = endpoints_of("publish")
    assert {"ghcr.io:443", "pkg-containers.githubusercontent.com:443"} <= allowed
    assert "upload.pypi.org:443" in allowed
