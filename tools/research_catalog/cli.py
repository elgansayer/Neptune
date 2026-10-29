#!/usr/bin/env python3
"""Validate/report feature evidence metadata; never execute recorded commands."""
import argparse
from datetime import date
import json
from pathlib import Path
import re
import sys

DEFAULT = Path(__file__).resolve().parents[2] / "docs/restart/feature-catalogue.json"
ID = re.compile(r"[a-z][a-z0-9-]*\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def string(value):
    return isinstance(value, str) and bool(value.strip())


def digest(value, pattern=SHA256):
    return isinstance(value, str) and bool(pattern.fullmatch(value))


def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        require(key not in obj, f"Duplicate JSON key: {key}")
        obj[key] = value
    return obj


def validate(data):
    require(isinstance(data, dict), "Catalogue must be an object")
    require(type(data.get("schema_version")) is int and data["schema_version"] == 1,
            "Unsupported catalogue schema_version")
    require(data.get("coverage_scope") == "starter", "Schema 1 is a starter catalogue, not exhaustive coverage")
    sources = data.get("sources")
    features = data.get("features")
    require(isinstance(sources, list) and sources, "Missing source catalogue")
    require(isinstance(features, list) and features, "No features: empty discovery is not success")
    source_ids = set()
    for source in sources:
        require(isinstance(source, dict), "Invalid source record")
        sid = source.get("id")
        require(isinstance(sid, str) and ID.fullmatch(sid), "Invalid source ID")
        require(sid not in source_ids, f"Duplicate source: {sid}")
        source_ids.add(sid)
        require(string(source.get("url")) and source["url"].startswith("https://"), f"{sid}: HTTPS source URL required")
        require(string(source.get("checked_on")), f"{sid}: checked_on required")
        date.fromisoformat(source["checked_on"])
        require(string(source.get("description")), f"{sid}: description required")
    indexed = {}
    for feature in features:
        require(isinstance(feature, dict), "Invalid feature record")
        fid = feature.get("id")
        require(isinstance(fid, str) and ID.fullmatch(fid), "Invalid feature ID")
        require(fid not in indexed, f"Duplicate feature: {fid}")
        indexed[fid] = feature
        for field in ("title", "reference_version"):
            require(string(feature.get(field)), f"{fid}: {field} required")
        require(feature.get("reference") in ("power-bomberman", "saturn", "neptune"), f"{fid}: unknown reference")
        require(feature.get("profile") in ("saturn", "neptune", "shared"), f"{fid}: unknown profile")
        status = feature.get("reference_status")
        require(status in ("unknown", "documented", "reported", "observed", "not_applicable"), f"{fid}: unknown reference status")
        implementation = feature.get("implementation_status")
        require(implementation in ("unaudited", "planned", "in_progress", "verified"), f"{fid}: unknown implementation status")
        refs = feature.get("source_ids")
        require(isinstance(refs, list) and all(isinstance(x, str) for x in refs), f"{fid}: invalid source IDs")
        require(len(refs) == len(set(refs)) and set(refs) <= source_ids, f"{fid}: duplicate/unknown source IDs")
        if status in ("documented", "reported"):
            require(bool(refs), f"{fid}: source required for reference claim")
        if feature["reference"] == "neptune":
            require(status == "not_applicable", f"{fid}: Neptune requirements are not reference observations")
        else:
            require(status != "not_applicable", f"{fid}: external reference needs an explicit evidence status")
        checks = feature.get("acceptance")
        require(isinstance(checks, list) and checks and all(string(x) for x in checks), f"{fid}: acceptance required")
        issue = feature.get("issue")
        require(type(issue) is int and issue > 0, f"{fid}: positive issue number required")
        deps = feature.get("depends_on")
        require(isinstance(deps, list) and all(isinstance(x, str) for x in deps), f"{fid}: invalid dependencies")
        require(len(deps) == len(set(deps)), f"{fid}: duplicate dependencies")
        observations = feature.get("observations")
        require(isinstance(observations, list), f"{fid}: observations must be an array")
        for observation in observations:
            require(isinstance(observation, dict), f"{fid}: invalid observation")
            for field in ("input_manifest_sha256", "artifact_sha256"):
                require(digest(observation.get(field)), f"{fid}: observation {field} required")
            for field in ("scenario", "command", "limitations"):
                require(string(observation.get(field)), f"{fid}: observation {field} required")
        if status == "observed":
            require(bool(observations), f"{fid}: observed claim needs pinned observation metadata")
            require(feature["reference_version"] != "unselected", f"{fid}: observed build cannot be unselected")
        verification = feature.get("verification")
        if verification is not None:
            require(isinstance(verification, dict), f"{fid}: invalid verification")
            require(digest(verification.get("tested_commit"), COMMIT), f"{fid}: tested commit required")
            require(digest(verification.get("artifact_sha256")), f"{fid}: verification artifact required")
            require(string(verification.get("command")), f"{fid}: verification command required")
            require(verification.get("result") in ("pass", "fail"), f"{fid}: verification result required")
        if implementation == "verified":
            require(verification is not None and verification["result"] == "pass", f"{fid}: verified claim needs passing evidence metadata")
            if feature["reference"] != "neptune":
                require(status == "observed", f"{fid}: reference parity needs observed reference evidence")
    for fid, feature in indexed.items():
        require(all(dep in indexed for dep in feature["depends_on"]), f"{fid}: unknown dependency")
    visiting, visited = set(), set()

    def visit(fid):
        require(fid not in visiting, f"Dependency cycle at {fid}")
        if fid in visited:
            return
        visiting.add(fid)
        for dep in indexed[fid]["depends_on"]:
            visit(dep)
        visiting.remove(fid)
        visited.add(fid)

    for fid in indexed:
        visit(fid)
    return data


def load(path):
    return validate(json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object))


def report(data):
    features = data["features"]
    observed = sum(f["reference_status"] == "observed" for f in features)
    verified = sum(f["implementation_status"] == "verified" for f in features)
    lines = ["# Feature catalogue", "", f"{len(features)} starter entries; {observed} observed references; {verified} verified implementations.",
             "", "Counts describe submitted metadata, not measured completeness. Evidence has not been executed or independently verified by this tool.", "",
             "| ID | Feature | Reference status | Neptune status | Issue |", "| --- | --- | --- | --- | --- |"]
    for feature in sorted(features, key=lambda item: item["id"]):
        title = feature["title"].replace("|", "\\|").replace("\n", " ")
        issue = feature["issue"]
        lines.append(f"| {feature['id']} | {title} | {feature['reference_status']} | {feature['implementation_status']} | [#{issue}](https://github.com/elgansayer/Neptune-Bomberman/issues/{issue}) |")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "report"))
    parser.add_argument("--catalogue", type=Path, default=DEFAULT)
    args = parser.parse_args()
    try:
        data = load(args.catalogue)
        print(report(data) if args.command == "report" else f"Valid metadata: {len(data['features'])} starter entries; evidence not executed.", end="\n" if args.command == "validate" else "")
    except (ValueError, OSError, RecursionError) as exc:
        print(f"Catalogue error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
