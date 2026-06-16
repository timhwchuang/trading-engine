"""Phase 3/6: Ensure trading_engine can be imported and kernel exercised
with no 'shioaji' package present (pure broker-agnostic usage).
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CORE_FILES = (
    _REPO_ROOT / "src/trading_engine/engine.py",
    _REPO_ROOT / "src/trading_engine/session.py",
    _REPO_ROOT / "src/trading_engine/order_executor.py",
)


def _strip_type_checking_blocks(source: str) -> str:
    """Remove ``if TYPE_CHECKING:`` blocks so only runtime imports are checked."""
    return re.sub(
        r"if TYPE_CHECKING:.*?(?=\n(?:class |def |\Z))",
        "",
        source,
        flags=re.DOTALL,
    )


class TestNoShioajiCoreImport(unittest.TestCase):
    def test_core_modules_have_no_runtime_shioaji_import(self):
        for path in _CORE_FILES:
            text = _strip_type_checking_blocks(path.read_text())
            self.assertNotIn(
                "import shioaji",
                text,
                msg=f"{path.name} must not import shioaji at runtime",
            )
            self.assertNotIn(
                "from shioaji",
                text,
                msg=f"{path.name} must not import from shioaji at runtime",
            )

    def test_import_and_kernel_without_shioaji(self):
        # Simulate shioaji not installed by hiding it before import
        saved = {}
        for mod in list(sys.modules):
            if "shioaji" in mod:
                saved[mod] = sys.modules.pop(mod)

        # Also block future imports
        class _BlockShioaji:
            def find_module(self, fullname, path=None):
                if "shioaji" in fullname:
                    return self
                return None

            def load_module(self, fullname):
                raise ImportError("shioaji blocked for test")

        meta_finder = _BlockShioaji()
        sys.meta_path.insert(0, meta_finder)

        try:
            # Fresh import of the package (may still be cached as trading_engine)
            import importlib

            if "trading_engine" in sys.modules:
                # Reload to exercise top level again under blocked env
                import trading_engine as te  # type: ignore

                importlib.reload(te)
            else:
                import trading_engine as te  # type: ignore

            from trading_engine.core.types import PositionSnapshot, TickSnapshot
            from trading_engine.testing.helpers import make_host

            # Basic kernel construction + tick (mock) must work
            host = make_host()
            host._order_sync_mode = True
            host.contract = MagicMock(code="TXFR1")

            tick = MagicMock()
            tick.datetime = __import__("datetime").datetime(2026, 6, 10, 9, 30)
            tick.close = "18050"
            tick.volume = 30
            tick.tick_type = 1

            host.on_tick(tick)

            # Force flatten path also exercises without shioaji
            host.position_qty = 1
            host.position_dir = "Long"
            sig = host._maybe_kernel_force_flatten(1_700_000_000, 18055.0, tick.datetime)
            # In this dt (09:30) force_flatten is false, so None or not
            self.assertTrue(sig is None or sig.intent == "exit")

            # PositionSnapshot carries qty
            snap = host._position_snapshot()
            self.assertIsInstance(snap, PositionSnapshot)
            self.assertIsInstance(snap.qty, int)

            self.assertIsInstance(TickSnapshot, type)

        finally:
            sys.meta_path.remove(meta_finder)
            for k, v in saved.items():
                sys.modules[k] = v


if __name__ == "__main__":
    unittest.main()
