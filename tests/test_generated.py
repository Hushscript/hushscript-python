from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from hushscript import ERROR_CATALOG, HINTS, OPERATION_SCOPES

if TYPE_CHECKING:
    from types import ModuleType

ROOT = Path(__file__).resolve().parent.parent
SPEC = json.loads((ROOT / "openapi.json").read_text(encoding="utf-8"))
HTTP_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")


def _load_generator() -> ModuleType:
    location = importlib.util.spec_from_file_location("generate", ROOT / "scripts" / "generate.py")
    assert location is not None
    assert location.loader is not None
    module = importlib.util.module_from_spec(location)
    location.loader.exec_module(module)
    return module


GENERATOR = _load_generator()


def test_catalog_carries_every_entry_of_the_committed_spec() -> None:
    assert len(ERROR_CATALOG) == len(SPEC["x-error-catalog"])
    assert ERROR_CATALOG["insufficient_balance"].code == 3001
    assert ERROR_CATALOG["insufficient_balance"].status == 402


def test_scope_map_has_every_operation_that_declares_a_scope() -> None:
    declared = [
        f"{method.upper()} {path}"
        for path, operations in SPEC["paths"].items()
        for method, operation in operations.items()
        if method in HTTP_METHODS and operation.get("x-required-scope")
    ]
    assert sorted(OPERATION_SCOPES) == sorted(declared)
    assert OPERATION_SCOPES["GET /v1/account"] == "account:read"


def test_every_hint_slug_of_spec_9_3_is_present() -> None:
    slugs = {
        "unauthorized",
        "pat_scope_missing",
        "insufficient_balance",
        "rate_limited",
        "too_many_active_jobs",
        "agent_purchase_capped",
        "agent_pack_locked",
        "pat_purchase_requires_app",
        "pat_purchase_requires_authentication",
        "no_default_card",
        "unsupported_media",
        "duration_unreadable",
        "duration_out_of_range",
        "size_out_of_range",
        "daily_limit",
        "policy_version_stale",
        "wrong_state",
        "resume_file_mismatch",
        "resume_file_required",
        "resume_job_missing",
        "stream_size_mismatch",
        "default_card_required",
    }
    assert set(HINTS) == slugs
    assert "not the file the upload started with" in HINTS["resume_file_mismatch"]


@pytest.mark.parametrize(
    ("name", "emitter"), [("catalog", "emit_catalog"), ("scopes", "emit_scopes")]
)
def test_committed_tables_match_a_fresh_emit(name: str, emitter: str) -> None:
    emitted = getattr(GENERATOR, emitter)(SPEC)
    committed = (ROOT / "src" / "hushscript" / "generated" / f"{name}.py").read_text(
        encoding="utf-8"
    )
    assert emitted == committed


def test_emit_catalog_rejects_duplicate_slugs_and_bad_codes() -> None:
    entry = {"slug": "a", "code": 1, "status": 400, "meaning": "m"}
    with pytest.raises(ValueError, match="duplicate error slug a"):
        GENERATOR.emit_catalog({"x-error-catalog": [entry, entry]})
    with pytest.raises(TypeError, match="code must be an integer"):
        GENERATOR.emit_catalog({"x-error-catalog": [{**entry, "code": "1"}]})
    with pytest.raises(TypeError, match="meaning must be a non-empty string"):
        GENERATOR.emit_catalog({"x-error-catalog": [{**entry, "meaning": ""}]})
    with pytest.raises(ValueError, match="no x-error-catalog"):
        GENERATOR.emit_catalog({})


def test_emit_hints_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="empty"):
        GENERATOR.emit_hints({})
    with pytest.raises(TypeError, match="non-empty string"):
        GENERATOR.emit_hints({"a": ""})


def test_generator_declares_a_missing_path_parameter() -> None:
    spec = {
        "paths": {"/v1/x/{id}": {"post": {}, "get": {"parameters": [{"in": "path", "name": "id"}]}}}
    }
    patched = GENERATOR.declare_path_parameters(spec)
    assert patched == ["POST /v1/x/{id}"]
    assert spec["paths"]["/v1/x/{id}"]["post"]["parameters"][0]["name"] == "id"


def test_every_operation_of_the_spec_is_generated() -> None:
    operation_ids = sorted(
        operation["operationId"]
        for item in SPEC["paths"].values()
        for method, operation in item.items()
        if method in HTTP_METHODS
    )
    generated = sorted(
        path.stem
        for path in (ROOT / "src" / "hushscript" / "generated" / "api" / "default").glob("*.py")
        if path.stem != "__init__"
    )
    assert len(operation_ids) == 38
    assert generated == operation_ids
    assert "claim_agent_account" in generated
