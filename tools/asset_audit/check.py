#!/usr/bin/env python3
"""Run tools/asset_audit unit tests and fail if zero tests are discovered."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest


def main() -> int:
    suite = unittest.defaultTestLoader.discover(str(Path(__file__).resolve().parent), pattern="test_*.py")
    if suite.countTestCases() == 0:
        print("asset-audit check: zero tests discovered", file=sys.stderr)
        return 1
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
