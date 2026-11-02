"""Real production-client downloads, immutable cache reuse and pre-admission readiness.

Called by check_runtime.py; all content is an original fixture copied into a
separate authority profile. This does not test browser transport or avatar sharing.
"""
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import time

from run_bot_tests import ANSI, ERROR, ROOT


def _json_bytes(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def _profile(base_env, root):
    env = dict(base_env)
    for key, name in (("XDG_CONFIG_HOME", "config"), ("XDG_DATA_HOME", "data"), ("XDG_CACHE_HOME", "cache")):
        location = root / name
        location.mkdir(parents=True)
        env[key] = str(location)
    return env


def _fixture(root, variant, dependency=None):
    source = ROOT / "maps" / ("neptune_wide.json" if variant == "beta" else "neptune_standard.json")
    arena = json.loads(source.read_bytes())
    arena["name"] = "Original clean-client sharing " + variant
    raw_arena = _json_bytes(arena)
    # A valid, deliberately uncompressed arena spans multiple bounded chunks so
    # cancellation is exercised before even the first archive can activate.
    if variant == "alpha":
        raw_arena += b" " * (40000 - len(raw_arena))
    pack_id = "probe." + variant + ":pack"
    content_id = "probe." + variant + ":arena"
    manifest = {"schema": "neptune.pack.v1", "pack_id": pack_id, "version": "1.0.0",
                "author": "Neptune original test fixture", "license": "Apache-2.0",
                "dependencies": [dependency["identity"]] if dependency else [],
                "content": [{"id": content_id, "kind": "arena", "path": "arena.json",
                             "sha256": hashlib.sha256(raw_arena).hexdigest()}]}
    raw_manifest = _json_bytes(manifest)
    folder = root / "sharing-fixtures" / variant
    folder.mkdir(parents=True)
    (folder / "manifest.json").write_bytes(raw_manifest)
    (folder / "arena.json").write_bytes(raw_arena)
    identity = {"pack_id": pack_id, "version": "1.0.0", "manifest_sha256": hashlib.sha256(raw_manifest).hexdigest()}
    return {"identity": identity, "path": "user://sharing-fixtures/" + variant + "/manifest.json",
            "content": {**identity, "content_id": content_id, "kind": "arena", "sha256": manifest["content"][0]["sha256"]},
            "width": len(arena["grid"][0]), "height": len(arena["grid"]),
            "map_sha256": hashlib.sha256(bytes(cell for row in arena["grid"] for cell in row)).hexdigest()}


def _expected(chosen, shared):
    identities = sorted([chosen["identity"], shared["identity"]], key=lambda value: value["pack_id"])
    lock = {"schema": "neptune.manifest-lock.v1", "roots": identities, "packs": identities}
    return {"lock": lock, "lock_sha256": hashlib.sha256(_json_bytes(lock)).hexdigest(),
            **{key: chosen[key] for key in ("content", "width", "height", "map_sha256")}}


def run_content_sharing_checks(base, base_env, evidence, bounded):
    profiles = Path(tempfile.mkdtemp(prefix="sharing-profiles-", dir=evidence))
    server_env = _profile(base_env, profiles / "authority")
    client_env = _profile(base_env, profiles / "client")
    interrupted_env = _profile(base_env, profiles / "interrupted-client")
    code, text = bounded("sharing-user-directory", base + ["res://tools/godot/runtime_probe.tscn", "--",
                         "--runtime-role=test", "--probe-user-data-dir"], process_env=server_env)
    markers = [line.split("=", 1)[1] for line in text.splitlines() if line.startswith("NEPTUNE_USER_DATA_DIR=")]
    if code or ERROR.search(text) or len(markers) != 1:
        raise SystemExit("FAIL: cannot establish isolated authority user directory")
    user_dir = Path(markers[0])
    if not user_dir.resolve().is_relative_to(Path(server_env["XDG_DATA_HOME"]).resolve()):
        raise SystemExit("FAIL: authority user directory escaped its isolated XDG profile")
    shared = _fixture(user_dir, "shared")
    alpha = _fixture(user_dir, "alpha", shared)
    beta = _fixture(user_dir, "beta", shared)
    outcomes = []
    cases = [("wrong-ready", alpha, interrupted_env, "wrong-ready", 0),
             ("cancel", alpha, interrupted_env, "cancel", 0),
             ("resume", alpha, interrupted_env, "play", 0),
             ("cold-alpha", alpha, client_env, "play", 0),
             ("warm-alpha", alpha, client_env, "play", 2),
             ("cold-beta", beta, client_env, "play", 1),
             ("return-alpha", alpha, client_env, "play", 2)]
    for case, chosen, client_profile, mode, hits in cases:
        expected = _expected(chosen, shared)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        server_command = base + ["res://main_server.tscn", "--", "--server-port=" + str(port),
                                 "--room-seats=2", "--room-preset-limit=2", "--room-fill-to=2",
                                 "--room-pack=" + chosen["path"], "--room-pack=" + shared["path"],
                                 "--room-arena=" + chosen["content"]["content_id"]]
        server_log = evidence / ("sharing-" + case + "-server.log")
        with server_log.open("w") as output:
            server = subprocess.Popen(server_command, env=server_env, stdout=output, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    text = ANSI.sub("", server_log.read_text())
                    if server.poll() is not None or ERROR.search(text):
                        raise SystemExit("FAIL: sharing authority startup; inspect " + str(server_log))
                    if "Server listening on port " + str(port) in text:
                        break
                    time.sleep(0.05)
                else:
                    raise SystemExit("FAIL: sharing authority startup timeout")
                command = base + ["res://tools/godot/runtime_probe.tscn", "--", "--runtime-role=client",
                                  "--server-port=" + str(port), "--probe-content", "--probe-content-case=" + case,
                                  "--probe-content-mode=" + mode, "--probe-content-expected=" + _json_bytes(expected).decode()]
                code, text = bounded("sharing-" + case + "-client", command, process_env=client_profile)
                markers = [line.split("=", 1)[1] for line in text.splitlines() if line.startswith("NEPTUNE_CONTENT_SHARING=")]
                if code or ERROR.search(text) or len(markers) != 1:
                    raise SystemExit("FAIL: actual ClientMain sharing " + case + "; inspect client/server evidence")
                receipt = json.loads(markers[0])
                should_play = mode == "play"
                if (receipt.get("case") != case or receipt.get("lock_sha256") != expected["lock_sha256"]
                        or any(receipt.get(key) is not should_play for key in ("ready", "authenticated", "map", "snapshot"))
                        or receipt.get("cancelled") is not (mode == "cancel")
                        or receipt.get("refused") is not (mode == "wrong-ready")):
                    raise SystemExit("FAIL: sharing readiness/admission receipt " + case)
                if should_play:
                    hashes = {identity["pack_id"]: identity["manifest_sha256"] for identity in expected["lock"]["packs"]}
                    if (receipt.get("cache_hits") != hits or receipt.get("pack_count") != 2
                            or receipt.get("manifest_hashes") != hashes or receipt.get("map_sha256") != expected["map_sha256"]
                            or receipt.get("total_bytes", 0) <= 0 or receipt.get("received_bytes", -1) < 0
                            or (receipt["received_bytes"] == 0) != (hits == 2)
                            or (hits == 0 and receipt["received_bytes"] != receipt["total_bytes"])):
                        raise SystemExit("FAIL: verified immutable cache/byte oracle " + case)
                elif mode == "cancel" and not 0 < receipt.get("received_bytes", 0) <= 16384:
                    raise SystemExit("FAIL: interruption did not occur within the first uninstalled archive chunk")
                elif mode == "wrong-ready" and (receipt.get("received_bytes") != 0 or receipt.get("reason") != "content_lock_mismatch"):
                    raise SystemExit("FAIL: wrong-lock readiness was not refused before transfer/admission")
                text = ANSI.sub("", server_log.read_text())
                if ERROR.search(text) or text.count("[Server] Peer connected:") != 1:
                    raise SystemExit("FAIL: sharing authority transport evidence " + case)
                if should_play:
                    if text.count("joined shared game.") != 1 or text.count("Match started! Countdown complete.") != 1:
                        raise SystemExit("FAIL: ready client did not reach one actual authority round " + case)
                elif "joined shared game." in text or "Match started!" in text:
                    raise SystemExit("FAIL: cancelled download reached authority admission/countdown")
                outcomes.append(receipt)
                print("PASS: actual ClientMain content sharing:", json.dumps(receipt, sort_keys=True))
            finally:
                server.terminate()
                try:
                    server.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=3)
    (evidence / "content-sharing-summary.json").write_text(json.dumps(outcomes, indent=2) + "\n")
