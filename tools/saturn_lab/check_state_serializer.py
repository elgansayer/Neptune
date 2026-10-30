#!/usr/bin/env python3
"""Optional pinned-source serializer interoperability smoke, not game validation.

Supply five already obtained source files in one directory; no downloads occur.
The GPL serializer is compiled temporarily and is not vendored into Neptune.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import state_graphics as sg

SOURCES = {
    "state.c": "60c6aeb596154ad04a5e20abda7d563148b67fd92899d15b69bbc192b59254a8",
    "state.h": "af8d99457f565d238aa8ad5f2f8d7e1a18e5f7adc7dc35fa3c7b674b41be717f",
    "general.h": "683f45cc9a9947826b81b35bffb99a3a1399ec457dca10c96fda68a22a0dc431",
    "boolean.h": "9ae2871b702c3c7d89b5e0e40de28895e72bd0177e1d6da32cde6f59e46bb36e",
    "retro_inline.h": "7543242f56677091d46e3bc9a8b7d567a0df631cb8cdb1878970feaa53f77403",
}
# Only the logging declaration used by state.c; no emulator functionality is stubbed.
LOG_HEADER = """#ifndef TEST_LIBRETRO_H
#define TEST_LIBRETRO_H
enum retro_log_level { RETRO_LOG_DEBUG, RETRO_LOG_INFO, RETRO_LOG_WARN, RETRO_LOG_ERROR };
typedef void (*retro_log_printf_t)(enum retro_log_level, const char *, ...);
#endif
"""


def run(source, compiler="cc"):
    fixture = Path(__file__).parent / "tests/fixtures/state_serializer.c"
    with tempfile.TemporaryDirectory(prefix="neptune-state-source-") as tmp:
        root = Path(tmp)
        for name, expected in SOURCES.items():
            data = sg.read_bounded(source / name, 65536)
            if sg.sha(data) != expected:
                raise ValueError("Pinned source mismatch: " + name)
            (root / name).write_bytes(data)
        (root / "libretro.h").write_text(LOG_HEADER)
        (root / "fixture.c").write_bytes(fixture.read_bytes())
        subprocess.run([compiler, "-std=c11", "-O2", "-I", str(root),
                        str(root / "state.c"), str(root / "fixture.c"), "-o", str(root / "producer")],
                       check=True, timeout=60, capture_output=True)
        subprocess.run([str(root / "producer"), str(root / "state.bin")], check=True, timeout=10)
        data = sg.read_bounded(root / "state.bin", sg.MAX_STATE)
        report, files = sg.graphics(data, sys.byteorder, synthetic=True)
        for filename, count, expected in [("vram.bin", 0x40000, lambda i: (i ^ 0x50A3) & 65535),
                ("vdp2-vram.bin", 0x40000, lambda i: (i ^ 0xB400) & 65535),
                ("vdp2-cram.bin", 2048, lambda i: i * 3),
                ("vdp2-registers.bin", 256, lambda i: i * 19)]:
            normalized = files[filename]
            for i in range(count):
                if int.from_bytes(normalized[2*i:2*i+2], "big") != expected(i):
                    raise ValueError("Serializer/adapter mismatch in " + filename)
        if report["context"]["VDP1"]["current_command_byte_offset"] != 0x240:
            raise ValueError("Word-index conversion mismatch")
        wrong = "big" if sys.byteorder == "little" else "little"
        _, wrong_files = sg.graphics(data, wrong, synthetic=True)
        if wrong_files["vram.bin"] == files["vram.bin"]:
            raise ValueError("Wrong-order control failed to differ")
        return {"status": "serializer-interop-passed", "synthetic": True,
                "core_source_revision": sg.CORE_REVISION, "producer_byte_order": sys.byteorder,
                "state_sha256": sg.sha(data), "source_sha256": SOURCES,
                "fixture_sha256": sg.sha(fixture.read_bytes()),
                "verified_uint16_words": 526592, "wrong_byte_order_detected": True,
                "scope": "Actual pinned state.c writer, constructed arrays; no full core or original game"}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--sources", type=Path, required=True)
    p.add_argument("--compiler", default="cc")
    args = p.parse_args()
    try:
        result = run(args.sources, args.compiler)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print("FAIL: " + str(error), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
