#!/usr/bin/env python3
"""Run synthetic regression suite for tools/saturn_archive."""

from __future__ import annotations

from pathlib import Path
import unittest


def main() -> int:
    suite = unittest.defaultTestLoader.discover(str(Path(__file__).resolve().parent), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
