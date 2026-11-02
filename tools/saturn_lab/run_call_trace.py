#!/usr/bin/env python3
"""Explicit matched-core state-import experiment, never re-pins historical states.

Use the existing guarded, credential-free resource admission. Compare separate
fresh processes for reference, observer-disabled and observer-enabled modes.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import resource
import sys
import statistics
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/factory"))
import provision
import provision_call_trace_abi as observer
import probe_kernel
import state_graphics

REFERENCE_CORE = "c862380e94ba749e020e58ba5b2ec483f88a60ced38171fc63fda306b2f54f5e"
MODULES = {
    "frontend.py": "84b29f26338d31a0a4f546e75ecca88460f457f5463ae20dbb4a135ca7f1c8da",
    "cli.py": "f7bbc70633641dde5f8da9b5674dd4887522d02394b646034f9a98c2c88c2e50",
    "media.py": "baf71700a68ed4c82b35be7fc96b2733d2b466d7b96c12c2c505d672d73d3664",
    "log_shim.c": "cb32b7463692ee037bcd157637ed1c07f5005daa6e4819a77f02a66c09cf45a5",
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    raw = probe_kernel.read_bounded(path, 2 * 1024**2)
    def unique(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate metadata key")
            result[key] = value
        return result
    value = json.loads(raw, object_pairs_hook=unique)
    if not isinstance(value, dict):
        raise ValueError("Expected bounded metadata object")
    return value


def confined(root, relative):
    if not isinstance(relative, str) or "\\" in relative:
        raise ValueError("Invalid reference-relative path")
    path = PurePosixPath(relative)
    if not path.parts or path.is_absolute() or ".." in path.parts or path.as_posix() != relative:
        raise ValueError("Unsafe reference-relative path")
    target = root.joinpath(*path.parts)
    return provision.safe_path(target)


def reference(root, lock_path, expected_lock):
    if not re.fullmatch(r"[0-9a-f]{64}", expected_lock):
        raise ValueError("Require the coordinator's expected original-lock file hash")
    if sha(probe_kernel.read_bounded(lock_path, 2 * 1024**2)) != expected_lock:
        raise ValueError("Original lock differs before importing any reference source")
    lock = read_json(lock_path)
    profile = read_json(confined(root, lock["inputs"]["settings"]))
    if set(profile["source_modules"]) != set(MODULES):
        raise ValueError("Unsupported original reference frontend generation")
    paths = []
    for name, expected in MODULES.items():
        item = profile["source_modules"][name]
        path = confined(root, item["path"])
        if item["sha256"] != expected or sha(probe_kernel.read_bounded(path, 1024**2)) != expected:
            raise ValueError("Reference callback/support source differs before execution")
        paths.append(path)
    entry = confined(root, profile["frontend_path"])
    if (entry.name != "frontend.py" or profile["frontend_sha256"] != MODULES["frontend.py"] or
            len({path.parent for path in paths}) != 1 or entry not in paths):
        raise ValueError("Ambiguous reference callback import directory")
    sys.path.insert(0, str(entry.parent))
    specification = importlib.util.spec_from_file_location("neptune_pinned_reference_frontend", entry)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    module.verify_lock(root, lock)
    seed = module.validate_profile(root, profile)
    identity = module.checkpoint_identity(root, lock, profile)
    if (identity["core_sha256"] != REFERENCE_CORE or profile["region"] != "usa" or
            lock["region"] != "usa" or profile["options"].get("beetle_saturn_sh2_jit") != "disabled"):
        raise ValueError("Require the accepted USA interpreter-only reference")
    return module, lock, profile, identity, seed


def resident(state, kernel):
    parsed = state_graphics.parse(state)
    high = state_graphics.cpu_words(state_graphics.field(parsed, "MAIN", "WorkRAMH", 0x100000), "little")
    regions = []
    for address, size in ((0x0600B934, 28), (0x0600B96C, 2), (0x0600B984, 4)):
        offset = address - probe_kernel.BASE
        expected = kernel[offset:offset + size]
        if high[address - 0x06000000:address - 0x06000000 + size] != expected:
            raise ValueError("Observed original code/literal witness is absent from High Work RAM")
        regions.append({"address": f"0x{address:08x}", "bytes": size, "sha256": sha(expected)})
    return regions


def run(args):
    if type(args.frames) is not int or not 1 <= args.frames <= 600:
        raise ValueError("Require 1..600 bounded original frames")
    if type(args.pairs) is not int or not 1 <= args.pairs <= 64:
        raise ValueError("Require a declared 1..64-pair observation limit")
    if args.output.exists():
        raise ValueError("Use fresh private experiment output; never overwrite reference evidence")
    args.output.mkdir(mode=0o700, parents=True)
    result = {"schema": "neptune.explicit-call-trace-experiment.v1", "mode": args.mode,
              "status": "failure", "driver_sha256": sha(Path(__file__).read_bytes()),
              "source_modules": {"observer": sha((ROOT / "tools/factory/provision_call_trace_abi.py").read_bytes()),
                                 "state_parser": sha(Path(state_graphics.__file__).read_bytes()),
                                 "kernel_identity": sha(Path(probe_kernel.__file__).read_bytes())},
              "state_import": "explicit controlled import only; historical checkpoint/lock never modified",
              "model_calls": 0}
    driver = None
    phase = "input_identity"
    try:
        root = args.reference_root
        module, lock, profile, identity, seed = reference(root, args.lock, args.expected_lock)
        original, state = module.read_checkpoint(args.checkpoint, identity)
        kernel = probe_kernel.kernel_bytes(args.kernel)
        if any(not os.statvfs(path).f_flag & os.ST_RDONLY
               for path in (root, args.checkpoint.parent, args.kernel.parent)):
            raise ValueError("Run with original media/checkpoint/kernel mounted read-only")
        source_witness = resident(state, kernel)
        core = confined(root, lock["inputs"]["emulator"])
        if args.mode != "reference":
            if args.prepared is None:
                raise ValueError("Instrumented modes require an independently prepared immutable generation")
            _, _, recipe = provision.identity("beetle-saturn-call-trace", ROOT)
            core = provision.cached(args.prepared, "beetle-saturn-call-trace", recipe, ROOT)
            if not os.statvfs(args.prepared).f_flag & os.ST_RDONLY:
                raise ValueError("Prepared observer generation must be mounted read-only")
            result["prepared_recipe_sha256"] = recipe
        result.update(reference_identity=identity, reference_lock_file_sha256=args.expected_lock,
                      reference_checkpoint_file_sha256=sha(args.checkpoint.read_bytes()),
                      reference_state_sha256=original["state_sha256"], reference_frame=original["frame"],
                      selected_core_sha256=provision.digest(core), resident_code_before=source_witness)
        phase = "core_load_and_explicit_state_import"
        save = args.output / "save"
        save.mkdir()
        disc = confined(root, lock["inputs"]["disc"])
        for name in (disc.stem + ".smpc", "mednafen_saturn_libretro_shared.smpc"):
            (save / name).write_bytes(bytes(seed))
        driver = module.Core(core, root / profile["system_directory"], save, profile["options"],
                             confined(root, profile["log_shim"]["path"]))
        av = driver.load(disc, profile["controller_devices"])
        driver.restore(state)
        driver.frame, driver.video = original["frame"], original["last_video"]
        canonical_import = driver.save_state()
        resident(canonical_import, kernel)
        result.update(av=av, imported_state_bytes=len(canonical_import), imported_state_sha256=sha(canonical_import))
        tracer = None
        if args.mode != "reference":
            tracer = observer.Trace(driver.dll)
            if args.mode == "enabled":
                tracer.start(args.pairs)
        phase = "original_frame_execution"
        frames = []
        started = time.monotonic()
        for _ in range(args.frames):
            if args.mode == "enabled":
                tracer.frame(driver.frame)
            frames.append(driver.step([0] * 12))
        elapsed = time.monotonic() - started
        final = driver.save_state()
        witness = resident(final, kernel)
        (args.output / "final.state").write_bytes(final)
        (args.output / "observations.json").write_text(json.dumps({"av": av, "frames": frames}, sort_keys=True) + "\n")
        result.update(frames=len(frames), final_state_sha256=sha(final), resident_code_after=witness,
                      frame_observations_sha256=module.digest(frames),
                      video_sha256=module.digest([frame["video"] for frame in frames]),
                      audio_sha256=module.digest([(frame["audio_sha256"], frame["audio_frames"]) for frame in frames]),
                      audio_frames=sum(frame["audio_frames"] for frame in frames),
                      emulation_wall_seconds=elapsed, input_polls=driver.polls,
                      delivered_masks=[sorted(values) for values in driver.delivered])
        if args.mode == "enabled":
            phase = "bounded_original_call_validation"
            trace = tracer.finish()
            raw = (json.dumps(trace, indent=2, sort_keys=True) + "\n").encode()
            (args.output / "call-trace.json").write_bytes(raw)
            result.update(trace_sha256=sha(raw), pairs=trace["pairs"])
        result["status"] = "success"
        return result
    except Exception as error:
        result["error"] = {"phase": phase, "type": type(error).__name__, "reason": str(error)}
        raise
    finally:
        try:
            if driver is not None:
                driver.close()
        except Exception as error:
            result["status"] = "failure"
            result["cleanup_error"] = {"type": type(error).__name__, "reason": str(error)}
            raise
        finally:
            (args.output / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


def decoded_trace(value):
    records = []
    if value.get("schema") != "neptune.original-master-call-trace.v1" or not isinstance(value.get("records"), list):
        raise ValueError("Missing versioned original-call records")
    if not 2 <= len(value["records"]) <= observer.CAPACITY:
        raise ValueError("Empty/oversized original-call records")
    for item in value["records"]:
        if not isinstance(item, dict) or set(item) != {name for name, _ in observer.Record._fields_}:
            raise ValueError("Malformed original-call record")
        record = observer.Record()
        for name, _ in record._fields_:
            if name == "r":
                values = item[name]
                if not isinstance(values, list) or len(values) != 16 or any(type(n) is not int or not 0 <= n <= 0xFFFFFFFF for n in values):
                    raise ValueError("Invalid register vector")
                record.r[:] = values
            else:
                low, high = (-0x80000000, 0x7FFFFFFF) if name == "timestamp" else (0, 0xFFFFFFFF)
                if type(item[name]) is not int or not low <= item[name] <= high:
                    raise ValueError("Invalid trace scalar")
                setattr(record, name, item[name])
        records.append(record)
    fields = {name for name, _ in observer.Status._fields_}
    if not isinstance(value.get("status"), dict) or set(value["status"]) != fields:
        raise ValueError("Missing exact trace status")
    status = observer.Status()
    for name in fields:
        number = value["status"][name]
        if type(number) is not int or not 0 <= number <= 0xFFFFFFFF:
            raise ValueError("Invalid trace status scalar")
        setattr(status, name, number)
    expected = observer.validate(records, status)
    if value != expected:
        raise ValueError("Trace summary differs from independently validated records")
    return expected


def compare(directories):
    if len(directories) != 6 or len({path.resolve() for path in directories}) != 6:
        raise ValueError("Require two distinct fresh runs in each of three modes")
    runs = []
    for directory in directories:
        report = read_json(directory / "result.json")
        if report.get("schema") != "neptune.explicit-call-trace-experiment.v1" or report.get("status") != "success":
            raise ValueError("A required real run is missing or failed")
        observations = read_json(directory / "observations.json")
        frames = observations.get("frames")
        if not isinstance(frames, list) or not 1 <= len(frames) <= 600 or report["frames"] != len(frames):
            raise ValueError("Missing/empty original frame observations")
        canonical = lambda value: sha(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())
        if (canonical(frames) != report["frame_observations_sha256"] or
                canonical([frame["video"] for frame in frames]) != report["video_sha256"] or
                canonical([(frame["audio_sha256"], frame["audio_frames"]) for frame in frames]) != report["audio_sha256"] or
                sum(frame["audio_frames"] for frame in frames) != report["audio_frames"] or
                observations["av"] != report["av"]):
            raise ValueError("Original frame/video/audio artefact differs from its report")
        for index, frame in enumerate(frames):
            if frame["frame"] != report["reference_frame"] + index or frame["inputs"] != [0] * 12:
                raise ValueError("Nonconsecutive frame or unexpected controller input")
        state = probe_kernel.read_bounded(directory / "final.state", state_graphics.MAX_STATE)
        if sha(state) != report["final_state_sha256"]:
            raise ValueError("Final private state artefact differs")
        elapsed = report["emulation_wall_seconds"]
        if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed <= 0:
            raise ValueError("Missing real bounded timing observation")
        if report["mode"] == "enabled":
            raw = probe_kernel.read_bounded(directory / "call-trace.json", 2 * 1024**2)
            trace = decoded_trace(read_json(directory / "call-trace.json"))
            if sha(raw) != report["trace_sha256"] or trace["pairs"] != report["pairs"]:
                raise ValueError("Original call trace differs from its report")
        runs.append(report)
    groups = {mode: [run for run in runs if run["mode"] == mode]
              for mode in ("reference", "disabled", "enabled")}
    if any(len(group) != 2 for group in groups.values()):
        raise ValueError("Require exactly two runs per declared mode")
    baseline = groups["reference"][0]
    equal = ("driver_sha256", "source_modules", "reference_identity", "reference_lock_file_sha256",
             "reference_checkpoint_file_sha256", "reference_state_sha256", "reference_frame", "frames",
             "av", "imported_state_bytes", "imported_state_sha256", "final_state_sha256",
             "frame_observations_sha256", "video_sha256", "audio_sha256", "audio_frames",
             "resident_code_before", "resident_code_after", "input_polls", "delivered_masks")
    for run in runs:
        if any(run.get(key) != baseline.get(key) or key not in run for key in equal):
            raise ValueError("Reference/disabled/enabled repeatability or state import differs")
    if any(run["selected_core_sha256"] != REFERENCE_CORE for run in groups["reference"]):
        raise ValueError("Wrong unmodified reference core")
    patched = groups["disabled"] + groups["enabled"]
    if (len({run["selected_core_sha256"] for run in patched}) != 1 or
            patched[0]["selected_core_sha256"] == REFERENCE_CORE or
            len({run.get("prepared_recipe_sha256") for run in patched}) != 1 or
            not patched[0].get("prepared_recipe_sha256")):
        raise ValueError("Instrumented-core identity differs or is missing")
    if any(groups["enabled"][0].get(key) != groups["enabled"][1].get(key) for key in ("pairs", "trace_sha256")):
        raise ValueError("Real original caller traces are not repeatable")
    medians = {mode: statistics.median(run["emulation_wall_seconds"] for run in group)
               for mode, group in groups.items()}
    return {"schema": "neptune.call-observer-comparison.v1", "status": "success",
            "runs": 6, "repeats_per_mode": 2, "frames_per_run": baseline["frames"],
            "reference_core_sha256": REFERENCE_CORE, "instrumented_core_sha256": patched[0]["selected_core_sha256"],
            "equal_observations": list(equal), "pairs_per_enabled_run": groups["enabled"][0]["pairs"],
            "trace_sha256": groups["enabled"][0]["trace_sha256"],
            "median_emulation_wall_seconds": medians,
            "enabled_vs_disabled_wall_ratio": medians["enabled"] / medians["disabled"],
            "disabled_vs_reference_wall_ratio": medians["disabled"] / medians["reference"],
            "timing_scope": "whole bounded run; recorder stops at its declared pair limit; not hardware cycles or steady-state full tracing",
            "whole_game_fidelity_established": False}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    # Match the accepted reference worker's address-space/core-dump bounds.
    # Wall-clock and namespace/process lifetime are owned by the existing guard.
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024**2, 64 * 1024**2))
    resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
    if argv and argv[0] == "compare":
        parser = argparse.ArgumentParser(description="Check all six private original-run artefacts and traces")
        parser.add_argument("directories", type=Path, nargs=6)
        parser.add_argument("--report", type=Path, required=True)
        args = parser.parse_args(argv[1:])
        result = compare(args.directories)
        descriptor = os.open(args.report, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w") as output:
            output.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"status": result["status"], "runs": result["runs"]}))
        return 0
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reference-root", type=Path, required=True)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--expected-lock", required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--prepared", type=Path)
    parser.add_argument("--mode", choices=("reference", "disabled", "enabled"), required=True)
    parser.add_argument("--frames", type=int, default=120)
    parser.add_argument("--pairs", type=int, default=64)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = run(args)
    print(json.dumps({key: result[key] for key in ("status", "mode", "frames", "selected_core_sha256")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
