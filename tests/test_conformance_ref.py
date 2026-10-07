"""The conformance ref is pinned in one file; nothing else may restate it."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
READERS = ("compose.yaml", "justfile", "scripts/generate.py", ".github/workflows/ci.yml")


def test_conformance_ref_is_a_tag_and_a_newline() -> None:
    raw = (ROOT / "conformance-ref").read_text(encoding="utf-8")
    assert re.fullmatch(r"v\d+\.\d+\.\d+\n", raw), raw


def test_no_reader_restates_the_tag() -> None:
    tag = (ROOT / "conformance-ref").read_text(encoding="utf-8").strip()
    for name in READERS:
        text = (ROOT / name).read_text(encoding="utf-8")
        assert tag not in text, f"{name} restates the conformance tag"
        assert not re.search(r"#v\d+\.\d+\.\d+", text), f"{name} pins a tag; read conformance-ref"
