#!/usr/bin/env python3
"""Pinned headless Ghidra/JDK preparation; public SH-2 fixture, no reference media."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import tarfile
import urllib.request
import zipfile

FIELDS = {"kind", "platform", "minimum_free_bytes", "version", "jdk_version", "jdk_build", "sources"}
SCOPE = "public six-byte SH-2 headless import/disassembly/decompilation only"
LANGUAGE = "SuperH:BE:32:SH-2"
FIXTURE = bytes.fromhex("e02a000b0009")  # mov #42,r0; rts; nop (delay slot)
MAX_FILES = 50000
MAX_EXPANSION = 2 * 1024**3
MANIFEST = "payload-files.json"


def fail(kind, message):
    from provision import ProvisionError
    raise ProvisionError(kind, message)


def validate(recipe):
    if (set(recipe) != FIELDS or recipe["kind"] != "ghidra-jdk" or
            not isinstance(recipe["sources"], dict) or set(recipe["sources"]) != {"ghidra", "jdk"}):
        fail("invalid_recipe", "Require the complete pinned Ghidra/JDK recipe")
    for key in ("version", "jdk_version"):
        if not isinstance(recipe[key], str) or not re.fullmatch(r"[0-9]+\.[0-9]+(?:\.[0-9]+)?", recipe[key]):
            fail("invalid_recipe", "Require stable Ghidra/JDK versions")
    if (not recipe["jdk_version"].startswith("25.") or type(recipe["jdk_build"]) is not int or
            not 1 <= recipe["jdk_build"] <= 1000):
        fail("invalid_recipe", "This reviewed Ghidra launcher requires JDK25 and an exact build")
    version, jdk, build = recipe["version"], recipe["jdk_version"], recipe["jdk_build"]
    patterns = {
        "ghidra": re.escape("https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_" + version +
                            "_build/ghidra_" + version + "_PUBLIC_") + r"[0-9]{8}\.zip",
        "jdk": re.escape(f"https://github.com/adoptium/temurin25-binaries/releases/download/jdk-{jdk}%2B{build}/"
                         f"OpenJDK25U-jdk_x64_linux_hotspot_{jdk}_{build}.tar.gz"),
    }
    for name, source in recipe["sources"].items():
        if (not isinstance(source, dict) or set(source) != {"url", "sha256", "bytes"} or
                not isinstance(source["url"], str) or not re.fullmatch(patterns[name], source["url"]) or
                not isinstance(source["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", source["sha256"]) or
                type(source["bytes"]) is not int or not 1 <= source["bytes"] <= 768 * 1024**2):
            fail("invalid_recipe", "Require official versioned artifacts and bounded hashes")


def fetch(source, target):
    size, checksum = 0, hashlib.sha256()
    with urllib.request.urlopen(source["url"], timeout=30) as response, target.open("xb") as output:
        while chunk := response.read(min(1024**2, source["bytes"] + 1 - size)):
            size += len(chunk)
            if size > source["bytes"]:
                fail("source_mismatch", "Ghidra/JDK archive exceeds pinned byte count")
            checksum.update(chunk)
            output.write(chunk)
    if size != source["bytes"] or checksum.hexdigest() != source["sha256"]:
        fail("source_mismatch", "Ghidra/JDK archive size/hash mismatch")


def member_path(name):
    path = PurePosixPath(name.rstrip("/"))
    if (not name or "\\" in name or any(ord(c) < 32 for c in name) or path.is_absolute() or
            ".." in path.parts or str(path) != name.rstrip("/") or not path.parts):
        fail("unsafe_archive", "Unsafe archive path")
    return path


def unpack(archive, target, zipped):
    """Extract one root, no devices/hardlinks; internal JDK symlinks become copies."""
    target.mkdir()
    handle = zipfile.ZipFile(archive) if zipped else tarfile.open(archive, "r:gz")
    with handle:
        members = handle.infolist() if zipped else handle.getmembers()
        if not members or len(members) > MAX_FILES:
            fail("unsafe_archive", "Empty or oversized archive index")
        indexed, roots, total = {}, set(), 0
        for item in members:
            name = member_path(item.filename if zipped else item.name)
            if name in indexed:
                fail("unsafe_archive", "Duplicate archive path")
            roots.add(name.parts[0])
            mode = item.external_attr >> 16 if zipped else item.mode
            directory = item.is_dir() if zipped else item.isdir()
            link = None if zipped else item.linkname if item.issym() else None
            regular = not directory and (stat.S_IFMT(mode) in (0, stat.S_IFREG) if zipped else item.isfile())
            if not (directory or regular or link is not None):
                fail("unsafe_archive", "Unsupported archive member type")
            size = item.file_size if zipped else item.size
            total += size
            if size < 0 or total > MAX_EXPANSION:
                fail("unsafe_archive", "Archive exceeds expansion budget")
            indexed[name] = (item, directory, link, mode)
        if len(roots) != 1:
            fail("unsafe_archive", "Require exactly one archive root")
        for name, (_, directory, _, _) in indexed.items():
            if len(name.parts) == 1 and not directory:
                fail("unsafe_archive", "Archive root must be a directory")
            for parent in name.parents:
                if parent in indexed and not indexed[parent][1]:
                    fail("unsafe_archive", "Archive parent is not a directory")

        def regular_target(name, visited):
            if name in visited or name not in indexed:
                fail("unsafe_archive", "Unresolved or cyclic archive link")
            item, directory, link, _ = indexed[name]
            if directory:
                fail("unsafe_archive", "Archive links must resolve to a regular file")
            if link is None:
                return item
            if not link or "\\" in link or PurePosixPath(link).is_absolute() or any(ord(c) < 32 for c in link):
                fail("unsafe_archive", "Unsafe archive link")
            pieces = list(name.parent.parts)
            for piece in link.split("/"):
                if piece == "..":
                    if len(pieces) <= 1:
                        fail("unsafe_archive", "Escaping archive link")
                    pieces.pop()
                elif piece not in ("", "."):
                    pieces.append(piece)
            return regular_target(PurePosixPath(*pieces), visited | {name})

        copied = 0
        for name, (item, directory, link, mode) in indexed.items():
            output = target.joinpath(*name.parts[1:])
            if directory:
                output.mkdir(parents=True, exist_ok=True)
                continue
            selected = regular_target(name, set()) if link is not None else item
            length = selected.file_size if zipped else selected.size
            copied += length
            if copied > MAX_EXPANSION:
                fail("unsafe_archive", "Dereferenced archive exceeds expansion budget")
            output.parent.mkdir(parents=True, exist_ok=True)
            with (handle.open(selected) if zipped else handle.extractfile(selected)) as source, output.open("xb") as dest:
                shutil.copyfileobj(source, dest, 1024**2)
            output.chmod(0o755 if mode & 0o111 else 0o644)


def files_identity(directory):
    from provision import digest
    entries, total = {}, 0
    for path in sorted(directory.rglob("*")):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            fail("invalid_cache", "Nonregular Ghidra/JDK cache member")
        if path.is_dir() or path.name in {MANIFEST, "receipt.json"} and path.parent == directory:
            continue
        total += path.stat().st_size
        if total > MAX_EXPANSION or len(entries) >= MAX_FILES:
            fail("invalid_cache", "Ghidra/JDK cache exceeds payload budget")
        entries[path.relative_to(directory).as_posix()] = {
            "sha256": digest(path), "bytes": path.stat().st_size, "mode": stat.S_IMODE(path.stat().st_mode)}
    if not entries:
        fail("invalid_cache", "Empty Ghidra/JDK payload")
    return entries


WRAPPER = '''#!/usr/bin/python3
"""Pinned noninteractive launcher; caller owns process, workspace and network bounds."""
import os
from pathlib import Path
import sys
root = Path(__file__).resolve().parent
# Use argv for JVM paths: no shell splitting, inherited Java options or host JDK discovery.
env = {key: value for key, value in os.environ.items()
       if key not in {"JAVA_TOOL_OPTIONS", "_JAVA_OPTIONS", "JDK_JAVA_OPTIONS", "CLASSPATH"}}
java = root / "jdk/bin/java"
os.execve(str(java), [str(java), "-Xmx768M", "-XX:ActiveProcessorCount=1",
    "-Djava.awt.headless=true", "-Duser.home=" + env["HOME"],
    "-Djava.io.tmpdir=" + env["TMPDIR"], "-cp",
    str(root / "ghidra/Ghidra/Framework/Utility/lib/Utility.jar"),
    "ghidra.Ghidra", "ghidra.app.util.headless.AnalyzeHeadless", *sys.argv[1:]], env)
'''


def install(recipe, payload, work, runner, root):
    validate(recipe)
    config = work / "ghidra-recipe.json"
    config.write_text(json.dumps(recipe))
    runner.run([sys.executable, str(root / "tools/factory/provision_ghidra.py"),
                "extract", str(config), str(payload)], work, 600)
    wrapper = payload / "ghidra-headless"
    wrapper.write_text(WRAPPER)
    wrapper.chmod(0o755)
    (payload / MANIFEST).write_text(json.dumps(files_identity(payload), sort_keys=True) + "\n")


def smoke(recipe, binary, runner, root):
    from provision import digest, safe_path
    validate(recipe)
    directory = binary.parent
    manifest = safe_path(directory / MANIFEST)
    if not manifest.is_file() or manifest.stat().st_size > 12 * 1024**2:
        fail("invalid_cache", "Missing or oversized Ghidra/JDK manifest")
    if json.loads(manifest.read_text()) != files_identity(directory):
        fail("invalid_cache", "Ghidra/JDK payload identity differs")
    manifest_sha = digest(manifest)
    receipt = directory / "receipt.json"
    if receipt.exists() and json.loads(safe_path(receipt).read_text()).get("smoke", {}).get("payload_sha256") != manifest_sha:
        fail("invalid_cache", "Ghidra/JDK manifest differs from publication receipt")
    version = runner.run([str(directory / "jdk/bin/java"), "-version"], runner.evidence, 20)
    if not version.splitlines() or ('openjdk version "' + recipe["jdk_version"] + '"') not in version.splitlines()[0]:
        fail("smoke_failed", "Actual JDK release differs")
    fixture = runner.evidence / "public-sh2.bin"
    fixture.write_bytes(FIXTURE)
    observation = runner.evidence / "ghidra-public-sh2.json"
    runner.run([str(binary), str(runner.evidence), "public-sh2-project", "-import", str(fixture),
                "-loader", "BinaryLoader", "-processor", LANGUAGE, "-cspec", "default",
                "-loader-baseAddr", "06004000", "-noanalysis", "-max-cpu", "1",
                "-scriptPath", str(root / "tools/factory"), "-postScript",
                "provision_ghidra_smoke.java", str(observation), "-deleteProject"], runner.evidence, 120)
    if not observation.is_file() or observation.is_symlink() or observation.stat().st_size > 4096:
        fail("smoke_failed", "Missing or oversized real headless observation")
    result = json.loads(observation.read_text())
    expected = {"version": recipe["version"], "language": LANGUAGE, "base": "06004000",
                "instructions": ["mov", "rts", "nop"], "constant_return": 42}
    if result != expected:
        fail("smoke_failed", "Actual SH-2 import/disassembly/decompilation differs")
    # A smoke may not mutate the published dependency generation.
    if files_identity(directory) != json.loads(manifest.read_text()):
        fail("invalid_cache", "Headless execution mutated the prepared payload")
    return {"scope": SCOPE, **result, "jdk_version": recipe["jdk_version"],
            "fixture_sha256": digest(fixture), "payload_sha256": manifest_sha}


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] != "extract":
        raise SystemExit("Expected extract <trusted-recipe> <fresh-payload>")
    recipe = json.loads(Path(sys.argv[2]).read_text())
    validate(recipe)
    payload = Path(sys.argv[3])
    for name, source in recipe["sources"].items():
        archive = payload.parent / (name + ".download")
        fetch(source, archive)
        unpack(archive, payload / name, name == "ghidra")
        archive.unlink()
