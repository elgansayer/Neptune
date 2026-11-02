#!/usr/bin/env python3
"""Compare retained PCM from the same pinned libretro replay; no resampling."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from cli import LabError
from pcm import compare_captures


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--reference-start", type=int, default=0,
                        help="Explicit zero-based reference video-frame index selecting the suffix; no inferred alignment")
    args = parser.parse_args(argv)
    try:
        result = compare_captures(args.reference, args.candidate, args.reference_start)
        print(json.dumps(result, sort_keys=True))
        return 0 if result["match"] else 1
    except (LabError, OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError, OverflowError) as error:
        print(json.dumps({"match": False, "error": str(error)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
