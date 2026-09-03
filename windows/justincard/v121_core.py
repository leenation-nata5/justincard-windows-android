from __future__ import annotations

from typing import Any

MAX_ADD_QUANTITY = 999


def normalize_add_quantity(value: Any) -> int:
    """Return a safe collection-add quantity for search and scanner flows."""
    try:
        quantity = int(value)
    except (TypeError, ValueError, OverflowError):
        quantity = 1
    return max(1, min(MAX_ADD_QUANTITY, quantity))


__all__ = ["MAX_ADD_QUANTITY", "normalize_add_quantity"]
