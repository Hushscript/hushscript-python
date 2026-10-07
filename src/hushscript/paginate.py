from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic, TypeVar

from ._errors import HushscriptError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable, Iterator

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Page(Generic[T]):
    """One page of a list. `next_cursor` is opaque and None on the last page."""

    items: list[T]
    next_cursor: str | None


def pagination_loop() -> HushscriptError:
    return HushscriptError(
        "The API returned the same page cursor it was sent; stopping instead of repeating it.",
        code="pagination_loop",
    )


def paginate(fetch: Callable[[str | None], Page[T]]) -> Iterator[T]:
    """Walks a cursor-paged list one page at a time, yielding every item in order. The walk is lazy:
    closing the iterator (or breaking out of a loop over it) sends no further request. A page that
    hands back the cursor it was asked with would repeat forever, so it raises `pagination_loop`
    once its items have been yielded."""
    cursor: str | None = None
    while True:
        sent = cursor
        page = fetch(sent)
        yield from page.items
        cursor = page.next_cursor or None
        if cursor is None:
            return
        if cursor == sent:
            raise pagination_loop()


async def apaginate(fetch: Callable[[str | None], Awaitable[Page[T]]]) -> AsyncIterator[T]:
    """`paginate` on the event loop; a cancellation between pages ends the walk there."""
    cursor: str | None = None
    while True:
        sent = cursor
        page = await fetch(sent)
        for item in page.items:
            yield item
        cursor = page.next_cursor or None
        if cursor is None:
            return
        if cursor == sent:
            raise pagination_loop()
