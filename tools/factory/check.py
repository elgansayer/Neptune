#!/usr/bin/env python3
"""Run real SQLite/process and intake failure cases; empty suites fail."""
from pathlib import Path
import sys
import unittest

if __name__ == "__main__":
    suite = unittest.defaultTestLoader.discover(str(Path(__file__).parent / "tests"))
    if suite.countTestCases() == 0:
        sys.exit("FAIL: no factory tests")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() and not result.skipped else 1)
