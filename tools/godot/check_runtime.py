#!/usr/bin/env python3
"""Bounded real native startup/connection checks, not a match or browser test."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time

from run_bot_tests import ANSI, ERROR, ROOT


@contextmanager
def graphical_environment(env, evidence):
    if not shutil.which("Xvfb"):
        raise SystemExit("FAIL: --graphical requires Xvfb")
    display = evidence / "xvfb-display.txt"
    with display.open("w") as number, (evidence / "xvfb.log").open("w") as errors:
        desktop = subprocess.Popen(
            ["Xvfb", "-displayfd", str(number.fileno()), "-screen", "0", "640x480x24",
             "-nolisten", "tcp", "-ac"], env=env, stdout=subprocess.DEVNULL,
            stderr=errors, pass_fds=(number.fileno(),))
        try:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                value = display.read_text().strip()
                if desktop.poll() is not None:
                    raise SystemExit("FAIL: Xvfb startup; inspect xvfb.log")
                if value.isdigit():
                    break
                time.sleep(0.05)
            else:
                raise SystemExit("FAIL: Xvfb startup timeout")
            yield {**env, "DISPLAY": ":" + value}
        finally:
            desktop.terminate()
            try:
                desktop.wait(timeout=3)
            except subprocess.TimeoutExpired:
                desktop.kill()
                desktop.wait(timeout=3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", required=True)
    parser.add_argument("--evidence", type=Path, default=ROOT / ".godot/runtime-evidence")
    parser.add_argument("--graphical", action="store_true", help="Also require an Xvfb desktop client")
    parser.add_argument("--process-timeout", type=float, default=30.0,
                        help="Bound each engine process, including graphical driver startup (5..60 seconds)")
    args = parser.parse_args()
    if not 5.0 <= args.process_timeout <= 60.0:
        parser.error("--process-timeout must be between 5 and 60 seconds")
    args.evidence.mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "LANG", "LC_ALL", "USER", "LOGNAME")}
    for key in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
        folder = ROOT / ".godot/restart-runtime" / key.lower()
        folder.mkdir(parents=True, exist_ok=True)
        env[key] = str(folder)
    base = [args.godot, "--headless", "--path", str(ROOT)]

    def bounded(name, command, timeout=None, process_env=None):
        timeout = args.process_timeout if timeout is None else timeout
        log = args.evidence / (name + ".log")
        record = {"command": command, "timeout_sec": timeout}
        started = time.monotonic()
        with log.open("w") as output:
            try:
                result = subprocess.run(command, env=process_env or env, stdout=output,
                                        stderr=subprocess.STDOUT, timeout=timeout)
                record.update(exit=result.returncode, status="completed")
            except subprocess.TimeoutExpired:
                record.update(exit=None, status="timed_out")
                output.flush()
                print(log.read_text()[-3000:])
                raise SystemExit("FAIL: " + name + " process startup/execution bound; inspect " + str(log))
            finally:
                record["elapsed_sec"] = round(time.monotonic() - started, 3)
                (args.evidence / (name + ".json")).write_text(json.dumps(record, indent=2) + "\n")
        return result.returncode, ANSI.sub("", log.read_text())

    code, text = bounded("import", base + ["--editor", "--import", "--quit"], 90)
    if code or ERROR.search(text):
        raise SystemExit("FAIL: import; inspect runtime evidence")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    server_command = base + ["res://main_server.tscn", "--", "--server-port=" + str(port)]
    server_log = args.evidence / "server.log"
    with server_log.open("w") as output:
        server = subprocess.Popen(server_command, env=env, stdout=output, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                text = server_log.read_text()
                if server.poll() is not None or ERROR.search(ANSI.sub("", text)):
                    raise SystemExit("FAIL: server startup; inspect server.log")
                if "Server listening on port " + str(port) in text:
                    break
                time.sleep(0.05)
            else:
                raise SystemExit("FAIL: server startup timeout")
            if text.count("=== Bomberman Server Starting ===") != 1:
                raise SystemExit("FAIL: duplicate server owner")
            code, text = bounded("duplicate-server", server_command)
            if code == 0 or "Failed to start server" not in text:
                raise SystemExit("FAIL: occupied port must fail non-zero")
            clients = [("default-headless-client", base), ("explicit-headless-client", base)]
            if args.graphical:
                clients.append(("graphical-client", [args.godot,
                                "--display-driver", "x11", "--rendering-method", "gl_compatibility",
                                "--rendering-driver", "opengl3", "--audio-driver", "Dummy", "--path", str(ROOT)]))
            for name, command in clients:
                options = ["--server-port=" + str(port)]
                if name != "default-headless-client":
                    options.append("--runtime-role=client")
                command = command + ["res://tools/godot/runtime_probe.tscn", "--", *options]
                if name == "graphical-client":
                    with graphical_environment(env, args.evidence) as desktop_env:
                        desktop_env["LIBGL_ALWAYS_SOFTWARE"] = "1"
                        code, text = bounded(name, command, process_env=desktop_env)
                else:
                    code, text = bounded(name, command)
                if (code or ERROR.search(text) or "NEPTUNE_RUNTIME_CONNECTED" not in text
                        or "NEPTUNE_PROTOCOL_SELECTED=1" not in text
                        or "=== Bomberman Server Starting ===" in text):
                    raise SystemExit("FAIL: " + name + "; inspect evidence")
                print("PASS:", name, "connected through actual ClientMain")
            before = len(server_log.read_text())
            code, text = bounded("incompatible-production-client", base + [
                "res://tools/godot/runtime_probe.tscn", "--", "--runtime-role=client",
                "--server-port=" + str(port), "--probe-incompatible"])
            if (code or ERROR.search(text) or
                    "NEPTUNE_PROTOCOL_CLIENT_REFUSED=incompatible_protocol_versions" not in text):
                raise SystemExit("FAIL: production client did not surface compatibility refusal")
            if "[Server] Peer connected:" in server_log.read_text()[before:]:
                raise SystemExit("FAIL: incompatible production client reached server admission")
            print("PASS: actual ClientMain surfaces incompatibility without admitting/authenticating")
            for mode, reason in [("future", "incompatible_protocol_versions"),
                                 ("retry", "incompatible_protocol_versions"),
                                 ("malformed", "invalid_protocol_offer"),
                                 ("invalid", "invalid_protocol_offer"),
                                 ("duplicate", "invalid_protocol_offer"),
                                 ("oversized", "protocol_offer_too_large"),
                                 ("bytes", "invalid_protocol_offer"),
                                 ("format", "invalid_protocol_offer"),
                                 ("silent", "protocol_handshake_timeout_or_disconnect")]:
                before = len(server_log.read_text())
                command = base + ["res://tools/godot/protocol_probe.tscn", "--",
                                  "--runtime-role=test", "--server-port=" + str(port),
                                  "--protocol-probe=" + mode]
                code, text = bounded("protocol-" + mode, command)
                if (code or ERROR.search(text) or
                        "NEPTUNE_PROTOCOL_REJECTED mode=" + mode not in text):
                    raise SystemExit("FAIL: protocol-" + mode + "; inspect evidence")
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    delta = server_log.read_text()[before:]
                    if reason in delta:
                        break
                    time.sleep(0.05)
                else:
                    raise SystemExit("FAIL: no server rejection evidence for " + mode)
                if "[Server] Peer connected:" in delta:
                    raise SystemExit("FAIL: rejected protocol reached server admission")
                print("PASS: pre-connection protocol rejection:", mode)
            text = ANSI.sub("", server_log.read_text())
            if ERROR.search(text) or text.count("[Server] Peer connected:") != len(clients):
                raise SystemExit("FAIL: server did not confirm every connection")
        finally:
            server.terminate()
            try:
                server.wait(timeout=3)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=3)
    for name, option in [("invalid-role", "--runtime-role=invalid"), ("invalid-port", "--server-port=0")]:
        code, text = bounded(name, base + ["res://tools/godot/runtime_probe.tscn", "--", option])
        if code != 2 or "Invalid --" not in text:
            raise SystemExit("FAIL: invalid configuration must exit 2")
    print("PASS: single server owner, non-zero bind failure and invalid-config checks")
    print("Native connection/startup evidence only; no match, browser or parity claim.")


if __name__ == "__main__":
    main()
