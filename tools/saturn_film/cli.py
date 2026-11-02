#!/usr/bin/env python3
"""Inspect prior-asset FILM packet timing or extract lossless PCM privately."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.saturn_film.film import FilmError, extract, load


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("inspect", "extract"):
        command = subparsers.add_parser(name)
        command.add_argument("--input", type=Path, required=True)
        if name == "extract":
            command.add_argument("--output", type=Path, required=True,
                                 help="Fresh private directory; parent must already exist")
    args = parser.parse_args(argv)
    try:
        film = load(args.input)
        report = extract(film, args.output) if args.command == "extract" else film.report()
    except (FilmError, OSError) as error:
        print(f"FILM recovery failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
