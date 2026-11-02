#!/usr/bin/env python3
"""Separate bounded original-context experiment; historical locks stay unchanged.

Use the existing guarded, credential-free resource admission. Compare separate
fresh processes for reference, observer-disabled and observer-enabled modes.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import sys
import statistics
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/factory"))
import provision
import provision_context_trace_abi as observer
import probe_kernel
import state_graphics

from run_call_trace import REFERENCE_CORE, reference, confined, read_json, sha


def source_words(kernel):
    return [int.from_bytes(kernel[address-probe_kernel.BASE+2*i:address-probe_kernel.BASE+2*i+2], "big")
            for address, count in observer.WITNESS_RANGES for i in range(count)]


def resident(state, kernel):
    parsed = state_graphics.parse(state)
    high = state_graphics.cpu_words(state_graphics.field(parsed, "MAIN", "WorkRAMH", 0x100000), "little")
    regions = []
    for address, count in observer.WITNESS_RANGES:
        size = count * 2
        expected = kernel[address-probe_kernel.BASE:address-probe_kernel.BASE+size]
        if high[address-0x06000000:address-0x06000000+size] != expected:
            raise ValueError("Original context source witness is absent from High Work RAM")
        regions.append({"address": f"0x{address:08x}", "bytes": size, "sha256": sha(expected)})
    return regions


def run(args):
    if type(args.profile) is not int or args.profile not in (1, 2, 3):
        raise ValueError("Require explicit fresh/resumed/yield profile 1..3")
    if type(args.frames) is not int or not 1 <= args.frames <= 600:
        raise ValueError("Require 1..600 bounded original frames")
    if type(args.pairs) is not int or not 1 <= args.pairs <= 16:
        raise ValueError("Require a declared 1..16-cycle observation limit")
    if type(args.start_frames) is not int or not 0 <= args.start_frames <= args.frames:
        raise ValueError("Require a bounded port-zero Start pulse")
    if args.output.exists():
        raise ValueError("Use fresh private experiment output; never overwrite reference evidence")
    args.output.mkdir(mode=0o700, parents=True)
    result = {"schema": "neptune.explicit-context-trace-experiment.v1", "mode": args.mode,
              "status": "failure", "driver_sha256": sha(Path(__file__).read_bytes()),
              "port_zero_start_frames": args.start_frames, "context_profile": args.profile,
              "source_modules": {"observer": sha((ROOT / "tools/factory/provision_context_trace_abi.py").read_bytes()),
                                 "state_parser": sha(Path(state_graphics.__file__).read_bytes()),
                                 "kernel_identity": sha(Path(probe_kernel.__file__).read_bytes()),
                                 "reference_adapter": sha((ROOT / "tools/saturn_lab/run_call_trace.py").read_bytes())},
              "state_import": "explicit controlled import only; historical checkpoint/lock never modified",
              "model_calls": 0}
    driver, tracer, frames = None, None, []
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
            _, _, recipe = provision.identity("beetle-saturn-context-trace", ROOT)
            core = provision.cached(args.prepared, "beetle-saturn-context-trace", recipe, ROOT)
            if not os.statvfs(args.prepared).f_flag & os.ST_RDONLY:
                raise ValueError("Prepared observer generation must be mounted read-only")
            result["prepared_recipe_sha256"] = recipe
        result.update(reference_identity=identity, reference_lock_file_sha256=args.expected_lock,
                      reference_checkpoint_file_sha256=sha(args.checkpoint.read_bytes()),
                      original_kernel_sha256=sha(kernel),
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
                tracer.start(args.profile, args.pairs, source_words(kernel))
                if tracer.witness() != source_words(kernel):
                    raise ValueError("Native source witness differs from the identified original kernel")
        phase = "original_frame_execution"
        started = time.monotonic()
        for relative in range(args.frames):
            if args.mode == "enabled":
                tracer.frame(driver.frame)
            frames.append(driver.step([8 if relative < args.start_frames else 0] + [0] * 11))
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
            phase = "bounded_original_context_validation"
            trace = tracer.finish()
            raw = (json.dumps(trace, indent=2, sort_keys=True) + "\n").encode()
            (args.output / "context-trace.json").write_bytes(raw)
            result.update(trace_sha256=sha(raw), pairs=trace["completed_cycles"])
        result["status"] = "success"
        return result
    except Exception as error:
        result["error"] = {"phase": phase, "type": type(error).__name__, "reason": str(error)}
        raise
    finally:
        result.update(completed_original_frames=len(frames), original_game_bytes_executed=bool(frames))
        if result["status"] != "success" and frames:
            (args.output / "partial-observations.json").write_text(json.dumps({"frames": frames}, sort_keys=True) + "\n")
        if tracer is not None and tracer.started and result["status"] != "success":
            try:
                tracer.dll.neptune_context_stop()
                records, status = tracer.snapshot()
                result["failed_trace_status"] = observer.serialise(status)
                diagnostic = {"schema": "neptune.failed-context-trace-diagnostic.v1", "accepted": False,
                              "status": result["failed_trace_status"],
                              "records": [observer.serialise(record) for record in records],
                              "first_mismatched_source_witness": tracer.witness(True)}
                (args.output / "failed-context-records.json").write_text(json.dumps(diagnostic, indent=2, sort_keys=True) + "\n")
            except Exception as error:
                result["diagnostic_error"] = {"type": type(error).__name__, "reason": str(error)}
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
    if value.get("schema") != "neptune.original-master-context-trace.v1" or not isinstance(value.get("records"), list):
        raise ValueError("Missing versioned original-context records")
    if not 3 <= len(value["records"]) <= observer.CAPACITY:
        raise ValueError("Empty/oversized original-context records")
    for item in value["records"]:
        if not isinstance(item, dict) or set(item) != {name for name, _ in observer.Record._fields_}:
            raise ValueError("Malformed original-call record")
        record = observer.Record()
        for name, _ in record._fields_:
            if isinstance(getattr(record, name), observer.C.Array):
                values = item[name]
                if (not isinstance(values, list) or len(values) != len(getattr(record, name)) or
                        any(type(n) is not int or not 0 <= n <= 0xFFFFFFFF for n in values)):
                    raise ValueError("Invalid context snapshot vector")
                getattr(record, name)[:] = values
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
        if report.get("schema") != "neptune.explicit-context-trace-experiment.v1" or report.get("status") != "success":
            raise ValueError("A required real run is missing or failed")
        observations = read_json(directory / "observations.json")
        frames = observations.get("frames")
        if not isinstance(frames, list) or not 1 <= len(frames) <= 600 or report["frames"] != len(frames):
            raise ValueError("Missing/empty original frame observations")
        if (report.get("original_game_bytes_executed") is not True or
                report.get("completed_original_frames") != len(frames) or
                type(report.get("context_profile")) is not int or report["context_profile"] not in (1, 2, 3)):
            raise ValueError("Missing completed original frames or declared context profile")
        canonical = lambda value: sha(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())
        if (canonical(frames) != report["frame_observations_sha256"] or
                canonical([frame["video"] for frame in frames]) != report["video_sha256"] or
                canonical([(frame["audio_sha256"], frame["audio_frames"]) for frame in frames]) != report["audio_sha256"] or
                sum(frame["audio_frames"] for frame in frames) != report["audio_frames"] or
                observations["av"] != report["av"]):
            raise ValueError("Original frame/video/audio artefact differs from its report")
        pulse = report.get("port_zero_start_frames")
        if type(pulse) is not int or not 0 <= pulse <= len(frames):
            raise ValueError("Missing bounded controller pulse declaration")
        for index, frame in enumerate(frames):
            masks = [8 if index < pulse else 0] + [0] * 11
            if frame["frame"] != report["reference_frame"] + index or frame["inputs"] != masks:
                raise ValueError("Nonconsecutive frame or unexpected controller input")
        state = probe_kernel.read_bounded(directory / "final.state", state_graphics.MAX_STATE)
        if sha(state) != report["final_state_sha256"]:
            raise ValueError("Final private state artefact differs")
        elapsed = report["emulation_wall_seconds"]
        if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed <= 0:
            raise ValueError("Missing real bounded timing observation")
        if report["mode"] == "enabled":
            raw = probe_kernel.read_bounded(directory / "context-trace.json", 2 * 1024**2)
            trace = decoded_trace(read_json(directory / "context-trace.json"))
            if (sha(raw) != report["trace_sha256"] or trace["completed_cycles"] != report["pairs"] or
                    trace["profile"] != report["context_profile"]):
                raise ValueError("Original context trace differs from its report")
        runs.append(report)
    groups = {mode: [run for run in runs if run["mode"] == mode]
              for mode in ("reference", "disabled", "enabled")}
    if any(len(group) != 2 for group in groups.values()):
        raise ValueError("Require exactly two runs per declared mode")
    baseline = groups["reference"][0]
    equal = ("driver_sha256", "source_modules", "reference_identity", "reference_lock_file_sha256",
             "reference_checkpoint_file_sha256", "reference_state_sha256", "reference_frame", "frames", "port_zero_start_frames", "context_profile",
             "original_kernel_sha256", "completed_original_frames", "original_game_bytes_executed",
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
        raise ValueError("Real original context traces are not repeatable")
    medians = {mode: statistics.median(run["emulation_wall_seconds"] for run in group)
               for mode, group in groups.items()}
    return {"schema": "neptune.context-observer-comparison.v1", "status": "success", "context_profile": baseline["context_profile"],
            "runs": 6, "repeats_per_mode": 2, "frames_per_run": baseline["frames"],
            "reference_core_sha256": REFERENCE_CORE, "instrumented_core_sha256": patched[0]["selected_core_sha256"],
            "equal_observations": list(equal), "pairs_per_enabled_run": groups["enabled"][0]["pairs"],
            "trace_sha256": groups["enabled"][0]["trace_sha256"],
            "median_emulation_wall_seconds": medians,
            "enabled_vs_disabled_wall_ratio": medians["enabled"] / medians["disabled"],
            "disabled_vs_reference_wall_ratio": medians["disabled"] / medians["reference"],
            "timing_scope": "whole bounded run; recorder stops at its declared cycle limit; not hardware cycles or steady-state full tracing",
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
    parser.add_argument("--pairs", type=int, default=1)
    parser.add_argument("--profile", type=int, choices=(1, 2, 3), required=True)
    parser.add_argument("--start-frames", type=int, default=0,
                        help="Press port-zero Start for this many initial frames, then release; no other inputs")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = run(args)
    print(json.dumps({key: result[key] for key in ("status", "mode", "frames", "selected_core_sha256")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
