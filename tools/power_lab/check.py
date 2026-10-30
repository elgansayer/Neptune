#!/usr/bin/env python3
"""Run bounded Power analysis tooling tests, never infer original-game success."""
from pathlib import Path
import unittest

suite = unittest.defaultTestLoader.discover(str(Path(__file__).parent / "tests"))
if not suite.countTestCases():
    raise SystemExit("No Power tooling tests discovered")
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
