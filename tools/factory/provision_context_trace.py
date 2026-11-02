#!/usr/bin/env python3
"""Prepare a separate bounded context observer in a disposable matched core."""
import argparse
import json
from pathlib import Path
import sys

from provision_call_trace import REVISION, SOURCES, digest, plain


def prepare(source, header=None):
    source = Path(source).absolute()
    header = header or Path(__file__).with_name("provision_context_trace.h")
    content = {name: plain(source / name) for name in SOURCES}
    if any(digest(content[name]) != expected for name, expected in SOURCES.items()):
        raise ValueError("Core source differs from the inspected reference pin")
    observer = plain(header)
    destination = source / "mednafen/ss/neptune_context_trace.h"
    if destination.exists() or destination.is_symlink():
        raise ValueError("Use a fresh disposable core checkout; observer already exists")
    anchor = b'#include "sh7095.inc"'
    main = content["mednafen/ss/ss.c"]
    if main.count(anchor) != 1:
        raise ValueError("Ambiguous core inclusion point")
    main = main.replace(anchor, b'#include "neptune_context_trace.h"\n' + anchor)
    steps = content["mednafen/ss/sh7095.inc"]
    dispatch = b" const uint32_t instr = (uint16_t)z->Pipe_ID;"
    for name in (b"SH7095_Step_w0_C0", b"SH7095_Step_w0_C1"):
        signature = b"FORCE_INLINE void " + name + b"(SH7095* z)\n{"
        if steps.count(signature) != 1:
            raise ValueError("Missing/ambiguous matched master dispatch")
        start = steps.index(signature) + len(signature)
        offset = steps.index(dispatch, start)
        if offset - start > 2048:
            raise ValueError("Master pipeline anchor outside inspected boundary")
        steps = steps[:offset] + b" neptune_context_step(z);\n" + steps[offset:]
    exports = content["link.T"]
    if exports.count(b"global: retro_*;") != 1:
        raise ValueError("Missing inspected export boundary")
    names = ("begin", "frame", "stop", "status", "records", "witness")
    exports = exports.replace(b"global: retro_*;", b"global: retro_*; " +
                              b" ".join(("neptune_context_" + name + ";").encode() for name in names))
    outputs = {"mednafen/ss/ss.c": main, "mednafen/ss/sh7095.inc": steps,
               "link.T": exports, "mednafen/ss/neptune_context_trace.h": observer}
    for name, data in outputs.items():
        (source / name).write_bytes(data)
    return {"schema": "neptune.context-trace-patch.v1", "reference_revision": REVISION,
            "source_hashes": SOURCES, "patched_hashes": {name: digest(data) for name, data in outputs.items()},
            "observer_abi": 1, "cpu": "master SH-2 interpreter only",
            "profiles": {"1": "fresh selection 06006BE4", "2": "resumed selection 06006C00",
                         "3": "yield 06006D36"}, "maximum_cycles": 16,
            "capacity": 128, "maximum_inflight_dispatches": 4096,
            "source_witness_words": 339, "game_bytes_modified": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.source), sort_keys=True))
    except (ValueError, OSError) as error:
        print("FAIL: " + str(error), file=sys.stderr)
        raise SystemExit(1)
