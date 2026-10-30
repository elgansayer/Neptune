#!/usr/bin/env python3
"""Run research tooling tests, failing if discovery finds no tests."""
from pathlib import Path
import unittest

if __name__ == "__main__":
    suite = unittest.TestSuite()
    for directory in (Path(__file__).parent / "tests",
                      Path(__file__).parent.parent / "power_lab" / "tests"):
        found = unittest.defaultTestLoader.discover(str(directory), top_level_dir=str(directory))
        if found.countTestCases() == 0:
            raise SystemExit("No research tooling tests discovered: " + str(directory))
        suite.addTests(found)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
