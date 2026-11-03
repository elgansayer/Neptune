"""Real local server/auth/admission/snapshot capacity checks; not browser/load testing."""
import hashlib
import json
import socket
import subprocess
import time

from run_bot_tests import ANSI, ERROR, ROOT


def run_capacity_checks(base, env, evidence, bounded):
    for name, humans, bots, preset, auto_fill in [("twelve", 12, 0, 12, False),
                                       ("mixed", 6, 6, 12, False),
                                       ("preset-four", 4, 0, 4, False),
                                       ("default-fill-four", 1, 3, 4, True),
                                       ("default-fill-two", 1, 1, 2, True),
                                       ("explicit-no-fill", 2, 0, 2, False),
                                       ("auto-fill-four", 1, 3, 4, True),
                                       ("auto-fill-twelve", 2, 10, 12, True),
                                       ("standard-arena", 2, 2, 4, True),
                                       ("wide-arena", 2, 2, 4, True),
                                       ("registered-standard", 2, 2, 4, True),
                                       ("registered-wide", 2, 2, 4, True),
                                       ("registered-linked", 2, 2, 4, True)]:
        map_name, width, height = {"standard-arena": ("neptune_standard", 15, 13),
                                   "wide-arena": ("neptune_wide", 27, 13),
                                   "registered-standard": ("neptune_standard", 15, 13),
                                   "registered-wide": ("neptune_wide", 27, 13)}.get(name, ("neptune_twelve", 17, 13))
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as port_reservation:
            port_reservation.bind(("127.0.0.1", 0))
            port = port_reservation.getsockname()[1]
        seats = humans + bots
        options = ["--server-port=" + str(port), "--room-seats=" + str(seats),
                   "--room-preset-limit=" + str(preset)]
        expected_content = {}
        expected_lock = {}
        expected_lock_sha256 = ""
        if name.startswith("registered-"):
            variant = name.removeprefix("registered-")
            manifest_path = ROOT / "demo/packs" / variant / "manifest.json"
            manifest_bytes = manifest_path.read_bytes()
            manifest = json.loads(manifest_bytes)
            entry = manifest["content"][0]
            expected_content = {"pack_id": manifest["pack_id"], "version": manifest["version"],
                                "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                                "content_id": entry["id"], "kind": "arena", "sha256": entry["sha256"]}
            arena = json.loads((manifest_path.parent / entry["path"]).read_bytes())
            width, height = len(arena["grid"][0]), len(arena["grid"])
            # The dependent root deliberately precedes both dependencies. Every
            # supplied manifest remains an explicit root, regardless of ordering.
            variants = ["linked", "wide", "standard"] if variant == "linked" else ["standard", "wide"]
            identities = []
            for included in variants:
                contents = (ROOT / "demo/packs" / included / "manifest.json").read_bytes()
                metadata = json.loads(contents)
                identities.append({"pack_id": metadata["pack_id"], "version": metadata["version"],
                                   "manifest_sha256": hashlib.sha256(contents).hexdigest()})
                options.append("--room-pack=res://demo/packs/" + included + "/manifest.json")
            identities.sort(key=lambda identity: identity["pack_id"])
            expected_lock = {"schema": "neptune.manifest-lock.v1", "roots": identities, "packs": identities}
            lock_json = json.dumps(expected_lock, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
            expected_lock_sha256 = hashlib.sha256(lock_json.encode()).hexdigest()
            options.append("--room-arena=" + entry["id"])
        else:
            options.append("--room-map=res://maps/" + map_name + ".json")
        default_fill = name.startswith("default-fill-")
        personality = "BALANCED" if default_fill else "DEFENSIVE"
        if auto_fill and not default_fill:
            options += ["--room-fill-to=" + str(seats), "--room-bot-personality=DEFENSIVE"]
        elif not auto_fill:
            options.append("--room-fill-to=0")
        command = base + ["res://main_server.tscn", "--", *options]
        server_log = evidence / ("room-" + name + "-server.log")
        with server_log.open("w") as output:
            server = subprocess.Popen(command, env=env, stdout=output, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    text = ANSI.sub("", server_log.read_text())
                    if server.poll() is not None or ERROR.search(text):
                        raise SystemExit("FAIL: room server startup; inspect " + str(server_log))
                    if "Server listening on port " + str(port) in text:
                        break
                    time.sleep(0.05)
                else:
                    raise SystemExit("FAIL: room server startup timeout")
                command = base + ["res://tools/godot/room_capacity_probe.tscn", "--",
                                  "--runtime-role=test", "--server-port=" + str(port),
                                  "--probe-humans=" + str(humans), "--probe-bots=" + str(bots),
                                  "--probe-preset=" + str(preset),
                                  "--probe-map-width=" + str(width), "--probe-map-height=" + str(height)]
                if auto_fill:
                    command += ["--probe-auto-fill", "--probe-personality=" + personality]
                if expected_content:
                    command.append("--probe-content-json=" + json.dumps(expected_content, separators=(",", ":")))
                    command.append("--probe-lock-json=" + lock_json)
                    command.append("--probe-lock-sha256=" + expected_lock_sha256)
                    command.append("--probe-selection-count=" + str(len(identities)))
                code, text = bounded("room-" + name + "-clients", command)
                markers = [line.split("=", 1)[1] for line in text.splitlines()
                           if line.startswith("NEPTUNE_ROOM_CAPACITY=")]
                expected = {"seats": seats, "humans": humans, "bots": bots,
                            "preset_limit": preset, "protocol_limit": 12,
                            "accepted": humans, "refused": 0 if bots else 1,
                            "spectators": 1 if bots else 0, "snapshots": humans, "maps": humans, "active": True}
                if auto_fill: expected["auto_fill"] = True
                if expected_content:
                    expected.update(content=expected_content, selection=identities,
                                    lock=expected_lock, lock_sha256=expected_lock_sha256)
                receipt = json.loads(markers[0]) if len(markers) == 1 else {}
                policy = receipt.pop("bot_policy", "")
                seed = receipt.pop("bot_policy_seed", "")
                if (code or ERROR.search(text) or len(markers) != 1 or receipt != expected
                        or policy != "neptune-heuristic-v3" or not isinstance(seed, str)
                        or not seed.lstrip("-").isdigit()):
                    raise SystemExit("FAIL: real room " + name + "; inspect client/server evidence")
                text = ANSI.sub("", server_log.read_text())
                if (ERROR.search(text) or text.count("[Server] Peer connected:") != humans + 1
                        or text.count("[Server] Player admission refused: room_full") != (0 if bots else 1)
                        or text.count("Match started! Countdown complete.") != 1):
                    raise SystemExit("FAIL: server capacity/admission evidence for " + name)
                if auto_fill and "requested bot (" in text:
                    raise SystemExit("FAIL: automatic fill depended on client spawn-bot RPCs")
                print("PASS: actual room auth/maps/snapshots/refusal:", json.dumps(expected, sort_keys=True))
            finally:
                server.terminate()
                try:
                    server.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=3)

    # Valid map with four declared starts, explicitly requested twelve seats:
    # fail before listening/starting, with no fallback to a smaller room.
    command = base + ["res://main_server.tscn", "--", "--room-seats=12",
                      "--room-map=res://maps/classic_arena.json"]
    code, text = bounded("room-unsupported-map", command)
    if (code != 2 or "Room setup refused: insufficient_spawn_capacity" not in text
            or "Server listening" in text or "Match started!" in text or ERROR.search(text)):
        raise SystemExit("FAIL: unsupported map/seat combination did not refuse before start")
    for name, options in [("over-protocol", ["--room-seats=13"]),
                          ("over-preset", ["--room-seats=5", "--room-preset-limit=4"]),
                          ("duplicate", ["--room-seats=4", "--room-seats=4"]),
                          ("zero", ["--room-seats=0"])]:
        code, text = bounded("room-invalid-" + name, base + ["res://main_server.tscn", "--", *options])
        if code != 2 or "Server listening" in text:
            raise SystemExit("FAIL: invalid room options accepted: " + name)
    print("PASS: unsupported room map and invalid capacity options refuse before listening")
    for arena, reason in [("example.standard:missing", "unknown_content"),
                          ("example.missing:arena", "unknown_content")]:
        code, text = bounded("pack-invalid-" + arena.replace(":", "-"), base + [
            "res://main_server.tscn", "--", "--room-pack=res://demo/packs/standard/manifest.json",
            "--room-arena=" + arena])
        if (code != 2 or "Room setup refused: " + reason not in text or "Content diagnostic:" not in text
                or "Server listening" in text or "Match started!" in text or ERROR.search(text)):
            raise SystemExit("FAIL: explicit unknown arena did not refuse before listening")
    for name, options, reason in [
            ("over-room", ["--room-seats=4", "--room-fill-to=5"], "bot_fill_capacity_exceeded"),
            ("unknown-profile", ["--room-bot-personality=UNKNOWN"], "unknown_bot_personality")]:
        code, text = bounded("fill-invalid-" + name, base + ["res://main_server.tscn", "--", *options])
        if code != 2 or "Room setup refused: " + reason not in text or "Server listening" in text or ERROR.search(text):
            raise SystemExit("FAIL: invalid fill setup did not refuse before listening: " + name)
    for name, options in [("negative", ["--room-fill-to=-1"]),
                          ("over-protocol", ["--room-fill-to=13"]),
                          ("duplicate", ["--room-fill-to=4", "--room-fill-to=4"]),
                          ("missing", ["--room-fill-to"])]:
        code, text = bounded("fill-invalid-" + name, base + ["res://main_server.tscn", "--", *options])
        if code != 2 or "Server listening" in text:
            raise SystemExit("FAIL: invalid fill option accepted: " + name)
    print("PASS: invalid fill targets/profiles refuse before listening")
