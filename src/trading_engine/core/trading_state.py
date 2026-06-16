"""Lightweight state constants and enums for the trading engine.

This is intentionally *not* a full FSM class (see DESIGN.md for rationale).
It provides named constants and basic transition guards + warnings for
invalid combinations during development and adversarial testing.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Optional


class PendingIntent(StrEnum):
    """Canonical intent values for the single pending slot."""

    ENTRY = "entry"
    EXIT = "exit"


def validate_pending_consistency(
    *,
    is_pending: bool,
    pending_intent: Optional[str],
    exit_pending: bool,
    position_qty: int,
    position_dir: str,
    logger=None,
) -> None:
    """Log warnings on obviously invalid combinations (defensive, not crash).

    Called from hot paths in development / test builds to surface drift early.
    """
    if is_pending:
        if not pending_intent:
            _warn(logger, "is_pending=True but pending_intent is falsy")
        if pending_intent == PendingIntent.EXIT and not exit_pending:
            _warn(logger, "pending exit intent but exit_pending flag is False")
        if pending_intent == PendingIntent.ENTRY and exit_pending:
            _warn(logger, "pending entry but exit_pending flag is True")

    if position_qty > 0 and position_dir == "Flat":
        _warn(logger, "position_qty > 0 but position_dir is Flat")
    if position_qty == 0 and position_dir != "Flat":
        _warn(logger, "position_qty == 0 but position_dir is not Flat")


def _warn(logger, msg: str) -> None:
    if logger is not None:
        try:
            logger.warning("STATE_GUARD %s", msg)
        except Exception:
            pass
    else:
        import logging

        logging.getLogger(__name__).warning("STATE_GUARD %s", msg)


__all__ = ["PendingIntent", "validate_pending_consistency"]
