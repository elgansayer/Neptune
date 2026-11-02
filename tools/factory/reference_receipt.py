#!/usr/bin/env python3
"""Coordinator-only pinned reference recorder; public Ed25519 receipt verification.

Run trusted source, never worker/issue commands. Keys stay outside capture mounts.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "neptune.reference-experiment.v1"
SCOPE = "Coordinator-attested original observation repeatability only; no Godot, extraction, hardware or whole-game parity claim."
MAX_JSON = 1024 * 1024
MAX_OUTPUT = 64 * 1024**2
SPKI = bytes.fromhex("302a300506032b6570032100")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def safe(path):
    path = Path(path).absolute()
    require(not any(p.is_symlink() for p in (path, *path.parents)), "Symlinked authority/evidence paths are forbidden")
    return path


def read_json(path):
    path = safe(path)
    require(path.is_file() and path.stat().st_size <= MAX_JSON, "Missing or oversized receipt/policy/result")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "Duplicate JSON key")
            result[key] = value
        return result
    return json.loads(path.read_bytes(), object_pairs_hook=unique)


def write_json(path, value):
    with safe(path).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def openssl(*arguments):
    binary = shutil.which("openssl", path=os.defpath)
    require(binary is not None, "Missing OpenSSL Ed25519 capability; prepare it before recording")
    result = subprocess.run([binary, *map(str, arguments)], stdin=subprocess.DEVNULL,
                            capture_output=True, timeout=15,
                            env={"PATH": os.defpath, "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"})
    require(result.returncode == 0, "OpenSSL operation failed; no trusted receipt")
    require(len(result.stdout) <= 4096 and len(result.stderr) <= 4096, "Oversized crypto-tool output")
    return result.stdout


def public_bytes(path):
    path = safe(path)
    require(path.is_file() and path.stat().st_size == 44, "Require a raw Ed25519 SPKI public key")
    value = path.read_bytes()
    require(value.startswith(SPKI), "Only Ed25519 authority keys are accepted")
    return value


def private_key(path):
    path = safe(path)
    require(path.is_file() and 0 < path.stat().st_size <= 4096, "Missing private authority key")
    require(path.stat().st_uid == os.geteuid() and path.stat().st_mode & 0o777 == 0o600,
            "Authority key must be owned by the coordinator with mode0600")
    require(path.parent.stat().st_uid == os.geteuid() and path.parent.stat().st_mode & 0o777 == 0o700,
            "Authority directory must be owned by the coordinator with mode0700")
    return path


def keygen(directory):
    directory = safe(directory)
    require(not directory.exists(), "Preserve existing authorities; use a fresh directory")
    directory.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix=".authority-", dir=directory.parent) as stage:
        stage = Path(stage)
        key = stage / "private.pem"
        key.touch(mode=0o600)
        openssl("genpkey", "-algorithm", "ED25519", "-out", key)
        pub = openssl("pkey", "-in", key, "-pubout", "-outform", "DER")
        (stage / "public.der").write_bytes(pub)
        public_bytes(stage / "public.der")
        # Publish both files together; no overwrite of another key generation.
        stage.rename(directory)
    return {"public_key_sha256": digest(directory / "public.der")}


def seal(payload, key, public, output):
    """Internal primitive. Possession of a key is authority, not capture evidence."""
    key = private_key(key)
    public = safe(public)
    require(openssl("pkey", "-in", key, "-pubout", "-outform", "DER") == public_bytes(public),
            "Private/public authority mismatch")
    with tempfile.TemporaryDirectory(prefix="reference-sign-") as temp:
        message, signature = Path(temp) / "message", Path(temp) / "signature"
        message.write_bytes(canonical(payload))
        openssl("pkeyutl", "-sign", "-rawin", "-inkey", key, "-in", message, "-out", signature)
        raw = signature.read_bytes()
        require(len(raw) == 64, "Invalid Ed25519 signature output")
    envelope = {"payload": payload, "public_key_sha256": digest(public),
                "signature": base64.b64encode(raw).decode("ascii")}
    write_json(output, envelope)
    return envelope


def inventory(root):
    records, total = {}, 0
    for path in sorted(root.rglob("*")):
        safe(path)
        certificate = path == root / "reference-certificate.json"
        if path.is_file() and not certificate:
            total += path.stat().st_size
            require(total <= MAX_OUTPUT and len(records) < 128, "Reference output budget exceeded")
            records[path.relative_to(root).as_posix()] = {"bytes": path.stat().st_size, "sha256": digest(path)}
        else:
            require(path.is_dir() or (certificate and path.is_file()), "Unexpected output file type")
    return records


def verify(certificate, public, expected_key_sha256, binding, policy_sha256, artifacts):
    """The expected key, task and policy must come from trusted coordinator state."""
    public = safe(public)
    require(digest(public) == expected_key_sha256, "Untrusted authority public key")
    public_bytes(public)
    envelope = read_json(certificate)
    require(isinstance(envelope, dict) and set(envelope) == {"payload", "signature", "public_key_sha256"},
            "Malformed reference certificate")
    require(envelope["public_key_sha256"] == expected_key_sha256, "Certificate authority differs from trusted key")
    raw = base64.b64decode(envelope["signature"], validate=True)
    require(len(raw) == 64, "Missing/truncated signature")
    with tempfile.TemporaryDirectory(prefix="reference-verify-") as temp:
        message, signature = Path(temp) / "message", Path(temp) / "signature"
        message.write_bytes(canonical(envelope["payload"]))
        signature.write_bytes(raw)
        openssl("pkeyutl", "-verify", "-rawin", "-pubin", "-keyform", "DER", "-inkey", public,
                "-in", message, "-sigfile", signature)
    payload = envelope["payload"]
    require(isinstance(payload, dict) and set(payload) == {"schema", "scope", "task_binding", "policy_sha256",
            "owner", "scenario", "identity", "isolation", "runs", "comparisons", "files", "crypto", "recorded_at"},
            "Malformed signed experiment payload")
    require(payload["schema"] == SCHEMA and payload["scope"] == SCOPE, "Unsupported experiment scope")
    require(canonical(payload["task_binding"]) == canonical(binding) and payload["policy_sha256"] == policy_sha256,
            "Stale/foreign task or reference policy")
    require(isinstance(payload["isolation"], dict) and set(payload["isolation"]) ==
            {"source_read_only", "authority_hidden", "broker_hidden"} and
            all(value is True for value in payload["isolation"].values()),
            "Missing actual isolation proof")
    require(type(payload["recorded_at"]) in (int, float) and math.isfinite(payload["recorded_at"]) and
            0 < payload["recorded_at"] <= time.time() + 5, "Invalid signed experiment time")
    require(isinstance(payload["runs"], list) and len(payload["runs"]) == 3 and
            isinstance(payload["comparisons"], list) and len(payload["comparisons"]) == 2,
            "Missing repeated experiment evidence")
    for run in payload["runs"]:
        require(run["exit"] == 0 and type(run["exit"]) is int and type(run["frames"]) is int and 1 <= run["frames"] <= 600 and
                run["frames"] == payload["runs"][0]["frames"] and
                isinstance(run["canonical_digest"], str) and re.fullmatch(r"[0-9a-f]{64}", run["canonical_digest"]) and
                run["identity"] == payload["identity"], "Failed/skipped/incompatible run")
    require(len({r["canonical_digest"] for r in payload["runs"]}) == 1, "Repeated observations diverge")
    require(all(c["command"] == "compare" and type(c["matched_frames"]) is int and
                c["matched_frames"] == payload["runs"][0]["frames"] and
                c["canonical_digest"] == payload["runs"][0]["canonical_digest"] for c in payload["comparisons"]),
            "Incomplete repeated comparisons")
    require(payload["files"] == inventory(safe(artifacts)), "Missing, replaced, truncated or unexpected retained evidence")
    return {"authenticated": True, "scope": SCOPE, "certificate_sha256": digest(certificate),
            "public_key_sha256": expected_key_sha256, "task_binding": binding}


def tree_identity(root):
    return hashlib.sha256(canonical({p.relative_to(root).as_posix(): digest(p)
                                   for p in sorted(root.rglob("*.py"))})).hexdigest()


def load_policy(path):
    policy = read_json(path)
    required = {"root", "lock", "lock_sha256", "identity", "restore", "restore_sha256", "actions",
                "actions_sha256", "frames", "owner", "scenario", "python", "python_sha256",
                "factory_tree_sha256", "host_gate"}
    require(isinstance(policy, dict) and set(policy) == required, "Malformed trusted capture policy")
    require(type(policy["frames"]) is int and 1 <= policy["frames"] <= 600, "Bound experiments to1..600frames")
    for key in ("owner", "scenario"):
        require(isinstance(policy[key], str) and 0 < len(policy[key]) <= 200, "Missing bounded experiment owner/scenario")
    for key in ("lock_sha256", "restore_sha256", "actions_sha256", "python_sha256", "factory_tree_sha256"):
        require(isinstance(policy[key], str) and re.fullmatch(r"[0-9a-f]{64}", policy[key]), "Missing pinned policy identity")
    require(isinstance(policy["identity"], dict) and set(policy["identity"]) ==
            {"core_sha256", "frontend_sha256", "lock_sha256", "python_sha256", "settings_sha256"} and
            all(isinstance(v, str) and re.fullmatch(r"[0-9a-f]{64}", v) for v in policy["identity"].values()),
            "Incomplete expected reference component identity")
    return policy


def capture(policy_path, intake, source, authority, output):
    """Only this fixed recorder is a supported signing entrypoint, not seal(JSON)."""
    sys.path.insert(0, str(ROOT / "tools/factory"))
    from verify import task_binding
    policy_path, source, authority, output = map(safe, (policy_path, source, authority, output))
    policy = load_policy(policy_path)
    policy_sha = digest(policy_path)
    require(not output.exists(), "Use a fresh private experiment directory")
    require(not authority.is_relative_to(output) and not output.is_relative_to(authority), "Keep authority separate from captures")
    key = private_key(authority / "private.pem")
    public_bytes(authority / "public.der")
    # The existing binding enforces clean complete Git source, current task and scope.
    import verify as factory_verify
    snapshot, _ = factory_verify.read_intake(intake)
    base, head = snapshot["base_sha"], factory_verify.gate.git("rev-parse", "HEAD", root=source)
    changed = subprocess.check_output(["git", "diff", "--no-renames", "--name-only", "-z", base, head], cwd=source, text=True)
    paths = sorted(p for p in changed.split("\0") if p)
    binding = task_binding(intake, paths, source)
    root = safe(policy["root"])
    require(not output.is_relative_to(root), "Never write captures into original media")
    spec = importlib.util.spec_from_file_location("reference_input_validation", ROOT / "tools/saturn_lab/cli.py")
    inputs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(inputs)
    lock_path = inputs.confined_file(root, policy["lock"])
    require(digest(lock_path) == policy["lock_sha256"], "Reference lock differs from trusted policy")
    lock = read_json(lock_path)
    inputs.verify_lock(root, lock)
    profile = read_json(inputs.confined_file(root, lock["inputs"]["settings"]))
    entry = inputs.confined_file(root, profile["frontend_path"])
    require(digest(entry) == policy["identity"]["frontend_sha256"], "Reference entrypoint differs")
    python = Path(policy["python"]).resolve()
    require(digest(python) == policy["python_sha256"] == policy["identity"]["python_sha256"], "Pinned interpreter differs")
    restore, actions = safe(policy["restore"]), safe(policy["actions"])
    require(digest(restore) == policy["restore_sha256"] and digest(actions) == policy["actions_sha256"], "Checkpoint/input record differs")
    checkpoint = read_json(restore)
    require(checkpoint["identity"] == policy["identity"], "Foreign checkpoint identity")
    state = inputs.confined_file(restore.parent, checkpoint["state_path"])
    require(state.stat().st_size == checkpoint["state_bytes"] and digest(state) == checkpoint["state_sha256"], "Checkpoint state differs")
    from openhands_factory.agents.process import AgentProcessRunner, ProviderHomeMount
    from openhands_factory.host_resource_gate import HostResourceGate
    import openhands_factory
    factory = Path(openhands_factory.__file__).parent
    require(tree_identity(factory) == policy["factory_tree_sha256"], "Trusted installed factory runtime differs")
    home = Path.home().resolve()
    # Reuse the existing namespace and exclusive host gate, no new scheduler/store.
    mounts = []
    for parent in {restore.parent, actions.parent}:
        require(parent.is_relative_to(home) and not authority.is_relative_to(parent), "Unsafe private capture mount")
        mounts.append(ProviderHomeMount(parent.relative_to(home).as_posix(), read_only=True))
    require(authority.is_relative_to(home) and not authority.is_relative_to(root), "Authority must be hidden by the home mask")
    output.mkdir(parents=True, mode=0o700)
    environment = {"PATH": os.defpath, "HOME": str(home), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
    runner = AgentProcessRunner(isolate_processes=True, guard_timeout_seconds=5)
    report = {"schema": SCHEMA, "scope": SCOPE, "task_binding": binding, "policy_sha256": policy_sha,
              "owner": policy["owner"], "scenario": policy["scenario"], "identity": policy["identity"],
              "isolation": {}, "runs": [], "comparisons": [], "files": {}, "recorded_at": time.time(),
              "crypto": {"binary_sha256": digest(Path(shutil.which("openssl", path=os.defpath)).resolve()),
                         "version": openssl("version").decode().strip()}}
    def execute(command, name, timeout):
        result = runner.run(command, cwd=output, env=environment, stdin_text=None,
                            timeout_seconds=timeout, max_output_bytes=2 * 1024**2, home_mounts=mounts)
        (output / (name + ".stdout")).write_text(result.stdout)
        (output / (name + ".stderr")).write_text(result.stderr)
        require(result.exit_code == 0 and not result.timed_out and not result.output_truncated and not result.cancelled,
                "Bounded isolated experiment failed: " + name)
        return result
    old = {key: os.environ.get(key) for key in ("FACTORY_REPOSITORY", "FACTORY_STATE_DIR", "FACTORY_LOG_DIR")}
    os.environ.update(FACTORY_REPOSITORY=str(root), FACTORY_STATE_DIR="/var/lib", FACTORY_LOG_DIR="/var/log")
    try:
        with HostResourceGate(safe(policy["host_gate"]), 1, lease_seconds=600).exclusive():
            probe = ("import json,os,pathlib; assert os.statvfs(" + repr(str(root)) + ").f_flag & os.ST_RDONLY; "
                     "assert not pathlib.Path(" + repr(str(key)) + ").exists(); "
                     "assert not pathlib.Path('/var/lib/repo-factory').exists(); "
                     "print(json.dumps({'source_read_only':True,'authority_hidden':True,'broker_hidden':True}))")
            result = execute([str(python), "-I", "-c", probe], "isolation", 20)
            report["isolation"] = json.loads(result.stdout)
            for index in range(3):
                destination = output / ("run-" + str(index))
                destination.mkdir()
                command = [str(python), str(entry), "_worker", "run", "--root", str(root), "--lock", str(lock_path),
                           "--restore", str(restore), "--actions", str(actions), "--frames", str(policy["frames"]),
                           "--capture", "0", "--timeout", "60", "--output", str(destination)]
                result = execute(command, "run-" + str(index), 90)
                markers = [line.split("=", 1)[1] for line in result.stdout.splitlines() if line.startswith("NEPTUNE_LIBRETRO_RESULT=")]
                observed = read_json(destination / "result.json")
                require(len(markers) == 1 and json.loads(markers[0]) == observed, "Missing/mismatching actual worker result")
                frames = read_json(destination / "observations.json")
                require(observed["frames"] == policy["frames"] and len(frames["frames"]) == policy["frames"] and
                        observed["identity"] == frames["identity"] == policy["identity"], "Incomplete or foreign actual capture")
                report["runs"].append({"exit": result.exit_code, "frames": observed["frames"], "identity": observed["identity"],
                                       "command": command, "canonical_digest": observed["canonical_digest"]})
                inventory(output)
            for index in (1, 2):
                destination = output / ("comparison-" + str(index))
                destination.mkdir()
                execute([str(python), str(entry), "_worker", "compare", "--root", str(root), "--output", str(destination),
                         "--reference", str(output / "run-0/observations.json"),
                         "--candidate", str(output / ("run-" + str(index)) / "observations.json")], "comparison-" + str(index), 20)
                compared = read_json(destination / "result.json")
                require(compared["matched_frames"] == policy["frames"], "Incomplete actual repeatability comparison")
                report["comparisons"].append(compared)
    finally:
        for name, value in old.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
    require(task_binding(intake, paths, source) == binding and digest(policy_path) == policy_sha,
            "Task/source/policy changed during capture")
    require(tree_identity(factory) == policy["factory_tree_sha256"], "Factory runtime changed during capture")
    inputs.verify_lock(root, lock)
    require(digest(restore) == policy["restore_sha256"] and digest(actions) == policy["actions_sha256"] and
            digest(state) == checkpoint["state_sha256"], "Checkpoint/input changed during capture")
    report["files"] = inventory(output)
    seal(report, key, authority / "public.der", output / "reference-certificate.json")
    return verify(output / "reference-certificate.json", authority / "public.der", digest(authority / "public.der"),
                  binding, policy_sha, output)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    generate = sub.add_parser("keygen")
    generate.add_argument("--authority", type=Path, required=True)
    record = sub.add_parser("capture")
    for name in ("policy", "intake", "source", "authority", "output"):
        record.add_argument("--" + name, type=Path, required=True)
    check = sub.add_parser("verify")
    for name in ("certificate", "public-key", "binding", "artifacts"):
        check.add_argument("--" + name, type=Path, required=True)
    for name in ("key-sha256", "policy-sha256"):
        check.add_argument("--" + name, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "keygen":
            result = keygen(args.authority)
        elif args.command == "capture":
            signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("Total capture deadline exceeded")))
            signal.alarm(480)
            try:
                result = capture(args.policy, args.intake, args.source, args.authority, args.output)
            finally:
                signal.alarm(0)
        else:
            result = verify(args.certificate, args.public_key, args.key_sha256, read_json(args.binding),
                            args.policy_sha256, args.artifacts)
        print("NEPTUNE_REFERENCE_RECEIPT=" + json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, OSError, KeyError, TypeError, ImportError, RecursionError, subprocess.SubprocessError) as error:
        print("FAIL: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
