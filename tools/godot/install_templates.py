#!/usr/bin/env python3
"""Install hash-pinned Linux x86_64 and web export templates without root."""
import argparse
import json
from pathlib import Path
import re
import tempfile
import urllib.request
import zipfile

from install import digest

TEMPLATES = ("linux_debug.x86_64", "linux_release.x86_64", "version.txt",
             "web_debug.zip", "web_release.zip", "web_nothreads_debug.zip", "web_nothreads_release.zip",
             "web_dlink_debug.zip", "web_dlink_release.zip",
             "web_dlink_nothreads_debug.zip", "web_dlink_nothreads_release.zip")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True, type=Path,
                        help="Godot export_templates directory; creates the pinned version subdirectory")
    parser.add_argument("--archive", type=Path, help="Use an existing archive after verifying its pinned hash")
    args = parser.parse_args()
    lock = json.loads((Path(__file__).parent / "toolchain.json").read_text())["export_templates"]
    if not re.fullmatch(r"[0-9]+\.[0-9]+(?:\.[0-9]+)?\.stable", lock["version"]):
        raise SystemExit("Invalid stable template version")
    args.directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.directory, prefix=".templates-") as temp:
        archive = args.archive
        if archive is None:
            archive = Path(temp) / "templates.tpz"
            with urllib.request.urlopen(lock["archive_url"], timeout=60) as response, archive.open("wb") as output:
                total = 0
                while chunk := response.read(4 * 1024 * 1024):
                    total += len(chunk)
                    if total > 2 * 1024**3:
                        raise SystemExit("Export templates exceed download limit")
                    output.write(chunk)
        if digest(archive) != lock["archive_sha256"]:
            raise SystemExit("Export template archive identity mismatch")
        with zipfile.ZipFile(archive) as zipped:
            if zipped.read("templates/version.txt").decode().strip() != lock["version"]:
                raise SystemExit("Export template version mismatch")
            for name in TEMPLATES:
                info = zipped.getinfo("templates/" + name)
                if info.file_size > 200 * 1024**2:
                    raise SystemExit("Export template exceeds size limit: " + name)
                candidate = Path(temp) / name
                candidate.write_bytes(zipped.read(info))
                if name.startswith("linux_"):
                    candidate.chmod(0o755)
        target = args.directory / lock["version"]
        target.mkdir(exist_ok=True)
        for name in TEMPLATES:
            (Path(temp) / name).replace(target / name)
    print(target.resolve())


if __name__ == "__main__":
    main()
