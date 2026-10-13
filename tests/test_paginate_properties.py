from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from hushscript import HushscriptError, Page
from hushscript.paginate import apaginate, paginate

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator


@pytest.mark.parametrize("asynchronous", [False, True])
@given(
    pages=st.lists(st.lists(st.integers(), max_size=10), min_size=1, max_size=10),
    terminal=st.sampled_from([None, ""]),
)
def test_pagination_is_lazy_and_preserves_every_page(
    *, asynchronous: bool, pages: list[list[int]], terminal: str | None
) -> None:
    sent: list[str | None] = []

    def fetch(cursor: str | None) -> Page[int]:
        sent.append(cursor)
        index = len(sent) - 1
        assert cursor == (None if index == 0 else f"cursor_{index}")
        return Page(pages[index], terminal if index == len(pages) - 1 else f"cursor_{index + 1}")

    async def afetch(cursor: str | None) -> Page[int]:
        return fetch(cursor)

    async def drain() -> list[int]:
        walk = apaginate(afetch)
        assert sent == []
        return [item async for item in walk]

    if asynchronous:
        result = asyncio.run(drain())
    else:
        walk = paginate(fetch)
        assert sent == []
        result = list(walk)
    assert result == [item for page in pages for item in page]
    assert sent == [None, *(f"cursor_{i}" for i in range(1, len(pages)))]


@pytest.mark.parametrize("asynchronous", [False, True])
@given(items=st.lists(st.integers(), max_size=10), cursor=st.text(alphabet="abc123", min_size=1))
def test_an_immediately_repeated_cursor_stops_after_two_fetches(
    *, asynchronous: bool, items: list[int], cursor: str
) -> None:
    sent: list[str | None] = []

    def fetch(value: str | None) -> Page[int]:
        sent.append(value)
        assert len(sent) <= 2
        return Page(items, cursor)

    async def afetch(value: str | None) -> Page[int]:
        return fetch(value)

    async def drain() -> None:
        _ = [item async for item in apaginate(afetch)]

    def walk() -> None:
        if asynchronous:
            asyncio.run(drain())
        else:
            list(paginate(fetch))

    with pytest.raises(HushscriptError) as raised:
        walk()
    assert type(raised.value) is HushscriptError
    assert (raised.value.code, raised.value.status) == ("pagination_loop", None)
    assert sent == [None, cursor]


@pytest.mark.parametrize("asynchronous", [False, True])
@given(items=st.lists(st.integers(), min_size=1, max_size=10))
def test_closing_a_walk_never_fetches_the_next_page(
    *, asynchronous: bool, items: list[int]
) -> None:
    sent: list[str | None] = []

    def fetch(cursor: str | None) -> Page[int]:
        sent.append(cursor)
        assert sent == [None]
        return Page(items, "more")

    async def afetch(cursor: str | None) -> Page[int]:
        return fetch(cursor)

    async def close() -> None:
        walk: AsyncGenerator[int] = apaginate(afetch)  # type: ignore[assignment]  # pyright: ignore[reportAssignmentType]
        assert await anext(walk) == items[0]
        await walk.aclose()

    if asynchronous:
        asyncio.run(close())
    else:
        walk: Generator[int] = paginate(fetch)  # type: ignore[assignment]  # pyright: ignore[reportAssignmentType]
        assert next(walk) == items[0]
        walk.close()
    assert sent == [None]
