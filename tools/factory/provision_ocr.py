#!/usr/bin/env python3
"""Pinned local OCR preparation. PNM only; private images never leave the host."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tarfile
import urllib.request

FIELDS = {"kind", "platform", "minimum_free_bytes", "version", "leptonica_version",
          "cmake_version", "sources"}
SCOPE = "local PNM English OCR public-text roundtrip only"
TEXT = "NEPTUNE READY"


def fail(kind, message):
    from provision import ProvisionError
    raise ProvisionError(kind, message)


def validate(recipe):
    if (set(recipe) != FIELDS or recipe["kind"] != "tesseract-source" or
            set(recipe["sources"]) != {"cmake", "leptonica", "tesseract", "english"}):
        fail("invalid_recipe", "Require the complete pinned OCR recipe")
    for key in ("version", "leptonica_version", "cmake_version"):
        if not isinstance(recipe[key], str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", recipe[key]):
            fail("invalid_recipe", "Require stable OCR/build versions")
    patterns = {
        "cmake": re.escape("https://github.com/Kitware/CMake/releases/download/v" +
                           recipe["cmake_version"] + "/cmake-" + recipe["cmake_version"] +
                           "-linux-x86_64.tar.gz"),
        "leptonica": r"https://codeload\.github\.com/DanBloomberg/leptonica/tar\.gz/[0-9a-f]{40}",
        "tesseract": r"https://codeload\.github\.com/tesseract-ocr/tesseract/tar\.gz/[0-9a-f]{40}",
        "english": r"https://raw\.githubusercontent\.com/tesseract-ocr/tessdata_fast/[0-9a-f]{40}/eng\.traineddata",
    }
    for name, source in recipe["sources"].items():
        if (set(source) != {"url", "sha256", "bytes"} or
                not isinstance(source["url"], str) or not re.fullmatch(patterns[name], source["url"]) or
                not isinstance(source["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", source["sha256"]) or
                type(source["bytes"]) is not int or not 1 <= source["bytes"] <= 100 * 1024**2):
            fail("invalid_recipe", "Require official immutable sources and bounded hashes")


def fetch(source, target):
    expected = source["bytes"]
    digest = hashlib.sha256()
    size = 0
    with urllib.request.urlopen(source["url"], timeout=30) as response, target.open("xb") as output:
        while chunk := response.read(min(1024**2, expected + 1 - size)):
            size += len(chunk)
            if size > expected:
                fail("source_mismatch", "OCR source exceeds pinned byte count")
            digest.update(chunk)
            output.write(chunk)
    if size != expected or digest.hexdigest() != source["sha256"]:
        fail("source_mismatch", "OCR source size/hash mismatch")


def unpack(archive, destination):
    # No symlinks, special files, duplicate paths or unbounded expanded archives.
    with tarfile.open(archive) as tar:
        members = tar.getmembers()
        paths = [PurePosixPath(member.name) for member in members]
        if (not members or len(members) > 20000 or
                sum(member.size for member in members) > 512 * 1024**2 or
                len(set(paths)) != len(paths) or
                len({path.parts[0] for path in paths if path.parts}) != 1):
            fail("source_mismatch", "Invalid or oversized OCR source tree")
        for member, path in zip(members, paths):
            if (not path.parts or path.is_absolute() or ".." in path.parts or
                    not (member.isfile() or member.isdir()) or member.size < 0):
                fail("source_mismatch", "Unsafe OCR archive member")
        destination.mkdir()
        for member, path in zip(members, paths):
            target = destination.joinpath(*path.parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(member) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output)
                target.chmod(0o755 if member.mode & 0o111 else 0o644)
        return destination / paths[0].parts[0]


def fixture(path):
    # Independently generated public bitmap letters, no reference game content.
    glyphs = {
        "N": "10001 11001 11001 10101 10011 10011 10001",
        "E": "11111 10000 10000 11110 10000 10000 11111",
        "P": "11110 10001 10001 11110 10000 10000 10000",
        "T": "11111 00100 00100 00100 00100 00100 00100",
        "U": "10001 10001 10001 10001 10001 10001 01110",
        "R": "11110 10001 10001 11110 10100 10010 10001",
        "A": "01110 10001 10001 11111 10001 10001 10001",
        "D": "11110 10001 10001 10001 10001 10001 11110",
        "Y": "10001 10001 01010 00100 00100 00100 00100",
    }
    scale, border = 6, 30
    width, height = (len(TEXT) * 6 - 1) * scale + 2 * border, 7 * scale + 2 * border
    pixels = bytearray([255]) * (width * height)
    for index, letter in enumerate(TEXT):
        if letter == " ":
            continue
        for row, bits in enumerate(glyphs[letter].split()):
            for column, bit in enumerate(bits):
                if bit == "1":
                    for y in range(border + row * scale, border + (row + 1) * scale):
                        start = y * width + border + (index * 6 + column) * scale
                        pixels[start:start + scale] = b"\0" * scale
    path.write_bytes(f"P5\n{width} {height}\n255\n".encode() + pixels)


def install(recipe, payload, work, runner, root):
    validate(recipe)
    for command in ("make", "cc", "c++"):
        if shutil.which(command, path=os.defpath) is None:
            fail("missing_host_dependency", "Managed preparation required for: " + command)
    recipe_path = work / "ocr-recipe.json"
    recipe_path.write_text(json.dumps(recipe))
    runner.run([sys.executable, str(root / "tools/factory/provision_ocr.py"),
                "fetch", str(recipe_path), str(work)], work, 180)
    trees = {name: unpack(work / (name + ".tar.gz"), work / (name + "-source"))
             for name in ("cmake", "leptonica", "tesseract")}
    cmake = str(trees["cmake"] / "bin/cmake")
    version = runner.run([cmake, "--version"], work, 15).splitlines()[0]
    if version != "cmake version " + recipe["cmake_version"]:
        fail("source_mismatch", "Build-tool runtime differs from reviewed version")
    prefix = work / "leptonica-install"
    common = ["-G", "Unix Makefiles", "-DCMAKE_BUILD_TYPE=Release", "-DBUILD_SHARED_LIBS=OFF"]
    lept = work / "leptonica-build"
    runner.run([cmake, "-S", str(trees["leptonica"]), "-B", str(lept), *common,
                "-DCMAKE_INSTALL_PREFIX=" + str(prefix), "-DBUILD_PROG=OFF", "-DSW_BUILD=OFF",
                *["-DENABLE_" + name + "=OFF" for name in
                  ("ZLIB", "PNG", "GIF", "JPEG", "TIFF", "WEBP", "OPENJPEG")]], work, 90)
    runner.run([cmake, "--build", str(lept), "--parallel", "1"], work, 600)
    runner.run([cmake, "--install", str(lept)], work, 30)
    tess = work / "tesseract-build"
    runner.run([cmake, "-S", str(trees["tesseract"]), "-B", str(tess), *common,
                "-DCMAKE_PREFIX_PATH=" + str(prefix), "-DBUILD_TRAINING_TOOLS=OFF",
                "-DBUILD_TESTS=OFF", "-DGRAPHICS_DISABLED=ON", "-DDISABLED_LEGACY_ENGINE=ON",
                "-DDISABLE_CURL=ON", "-DDISABLE_ARCHIVE=ON", "-DDISABLE_TIFF=ON",
                "-DOPENMP_BUILD=OFF", "-DENABLE_NATIVE=OFF", "-DENABLE_LTO=OFF",
                "-DCMAKE_CXX_FLAGS=-DTESSERACT_DISABLE_DEBUG_FONTS",
                "-DENABLE_CCACHE=OFF", "-DENABLE_PRECOMPILED_HEADERS=OFF"], work, 90)
    runner.run([cmake, "--build", str(tess), "--target", "tesseract", "--parallel", "1"], work, 900)
    shutil.copy2(tess / "bin/tesseract", payload / "tesseract")
    data = payload / "tessdata"
    data.mkdir()
    shutil.copy2(work / "english.traineddata", data / "eng.traineddata")
    notices = payload / "notices"
    notices.mkdir()
    for name in ("tesseract", "leptonica"):
        source = trees[name] / ("LICENSE" if name == "tesseract" else "leptonica-license.txt")
        shutil.copy2(source, notices / (name + ".txt"))


def smoke(recipe, binary, runner):
    from provision import digest, safe_path
    validate(recipe)
    data = safe_path(binary.parent / "tessdata/eng.traineddata")
    if not data.is_file() or digest(data) != recipe["sources"]["english"]["sha256"]:
        fail("smoke_failed", "Missing or changed pinned English model")
    version = runner.run([str(binary), "--version"], binary.parent, 15)
    if ("tesseract " + recipe["version"] not in version.splitlines() or
            " leptonica-" + recipe["leptonica_version"] not in version.splitlines()):
        fail("smoke_failed", "Actual OCR/runtime library version differs")
    image = runner.evidence / "ocr-public-text.pgm"
    fixture(image)
    actual = runner.run([str(binary), str(image), "stdout", "--tessdata-dir",
                         str(data.parent), "-l", "eng", "--oem", "1", "--psm", "7"],
                        binary.parent, 30)
    if actual != TEXT:
        fail("smoke_failed", "OCR public text differs or is empty")
    return {"scope": SCOPE, "version": recipe["version"],
            "leptonica_version": recipe["leptonica_version"], "text": actual,
            "image_sha256": digest(image), "traineddata_sha256": digest(data)}


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] != "fetch":
        raise SystemExit("Expected fetch <trusted-recipe> <preparation-directory>")
    recipe = json.loads(Path(sys.argv[2]).read_text())
    validate(recipe)
    for name, source in recipe["sources"].items():
        fetch(source, Path(sys.argv[3]) / (name + (".traineddata" if name == "english" else ".tar.gz")))
