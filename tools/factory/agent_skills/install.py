#!/usr/bin/env python3
"""Install or verify the reviewed, hash-pinned Neptune agent skills (no hooks)."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tarfile
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
MAX_ARCHIVE = 128 * 1024**2
MAX_EXPANDED = 512 * 1024**2


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def tree_digest(root):
    result = hashlib.sha256()
    if not root.is_dir() or root.is_symlink():
        raise ValueError(f"Not a regular skill directory: {root}")
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Skill contains a symbolic link: {path}")
        if path.is_file():
            result.update((path.relative_to(root).as_posix() + "\0" + digest(path) + "\n").encode())
    return result.hexdigest()


def relative(value):
    path = PurePosixPath(value)
    if not value or not path.parts or path.is_absolute() or ".." in path.parts or "\\" in value:
        raise ValueError(f"Unsafe relative path: {value}")
    return path


def validate_lock(lock):
    if lock.get("schema") != "neptune.agent-skills.v1" or not lock.get("sources"):
        raise ValueError("Missing or unsupported skill lock")
    names, ids = set(), set()
    for source in lock["sources"]:
        if not re.fullmatch(r"[a-z0-9-]+", source["id"]) or source["id"] in ids:
            raise ValueError("Invalid/duplicate source ID")
        ids.add(source["id"])
        url = urllib.parse.urlsplit(source["archive_url"])
        if url.scheme != "https" or url.username or url.query or url.fragment:
            raise ValueError("Sources require uncredentialed HTTPS archive URLs")
        if url.hostname == "codeload.github.com":
            revision = source["revision"]
            if not re.fullmatch(r"[0-9a-f]{40}", revision):
                raise ValueError("Git sources require full commit identities")
            if url.path != f'/{source["repository"]}/tar.gz/{revision}':
                raise ValueError("Archive URL does not match pinned repository/revision")
        elif url.hostname == "registry.npmjs.org":
            if source["id"] != "rea" or url.path != f'/rea-agents/-/rea-agents-{source["revision"]}.tgz':
                raise ValueError("Unsupported npm source")
        else:
            raise ValueError("Unsupported source host")
        if not re.fullmatch(r"[0-9a-f]{64}", source["archive_sha256"]):
            raise ValueError("Missing archive hash")
    for skill in all_skills(lock):
        if not re.fullmatch(r"[a-z0-9-]{1,64}", skill["name"]) or skill["name"] in names:
            raise ValueError("Invalid/duplicate skill name")
        names.add(skill["name"])
        relative(skill["path"])
        if not re.fullmatch(r"[0-9a-f]{64}", skill["tree_sha256"]):
            raise ValueError("Missing skill tree hash")
    if not names:
        raise ValueError("Empty skill selection")


def all_skills(lock):
    return [skill for source in lock["sources"] for skill in source["skills"]] + lock.get("local_skills", [])


def acquire(source, archives, download):
    path = archives / (source["id"] + ".tar.gz")
    if not path.exists():
        if not download:
            raise ValueError(f"Missing cached archive {path}; use --download in preparation")
        archives.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=archives, delete=False) as output:
            temporary = Path(output.name)
            try:
                with urllib.request.urlopen(source["archive_url"], timeout=45) as response:
                    size = 0
                    while block := response.read(1024**2):
                        size += len(block)
                        if size > MAX_ARCHIVE:
                            raise ValueError("Archive exceeds download budget")
                        output.write(block)
                output.close()
                if digest(temporary) != source["archive_sha256"]:
                    raise ValueError("Downloaded archive hash mismatch")
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
    if path.is_symlink() or path.stat().st_size > MAX_ARCHIVE or digest(path) != source["archive_sha256"]:
        raise ValueError(f"Cached archive identity mismatch: {path}")
    return path


def unpack(archive, destination, selected_paths):
    total, roots = 0, set()
    with tarfile.open(archive, "r:gz") as source:
        for count, member in enumerate(source, 1):
            path = relative(member.name)
            roots.add(path.parts[0])
            if count > 20000 or len(roots) != 1:
                raise ValueError("Archive has unsupported layout")
            child = PurePosixPath(*path.parts[1:])
            selected = any(child == PurePosixPath(item) or PurePosixPath(item) in child.parents for item in selected_paths)
            if (member.issym() or member.islnk()) and not selected:
                continue  # Never materialize unrelated upstream convenience links.
            if not (member.isfile() or member.isdir()):
                raise ValueError("Archive has unsupported layout, links or special files")
            target = destination.joinpath(*path.parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                total += member.size
                if total > MAX_EXPANDED:
                    raise ValueError("Archive exceeds extraction budget")
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.extractfile(member) as incoming, target.open("xb") as output:
                    shutil.copyfileobj(incoming, output)
                target.chmod(0o644 | (member.mode & 0o111))
    if len(roots) != 1:
        raise ValueError("Empty archive")
    return destination / next(iter(roots))


def verify_trees(lock, generation):
    for skill in all_skills(lock):
        path = generation / "skills" / skill["name"]
        if not (path / "SKILL.md").is_file() or tree_digest(path) != skill["tree_sha256"]:
            raise ValueError(f"Installed skill identity mismatch: {skill['name']}")


def freeze_generation(generation):
    for path in sorted(generation.rglob("*"), reverse=True):
        path.chmod(path.stat().st_mode & ~0o222)
    generation.chmod(generation.stat().st_mode & ~0o222)


def install(lock_path, cache, destination, download=False, verify=False):
    lock = json.loads(lock_path.read_text())
    validate_lock(lock)
    generation = cache / digest(lock_path)
    if not verify and not generation.exists():
        cache.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".prepare-skills-", dir=cache) as temp:
            stage = Path(temp)
            (stage / "skills").mkdir()
            (stage / "licenses").mkdir()
            for source in lock["sources"]:
                extracted = stage / source["id"]
                extracted.mkdir()
                source_root = unpack(acquire(source, cache / "archives", download), extracted,
                                     [skill["path"] for skill in source["skills"]])
                for skill in source["skills"]:
                    shutil.copytree(source_root / skill["path"], stage / "skills" / skill["name"])
                for license_path in source_root.glob("LICENSE*"):
                    if license_path.is_file():
                        shutil.copy2(license_path, stage / "licenses" / (source["id"] + "-" + license_path.name))
                shutil.rmtree(extracted)
            for skill in lock.get("local_skills", []):
                shutil.copytree(lock_path.parent / skill["path"], stage / "skills" / skill["name"])
            verify_trees(lock, stage)
            (stage / "receipt.json").write_text(json.dumps({"lock_sha256": digest(lock_path), "skills": len(all_skills(lock))}, indent=2) + "\n")
            stage.replace(generation)
    verify_trees(lock, generation)
    if not verify:
        freeze_generation(generation)
        destination.mkdir(parents=True, exist_ok=True)
    for skill in all_skills(lock):
        link = destination / skill["name"]
        target = generation / "skills" / skill["name"]
        if link.is_symlink() and link.resolve() == target.resolve():
            continue
        if verify or link.exists() or link.is_symlink():
            raise ValueError(f"Missing or conflicting skill registration: {link}")
        link.symlink_to(os.path.relpath(target, destination), target_is_directory=True)
    return {"status": "verified", "skills": len(all_skills(lock)), "generation": str(generation.resolve()), "destination": str(destination.resolve()), "lock_sha256": digest(lock_path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, default=HERE / "skills-lock.json")
    parser.add_argument("--cache", type=Path, default=ROOT / ".factory-tools/agent-skills")
    parser.add_argument("--dest", type=Path, default=ROOT / ".agents/skills")
    parser.add_argument("--download", action="store_true", help="Acquire missing archives in the preparation environment")
    parser.add_argument("--verify", action="store_true", help="Verify installed bytes and links offline without writes")
    args = parser.parse_args()
    try:
        print(json.dumps(install(args.lock, args.cache, args.dest, args.download, args.verify), sort_keys=True))
    except (OSError, ValueError, KeyError, tarfile.TarError) as error:
        parser.exit(1, f"Skill preparation failed: {error}\n")


if __name__ == "__main__":
    main()
