#!/usr/bin/env python3
"""Read a pinned Beetle raw checkpoint into private VDP1/VDP2 capture inputs.

No emulator execution, command discovery, palette resolver or sheet extraction.
The core revision/identity remain declarations; a hash is not an execution receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import sys

from probe_kernel import kernel_bytes

CORE_REVISION = "01bc063fdd0fb5fc208850c9ecc658834df762ab"
VERSION = 0x00103201
MAX_STATE = 64 * 1024 * 1024
MAX_FIELDS = 32768
ARRAYS = {
    ("VDP1", "VRAM"): (0x80000, "vram.bin"),
    ("VDP2", "VRAM"): (0x80000, "vdp2-vram.bin"),
    ("VDP2", "CRAM"): (0x1000, "vdp2-cram.bin"),
    ("VDP2", "RawRegs"): (0x200, "vdp2-registers.bin"),
}
SCALARS = {
    "VDP1": {"CurCommandAddr": 4, "RetCommandAddr": 4, "DrawingActive": 1,
             "FBDrawWhich": 1, "TVMR": 1, "FBCR": 1, "PTMR": 1,
             "EDSR": 1, "CommandPhase": 4},
    "VDP2": {"CRAM_Mode": 1, "HRes": 1, "VRes": 1, "InterlaceMode": 1,
             "RAMCTL_Raw": 2},
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_bounded(path, maximum):
    with path.open("rb") as stream:
        data = stream.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError("Input exceeds size limit")
    return data


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def unique_json(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError("Duplicate JSON key")
            out[key] = value
        return out
    result = json.loads(raw, object_pairs_hook=pairs)
    if not isinstance(result, dict):
        raise ValueError("Expected JSON object")
    return result


def parse(data):
    """Strict framing for the inspected pin, retaining bounded unknown fields."""
    if len(data) > MAX_STATE or len(data) < 32 or data[:8] != b"MDFNSVST":
        raise ValueError("Expected bounded raw MDFNSVST state; wrappers are unsupported")
    version, length = struct.unpack_from("<II", data, 16)
    if version != VERSION or any(data[8:16] + data[24:32]):
        raise ValueError("Unsupported state header/version")
    if not 32 <= length <= len(data) or any(data[length:]):
        raise ValueError("Invalid recorded length or nonzero frontend padding")
    sections, count, cursor = {}, 0, 32

    def name(raw):
        if not raw or any(c < 32 or c > 126 for c in raw):
            raise ValueError("Invalid record name")
        return raw.decode("ascii")

    while cursor < length:
        if len(sections) >= 256:
            raise ValueError("Too many sections")
        if cursor + 36 > length:
            raise ValueError("Truncated section header")
        start = cursor
        raw_name = data[cursor:cursor + 32]
        parts = raw_name.split(b"\0", 1)
        section = name(parts[0])
        if len(parts) == 2 and any(parts[1]):
            raise ValueError("Invalid section name padding")
        size = struct.unpack_from("<I", data, cursor + 32)[0]
        cursor += 36
        end = cursor + size
        if end > length or section in sections:
            raise ValueError("Out-of-range or duplicate section")
        fields, offsets = {}, {}
        while cursor < end:
            count += 1
            if count > MAX_FIELDS:
                raise ValueError("Too many fields")
            n = data[cursor]
            cursor += 1
            if cursor + n + 4 > end:
                raise ValueError("Truncated field header")
            field = name(data[cursor:cursor + n])
            cursor += n
            size = struct.unpack_from("<I", data, cursor)[0]
            cursor += 4
            if cursor + size > end or field in fields:
                raise ValueError("Out-of-range or duplicate field")
            fields[field] = data[cursor:cursor + size]
            offsets[field] = cursor
            cursor += size
        sections[section] = {"fields": fields, "offsets": offsets,
                             "offset": start, "bytes": end - start}
    return {"version": version, "recorded_bytes": length,
            "padding_bytes": len(data) - length, "sections": sections}


def field(state, section, key, size):
    value = state["sections"].get(section, {}).get("fields", {}).get(key)
    if value is None or len(value) != size:
        raise ValueError("Missing/wrong-sized field: " + section + "." + key)
    return value


def cpu_words(data, order):
    if order not in ("little", "big") or len(data) % 2:
        raise ValueError("Expected declared producer order and complete uint16 array")
    if order == "big":
        return data
    out = bytearray(len(data))
    out[0::2], out[1::2] = data[1::2], data[0::2]
    return bytes(out)


def graphics(data, order, *, synthetic, kernel=None):
    state = parse(data)
    if type(synthetic) is not bool:
        raise ValueError("Declare synthetic boolean")
    files = {filename: cpu_words(field(state, section, key, size), order)
             for (section, key), (size, filename) in ARRAYS.items()}
    context = {}
    for section, layout in SCALARS.items():
        context[section] = {key: int.from_bytes(field(state, section, key, size), order,
                               signed=key in ("RetCommandAddr", "CommandPhase"))
                            for key, size in layout.items()}
    context["VDP1"]["current_command_byte_offset"] = context["VDP1"]["CurCommandAddr"] * 2
    # A separately hash-verified original file disambiguates the state producer's
    # word order. This checks a code span, not the truth of all checkpoint labels.
    witness = {"status": "synthetic-no-original-witness"}
    if not synthetic:
        if kernel is None:
            raise ValueError("Original capture requires the verified USA kernel witness")
        high = cpu_words(field(state, "MAIN", "WorkRAMH", 0x100000), order)
        expected = kernel_bytes(kernel)[0x44B0:0x44F0]
        if high[0xA4B0:0xA4F0] != expected:
            raise ValueError("USA original code witness mismatch; wrong order/build/load phase")
        witness = {"status": "original-code-span-matched", "cpu_address": "0x0600A4B0",
                   "kernel_offset": "0x44B0", "bytes": 64, "sha256": sha(expected)}
    vdp2 = state["sections"]["VDP2"]
    files["vdp2-state.bin"] = data[vdp2["offset"]:vdp2["offset"] + vdp2["bytes"]]
    files["context.json"] = json_bytes(context)
    index = {s: {k: {"offset": v["offsets"][k], "bytes": len(b), "sha256": sha(b)}
                    for k, b in v["fields"].items()}
             for s, v in state["sections"].items()}
    return {"version": state["version"], "recorded_bytes": state["recorded_bytes"],
            "padding_bytes": state["padding_bytes"], "fields": index,
            "context": context, "byte_order_witness": witness}, files


def adapt(checkpoint, output, *, order, core_revision, capture_id, synthetic=False, kernel=None):
    if core_revision != CORE_REVISION:
        raise ValueError("Unsupported declared core source revision")
    if not isinstance(capture_id, str) or not capture_id.strip() or len(capture_id) > 256:
        raise ValueError("Invalid capture ID")
    raw_meta = read_bounded(checkpoint, 16384)
    meta = unique_json(raw_meta)
    if meta.get("schema") != "neptune.libretro-checkpoint.v1":
        raise ValueError("Unsupported checkpoint sidecar")
    identity = meta.get("identity")
    keys = ("lock_sha256", "core_sha256", "settings_sha256", "frontend_sha256", "python_sha256")
    if not isinstance(identity, dict) or any(not isinstance(identity.get(k), str) or
            not re.fullmatch(r"[0-9a-f]{64}", identity[k]) for k in keys):
        raise ValueError("Incomplete checkpoint identity")
    if type(meta.get("frame")) is not int or meta["frame"] < 0:
        raise ValueError("Invalid checkpoint frame")
    relative = meta.get("state_path")
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValueError("Invalid relative state path")
    parent = checkpoint.parent.resolve()
    path = (parent / relative).resolve(strict=True)
    if not path.is_relative_to(parent):
        raise ValueError("State path escapes checkpoint directory")
    data = read_bounded(path, MAX_STATE)
    if type(meta.get("state_bytes")) is not int or meta["state_bytes"] != len(data) or meta.get("state_sha256") != sha(data):
        raise ValueError("Checkpoint state size/digest mismatch")
    report, files = graphics(data, order, synthetic=synthetic, kernel=kernel)
    capture = {"schema": "neptune.vdp1-capture.v1", "game": "Saturn Bomberman",
               "build": "USA MK-81070 V1.003" if not synthetic else "synthetic fixture",
               "capture_id": capture_id, "frame": meta["frame"], "synthetic": synthetic,
               "byte_order": "big", "input_lock_sha256": identity["lock_sha256"],
               "core_sha256": identity["core_sha256"], "vram_sha256": sha(files["vram.bin"]),
               "vdp2_state_sha256": sha(files["vdp2-state.bin"])}
    files["capture.json"] = json_bytes(capture)
    report.update(schema="neptune.state-graphics.v1", status="state-adapted", synthetic=synthetic,
                  core_source_revision=core_revision, producer_byte_order=order,
                  state_sha256=sha(data), checkpoint_metadata_sha256=sha(raw_meta),
                  checkpoint_identity={k: identity[k] for k in keys},
                  adapter_sha256=sha(Path(__file__).read_bytes()),
                  limitations=["Declarations and byte consistency are not authenticated host execution.",
                               "No command discovery, palette resolution, complete scene or sheet recovery.",
                               "Mid-draw state may not describe the currently displayed frame.",
                               "All raw outputs remain host-private."],
                  outputs={n: {"bytes": len(b), "sha256": sha(b)} for n, b in sorted(files.items())})
    output.mkdir(mode=0o700)
    try:
        for name, value in files.items():
            (output / name).write_bytes(value)
        (output / "manifest.json").write_bytes(json_bytes(report))
    except BaseException:
        shutil.rmtree(output)
        raise
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--producer-byte-order", choices=("little", "big"), required=True)
    p.add_argument("--core-source-revision", required=True)
    p.add_argument("--capture-id", required=True)
    p.add_argument("--kernel", type=Path)
    p.add_argument("--synthetic", action="store_true")
    args = p.parse_args(argv)
    try:
        report = adapt(args.checkpoint, args.output, order=args.producer_byte_order,
                       core_revision=args.core_source_revision, capture_id=args.capture_id,
                       synthetic=args.synthetic, kernel=args.kernel)
    except (OSError, ValueError, TypeError, struct.error) as error:
        print("FAIL: " + str(error), file=sys.stderr)
        return 1
    print(json.dumps({"status": report["status"], "synthetic": report["synthetic"],
                      "manifest": str(args.output / "manifest.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
