#!/usr/bin/env python3
"""Run research tooling tests, failing if discovery finds no tests."""
from pathlib import Path
import unittest

if __name__ == "__main__":
    suite = unittest.defaultTestLoader.discover(str(Path(__file__).parent / "tests"))
    if suite.countTestCases() == 0:
        raise SystemExit("No research tooling tests discovered")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
