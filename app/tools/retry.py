from __future__ import annotations

from collections.abc import Callable
from time import sleep
from typing import TypeVar


T = TypeVar("T")


def with_retry(func: Callable[[], T], attempts: int = 2, delay_seconds: float = 0.25) -> tuple[T, int]:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return func(), attempt
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < attempts - 1:
                sleep(delay_seconds * (attempt + 1))
    assert last_error is not None
    raise last_error
