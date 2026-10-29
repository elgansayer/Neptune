#!/usr/bin/env python3
"""Local, dependency-free source inventory and reproducible research input locks.

This tool does not emulate Saturn, decode disc files, or certify asset provenance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import struct
import sys
import tempfile
from typing import Any

SCHEMA = "neptune.saturn-inputs.v1"
IGNORED_DIRS = {".git", ".godot", "__pycache__", ".venv"}
CUE_FILE = re.compile(r'^\s*FILE\s+(?:"([^"]+)"|(\S+))\s+(\S+)\s*$', re.I)


class LabError(Exception):
    """An input is missing, unsafe, inconsistent, or unsupported."""


def confined_file(root: Path, relative: str) -> Path:
    """Resolve a portable path without following any symlink components."""
    if not isinstance(relative, str) or not relative or "\\" in relative or ":" in relative:
        raise LabError(f"Invalid relative path: {relative!r}")
    parts = PurePosixPath(relative)
    if parts.is_absolute() or ".." in parts.parts or parts.as_posix() != relative:
        raise LabError(f"Path must be normalised and remain within root: {relative!r}")
    target = root
    for component in parts.parts:
        target = target / component
        if target.is_symlink():
            raise LabError(f"Symlinks are not permitted: {relative}")
    if not target.is_file():
        raise LabError(f"Missing regular file: {relative}")
    if not target.resolve().is_relative_to(root.resolve()):
        raise LabError(f"Path escapes root: {relative}")
    return target


def fingerprint(path: Path) -> dict[str, Any]:
    before = path.stat()
    digest = hashlib.sha256()
    count = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            count += len(chunk)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (
        after.st_size, after.st_mtime_ns, after.st_ino
    ) or count != after.st_size:
        raise LabError(f"File changed during hashing: {path.name}")
    return {"bytes": count, "sha256": digest.hexdigest()}


def record(root: Path, relative: str) -> dict[str, Any]:
    return {"path": relative, **fingerprint(confined_file(root, relative))}


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def inventory(root: Path, excluded: Path | None = None) -> dict[str, Any]:
    if not root.is_dir():
        raise LabError("Inventory root must be a directory")
    files: list[dict[str, Any]] = []
    by_hash: dict[str, list[str]] = {}
    def walk_error(error: OSError) -> None:
        raise error
    for parent, directories, names in os.walk(root, onerror=walk_error, followlinks=False):
        directories[:] = sorted(name for name in directories if name not in IGNORED_DIRS)
        for name in directories:
            if (Path(parent) / name).is_symlink():
                raise LabError(f"Symlink directory in inventory: {name}")
        for name in sorted(names):
            path = Path(parent) / name
            if excluded is not None and path.absolute() == excluded.absolute():
                continue
            relative = path.relative_to(root).as_posix()
            item = record(root, relative)
            if path.suffix.lower() == ".png":
                with path.open("rb") as stream:
                    header = stream.read(24)
                if len(header) == 24 and header[:8] == b"\x89PNG\r\n\x1a\n" and header[12:16] == b"IHDR":
                    item["png_header_dimensions"] = list(struct.unpack(">II", header[16:24]))
            files.append(item)
            by_hash.setdefault(item["sha256"], []).append(relative)
    files.sort(key=lambda item: item["path"])
    return {
        "schema": "neptune.asset-inventory.v1",
        "file_count": len(files),
        "total_bytes": sum(item["bytes"] for item in files),
        "files": files,
        "duplicate_groups": sorted(sorted(paths) for paths in by_hash.values() if len(paths) > 1),
        "provenance": "unverified",
    }


def disc_files(root: Path, entry: str) -> list[str]:
    path = confined_file(root, entry)
    suffix = path.suffix.lower()
    if suffix == ".chd":
        return [entry]
    if suffix != ".cue":
        raise LabError("Use a complete BIN/CUE set or CHD; select the .cue or .chd file")
    tracks: set[str] = set()
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not re.match(r"^\s*FILE(?:\s|$)", line, re.I):
            continue
        match = CUE_FILE.fullmatch(line)
        if not match or match.group(3).upper() != "BINARY":
            raise LabError(f"Unsupported CUE FILE declaration on line {number}; require BINARY tracks")
        name = match.group(1) or match.group(2)
        # Validate the declared name before joining; joining can hide absolute paths.
        confined_file(path.parent, name)
        relative = (PurePosixPath(entry).parent / name).as_posix()
        confined_file(root, relative)
        tracks.add(relative)
    if not tracks:
        raise LabError("CUE contains no BINARY FILE declarations")
    return [entry, *sorted(tracks - {entry})]


def create_lock(root: Path, disc: str, bios: str, emulator: str, settings: str, region: str) -> dict[str, Any]:
    configuration = read_json(confined_file(root, settings))
    if not isinstance(configuration, dict) or not configuration:
        raise LabError("Settings must be a non-empty JSON object describing the intended emulator configuration")
    selected = {"disc": disc, "bios": bios, "emulator": emulator, "settings": settings}
    if len(set(selected.values())) != len(selected):
        raise LabError("Disc, BIOS, emulator and settings must be separate files")
    dependencies = disc_files(root, disc)
    paths = sorted(set(dependencies + [bios, emulator, settings]))
    return {
        "schema": SCHEMA,
        "region": region,
        "inputs": selected,
        "files": [record(root, path) for path in paths],
        "scope": "Input identity only; compatibility, settings application, disc validity and repeatability are not verified",
    }


def verify_lock(root: Path, manifest: Any) -> int:
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
        raise LabError("Unsupported input lock schema")
    if manifest.get("region") not in {"japan", "usa", "europe"}:
        raise LabError("Invalid reference region")
    inputs = manifest.get("inputs")
    if not isinstance(inputs, dict) or set(inputs) != {"disc", "bios", "emulator", "settings"}:
        raise LabError("Lock must identify disc, BIOS, emulator and settings")
    if any(not isinstance(value, str) for value in inputs.values()) or len(set(inputs.values())) != 4:
        raise LabError("Input paths must be four distinct strings")
    expected = manifest.get("files")
    if not isinstance(expected, list) or not expected:
        raise LabError("Lock has no files")
    seen: set[str] = set()
    for item in expected:
        if not isinstance(item, dict) or set(item) != {"path", "bytes", "sha256"}:
            raise LabError("Malformed file record")
        relative = item["path"]
        if not isinstance(relative, str) or relative in seen:
            raise LabError("Duplicate or invalid file record path")
        if type(item["bytes"]) is not int or item["bytes"] < 0:
            raise LabError("Invalid file size")
        if not isinstance(item["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
            raise LabError("Invalid SHA-256")
        actual = record(root, relative)
        if actual != item:
            raise LabError(f"Input differs from lock: {relative}")
        seen.add(relative)
    required = set(disc_files(root, inputs["disc"])) | set(inputs.values())
    if seen != required:
        raise LabError("Lock file set does not exactly cover all selected inputs and CUE tracks")
    configuration = read_json(confined_file(root, inputs["settings"]))
    if not isinstance(configuration, dict) or not configuration:
        raise LabError("Settings must be a non-empty JSON object")
    return len(seen)


def output_json(value: Any, output: Path | None) -> None:
    body = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if output is None:
        print(body, end="")
        return
    if output.is_symlink():
        raise LabError("Output must not be a symlink")
    if output.exists():
        try:
            previous = read_json(output)
        except (ValueError, UnicodeError) as error:
            raise LabError("Refusing to overwrite an unrelated output file") from error
        if not isinstance(previous, dict) or previous.get("schema") != value.get("schema"):
            raise LabError("Refusing to overwrite an unrelated output file")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent, delete=False) as stream:
            temporary = stream.name
            stream.write(body)
        os.replace(temporary, output)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    scan = commands.add_parser("inventory", help="Hash existing files and report exact duplicates")
    scan.add_argument("root", type=Path)
    scan.add_argument("--output", type=Path)
    lock = commands.add_parser("lock", help="Fingerprint all reference inputs; does not run the emulator")
    lock.add_argument("--root", type=Path, required=True)
    for name in ("disc", "bios", "emulator", "settings"):
        lock.add_argument("--" + name, required=True, help="Path relative to --root")
    lock.add_argument("--region", choices=("japan", "usa", "europe"), required=True)
    lock.add_argument("--output", type=Path, required=True)
    verify = commands.add_parser("verify", help="Re-hash inputs and require complete manifest coverage")
    verify.add_argument("--root", type=Path, required=True)
    verify.add_argument("--lock", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "inventory":
            if args.output is not None and args.output.exists() and not args.output.is_file():
                raise LabError("Output must be a file")
            output_json(inventory(args.root, args.output), args.output)
        elif args.command == "lock":
            result = create_lock(args.root, args.disc, args.bios, args.emulator, args.settings, args.region)
            if any(args.output.resolve() == confined_file(args.root, item["path"]).resolve() for item in result["files"]):
                raise LabError("Output must not overwrite an input")
            output_json(result, args.output)
        else:
            count = verify_lock(args.root, read_json(args.lock))
            print(f"Verified {count} input files; emulator compatibility and gameplay parity remain unverified.")
    except (LabError, OSError, ValueError, UnicodeError) as error:
        print(f"saturn-lab: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
