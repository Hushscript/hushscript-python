from __future__ import annotations

from typing import cast


def as_dict(value: object) -> dict[str, object] | None:
    """`value` as a JSON object with typed keys, or None (isinstance alone leaves them unknown)."""
    return cast("dict[str, object]", value) if isinstance(value, dict) else None


def as_list(value: object) -> list[object] | None:
    """`value` as a JSON array or tuple, or None."""
    if isinstance(value, (list, tuple)):
        return list(cast("list[object]", value))
    return None
