#!/usr/bin/env python3
"""Validate the actual catalogue and run tests; fail on empty discovery."""
from pathlib import Path
import subprocess
import sys
import unittest
from cli import DEFAULT, load

if __name__ == "__main__":
    load(DEFAULT)
    root = Path(__file__).resolve().parents[2]
    subprocess.run([sys.executable, str(root / "docs/restart/backlog/build_catalogue.py"), "--check"],
                   cwd=root, check=True)
    suite = unittest.defaultTestLoader.discover(str(Path(__file__).parent / "tests"))
    if suite.countTestCases() == 0:
        raise SystemExit("No catalogue tests discovered")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
