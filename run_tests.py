#!/usr/bin/env python3
"""Run trading-engine unit tests."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_SRC = _ROOT / "src"


def _ensure_installed() -> None:
    try:
        import trading_engine  # noqa: F401
        return
    except ImportError:
        pass
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-e", str(_ROOT), "-q"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        if str(_SRC) not in sys.path:
            sys.path.insert(0, str(_SRC))


_ensure_installed()

if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

if __name__ == "__main__":
    raise SystemExit(
        unittest.main(
            module=None,
            argv=["", "discover", "-s", str(_ROOT / "tests"), "-t", str(_ROOT), "-v"],
            exit=True,
        )
    )
