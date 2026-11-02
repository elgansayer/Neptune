"""Run pinned gdtoolkit with an explicit writable cache, preserving HOME."""
import argparse
import runpy
import sys
from pathlib import Path


def main():
    arguments = argparse.ArgumentParser(description=__doc__, add_help=False)
    arguments.add_argument("mode", choices=("lint", "format"))
    arguments.add_argument("--cache", type=Path, required=True)
    selected, remaining = arguments.parse_known_args()
    from gdtoolkit.parser import parser

    # gdtoolkit 4.5.0 ignores XDG_CACHE_HOME and has no public cache selector.
    parser._cache_dirpath = str(selected.cache / "gdtoolkit")
    sys.argv = ["gdlint" if selected.mode == "lint" else "gdformat", *remaining]
    module = "gdtoolkit.linter" if selected.mode == "lint" else "gdtoolkit.formatter"
    runpy.run_module(module, run_name="__main__")


if __name__ == "__main__":
    main()
