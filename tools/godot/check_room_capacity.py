"""Real local server/auth/admission/snapshot capacity checks; not browser/load testing."""
import json
import socket
import subprocess
import time

from run_bot_tests import ANSI, ERROR


def run_capacity_checks(base, env, evidence, bounded):
    for name, humans, bots, preset in [("twelve", 12, 0, 12),
                                       ("mixed", 6, 6, 12),
                                       ("preset-four", 4, 0, 4)]:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as port_reservation:
            port_reservation.bind(("127.0.0.1", 0))
            port = port_reservation.getsockname()[1]
        seats = humans + bots
        options = ["--server-port=" + str(port), "--room-seats=" + str(seats),
                   "--room-preset-limit=" + str(preset),
                   "--room-map=res://maps/neptune_twelve.json"]
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
                                  "--probe-preset=" + str(preset)]
                code, text = bounded("room-" + name + "-clients", command)
                markers = [line.split("=", 1)[1] for line in text.splitlines()
                           if line.startswith("NEPTUNE_ROOM_CAPACITY=")]
                expected = {"seats": seats, "humans": humans, "bots": bots,
                            "preset_limit": preset, "protocol_limit": 12,
                            "accepted": humans, "refused": 1, "snapshots": humans, "maps": humans, "active": True}
                receipt = json.loads(markers[0]) if len(markers) == 1 else {}
                policy = receipt.pop("bot_policy", "")
                seed = receipt.pop("bot_policy_seed", "")
                if (code or ERROR.search(text) or len(markers) != 1 or receipt != expected
                        or policy != "neptune-heuristic-rng-v1" or not isinstance(seed, str)
                        or not seed.lstrip("-").isdigit()):
                    raise SystemExit("FAIL: real room " + name + "; inspect client/server evidence")
                text = ANSI.sub("", server_log.read_text())
                if (ERROR.search(text) or text.count("[Server] Peer connected:") != humans + 1
                        or text.count("[Server] Player admission refused: room_full") != 1
                        or text.count("Match started! Countdown complete.") != 1):
                    raise SystemExit("FAIL: server capacity/admission evidence for " + name)
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
