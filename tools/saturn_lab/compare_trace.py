#!/usr/bin/env python3
"""Compare canonical bounded traces; this does not authenticate reference captures."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

MAX_BYTES = 16 * 1024 * 1024
SCHEMA = "neptune.behaviour-trace.v1"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def integer_data(value, depth=0):
    require(depth <= 32, "observation nesting exceeds 32")
    if isinstance(value, dict):
        require(all(isinstance(key, str) for key in value), "non-string observation key")
        for item in value.values():
            integer_data(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            integer_data(item, depth + 1)
    else:
        require(value is None or type(value) in (int, bool, str), "observations require integer/fixed-point values, not floats")


def validate(trace):
    require(isinstance(trace, dict) and set(trace) == {"schema", "contract", "source", "samples"}, "invalid trace envelope")
    require(trace["schema"] == SCHEMA, "unsupported trace schema")
    contract = trace["contract"]
    require(isinstance(contract, dict) and set(contract) == {"scenario", "ruleset", "observation_schema", "input_sha256", "timebase"}, "invalid scenario contract")
    for key in ("scenario", "ruleset", "observation_schema"):
        require(isinstance(contract[key], str) and contract[key].strip(), "missing " + key)
    require(sha(contract["input_sha256"]), "missing canonical controller recording hash")
    rate = contract["timebase"]
    require(isinstance(rate, dict) and set(rate) == {"numerator", "denominator"}
            and all(type(x) is int and x > 0 for x in rate.values()), "timebase must be an explicit positive rational")
    source = trace["source"]
    require(isinstance(source, dict) and set(source) == {"kind", "build_sha256", "input_lock_sha256", "capture_sha256", "adapter_sha256"}, "invalid source identity")
    require(source["kind"] in {"reference", "implementation", "synthetic"}, "unknown source kind")
    require(all(sha(source[key]) for key in source if key != "kind"), "source hashes must be explicit")
    samples = trace["samples"]
    require(isinstance(samples, list) and 1 <= len(samples) <= 100000, "empty or excessive sample count")
    for frame, sample in enumerate(samples):
        require(isinstance(sample, dict) and set(sample) == {"frame", "observations"}, "invalid sample")
        require(type(sample["frame"]) is int and sample["frame"] == frame, "frames must start at zero and be contiguous")
        require(isinstance(sample["observations"], dict) and sample["observations"], "empty observation sample")
        integer_data(sample["observations"])
    return trace


def first_difference(left, right, path=""):
    if type(left) is not type(right):
        return path or "/"
    if isinstance(left, dict):
        for key in sorted(set(left) | set(right)):
            child = path + "/" + key.replace("~", "~0").replace("/", "~1")
            if key not in left or key not in right:
                return child
            found = first_difference(left[key], right[key], child)
            if found is not None:
                return found
    elif isinstance(left, list):
        for index in range(min(len(left), len(right))):
            found = first_difference(left[index], right[index], path + "/" + str(index))
            if found is not None:
                return found
        if len(left) != len(right):
            return path + "/" + str(min(len(left), len(right)))
    elif left != right:
        return path or "/"
    return None


def compare(reference, candidate):
    validate(reference)
    validate(candidate)
    require(reference["contract"] == candidate["contract"], "scenario/ruleset/timebase/input/schema mismatch; no implicit alignment or resampling")
    report = {"schema": "neptune.trace-comparison.v1", "match": True,
              "reference_sha256": hashlib.sha256(canonical(reference).encode()).hexdigest(),
              "candidate_sha256": hashlib.sha256(canonical(candidate).encode()).hexdigest(),
              "source_kinds": [reference["source"]["kind"], candidate["source"]["kind"]],
              "scope": "Equality of supplied observations only; provenance, emulator accuracy and complete game fidelity are not certified."}
    left, right = reference["samples"], candidate["samples"]
    for index in range(min(len(left), len(right))):
        field = first_difference(left[index]["observations"], right[index]["observations"])
        if field is not None:
            report.update(match=False, first_frame=index, field=field, reason="observation mismatch")
            return report
    if len(left) != len(right):
        report.update(match=False, first_frame=min(len(left), len(right)), field="/samples", reason="trace length mismatch")
    return report


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key: " + key)
        result[key] = value
    return result


def read(path):
    with path.open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    require(len(data) <= MAX_BYTES, "trace exceeds 16MiB; split the experiment")
    return json.loads(data, object_pairs_hook=unique_object)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()
    try:
        result = compare(read(args.reference), read(args.candidate))
        print(json.dumps(result, indent=2))
        return 0 if result["match"] else 1
    except (ValueError, TypeError, KeyError, OSError, RecursionError) as error:
        print(json.dumps({"match": False, "error": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
