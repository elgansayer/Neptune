#!/usr/bin/env python3
"""Apply one bounded observer to a disposable matched-core checkout, never media.

Run from trusted preparation source. This is not a sandbox or a new installer;
the existing provisioner owns checkout/build/deadline/cache publication.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

REVISION = "01bc063fdd0fb5fc208850c9ecc658834df762ab"
SOURCES = {
    "mednafen/ss/ss.c": "589348b10d28e6eb809dd75d91055a85e96b336021b64e8db084e80b90393388",
    "mednafen/ss/sh7095.inc": "bd6751ee36b9daa8028813f2ce0c9a8207b6c51bc0c0eb4d570ce2d9a71e372b",
    "mednafen/ss/sh7095.h": "3b8c1d42bdf37d3c7857471c4a05f2f968f61818e535c6eb8a29aef6612b888e",
    "mednafen/ss/sh7095_ops.inc": "b63d0d457725e3b4482c152542b61e35ab07a1e1e10786558269fbdb41fb8b74",
    "Makefile": "304fdc4d5018760a7d37a1131a3b09df879c1b40ce80c7af0f5567c9d0a22236",
    "link.T": "20d8a69f1e68c44481005916c466dc6bda13b3c45d04f56f7176463f388f9298",
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def plain(path):
    if any(parent.is_symlink() for parent in (path, *path.parents)):
        raise ValueError("Trace preparation rejects symlinked source paths")
    if not path.is_file() or path.stat().st_size > 1024 * 1024:
        raise ValueError("Missing or oversized matched-core source")
    return path.read_bytes()


def prepare(source, header=None):
    source = Path(source).absolute()
    header = header or Path(__file__).with_name("provision_call_trace.h")
    content = {name: plain(source / name) for name in SOURCES}
    if any(digest(content[name]) != expected for name, expected in SOURCES.items()):
        raise ValueError("Core source differs from the inspected reference pin")
    observer = plain(header)
    destination = source / "mednafen/ss/neptune_call_trace.h"
    if destination.exists() or destination.is_symlink():
        raise ValueError("Use a fresh disposable core checkout; observer already exists")
    anchor = b'#include "sh7095.inc"'
    main = content["mednafen/ss/ss.c"]
    if main.count(anchor) != 1:
        raise ValueError("Ambiguous core inclusion point")
    main = main.replace(anchor, b'#include "neptune_call_trace.h"\n' + anchor)
    steps = content["mednafen/ss/sh7095.inc"]
    dispatch = b" const uint32_t instr = (uint16_t)z->Pipe_ID;"
    for name in (b"SH7095_Step_w0_C0", b"SH7095_Step_w0_C1"):
        signature = b"FORCE_INLINE void " + name + b"(SH7095* z)\n{"
        if steps.count(signature) != 1:
            raise ValueError("Missing/ambiguous matched master dispatch")
        start = steps.index(signature) + len(signature)
        offset = steps.index(dispatch, start)
        if offset - start > 2048:
            raise ValueError("Master pipeline anchor is outside its inspected boundary")
        steps = steps[:offset] + b" neptune_call_step(z);\n" + steps[offset:]
    exports = content["link.T"]
    if exports.count(b"global: retro_*;") != 1:
        raise ValueError("Missing inspected export boundary")
    exports = exports.replace(b"global: retro_*;", b"global: retro_*; neptune_call_begin; "
                              b"neptune_call_frame; neptune_call_stop; neptune_call_status; neptune_call_records;")
    outputs = {"mednafen/ss/ss.c": main, "mednafen/ss/sh7095.inc": steps, "link.T": exports,
               "mednafen/ss/neptune_call_trace.h": observer}
    for name, data in outputs.items():
        (source / name).write_bytes(data)
    return {"schema": "neptune.call-trace-patch.v1", "reference_revision": REVISION,
            "source_hashes": SOURCES, "patched_hashes": {name: digest(data) for name, data in outputs.items()},
            "observer_abi": 2, "cpu": "master SH-2 interpreter only",
            "entry": "caller-selected from an inspected allowlist",
            "supported_entries": ["0x0600b934", "0x0600a0ec"], "maximum_pairs": 64,
            "instruction_pc": "normal pipeline PC-4; delay slots never labelled PC-4",
            "game_bytes_modified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.source), sort_keys=True))
    except (ValueError, OSError) as error:
        print("FAIL: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
