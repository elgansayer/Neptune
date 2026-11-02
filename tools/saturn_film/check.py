#!/usr/bin/env python3
"""Run synthetic parser/PCM controls; no original assets are bundled."""

from pathlib import Path
import sys
import unittest

if __name__ == "__main__":
    suite = unittest.defaultTestLoader.discover(str(Path(__file__).parent), pattern="test_*.py")
    if suite.countTestCases() == 0:
        raise SystemExit("No FILM tests discovered")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(not result.wasSuccessful())
