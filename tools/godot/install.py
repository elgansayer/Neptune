#!/usr/bin/env python3
"""Install the pinned Linux x86_64 Godot binary without root or package changes."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    lock = json.loads((Path(__file__).parent / "toolchain.json").read_text())
    for relative, expected in lock["addons"].items():
        if digest(ROOT / relative) != expected:
            raise SystemExit("Addon identity mismatch: " + relative)
    args.directory.mkdir(parents=True, exist_ok=True)
    binary = args.directory / lock["binary_name"]
    if binary.is_file() and digest(binary) == lock["binary_sha256"]:
        print(binary.resolve())
        return
    with tempfile.TemporaryDirectory(dir=args.directory) as temp:
        archive = Path(temp) / "godot.zip"
        with urllib.request.urlopen(lock["archive_url"], timeout=45) as response, archive.open("wb") as output:
            total = 0
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > 100 * 1024 * 1024:
                    raise SystemExit("Archive exceeds download limit")
                output.write(chunk)
        if digest(archive) != lock["archive_sha256"]:
            raise SystemExit("Godot archive identity mismatch")
        candidate = Path(temp) / lock["binary_name"]
        with zipfile.ZipFile(archive) as zipped:
            info = zipped.getinfo(lock["binary_name"])
            if info.file_size > 200 * 1024 * 1024:
                raise SystemExit("Godot binary exceeds size limit")
            candidate.write_bytes(zipped.read(info))
        if digest(candidate) != lock["binary_sha256"]:
            raise SystemExit("Godot binary identity mismatch")
        candidate.chmod(0o755)
        candidate.replace(binary)
    print(binary.resolve())


if __name__ == "__main__":
    main()
