"""Run the licmatch test suite without installing anything.

    pixi run licmatch-test          (from the repository root)
    python packages/licmatch/run_tests.py

stdlib unittest on purpose: the package must be testable wherever it is
vendored, including a checkout that has no pytest in its environment.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "src"))


def main() -> int:
    suite = unittest.defaultTestLoader.discover(str(HERE / "tests"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
