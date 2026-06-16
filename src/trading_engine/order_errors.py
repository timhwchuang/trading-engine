"""P4-11: Classify place_order failures for retry / alert policy."""

from __future__ import annotations

import re
from enum import Enum


class OrderErrorCategory(str, Enum):
    RETRYABLE = "retryable"
    FATAL = "fatal"
    UNKNOWN = "unknown"


_RETRY_PATTERNS = (
    r"timeout",
    r"timed out",
    r"connection",
    r"connect",
    r"network",
    r"line busy",
    r"temporar",
    r"reset by peer",
    r"broken pipe",
)

_FATAL_PATTERNS = (
    r"憑證",
    r"certificate",
    r"ca ",
    r"餘額",
    r"balance",
    r"margin",
    r"insufficient",
    r"拒單",
    r"reject",
    r"permission",
    r"unauthorized",
    r"forbidden",
    r"invalid",
)


def classify_order_error(exc: BaseException) -> OrderErrorCategory:
    text = f"{type(exc).__name__} {exc}".lower()
    for pattern in _FATAL_PATTERNS:
        if re.search(pattern, text):
            return OrderErrorCategory.FATAL
    for pattern in _RETRY_PATTERNS:
        if re.search(pattern, text):
            return OrderErrorCategory.RETRYABLE
    return OrderErrorCategory.UNKNOWN


def should_retry_order(
    *,
    intent: str,
    category: OrderErrorCategory,
    attempt: int,
    max_retries: int,
) -> bool:
    """Exit / flatten may retry; entry never retries (漏單是成本)."""
    if intent != "exit":
        return False
    if attempt >= max_retries:
        return False
    return category in (OrderErrorCategory.RETRYABLE, OrderErrorCategory.UNKNOWN)
