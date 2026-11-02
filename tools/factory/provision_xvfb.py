#!/usr/bin/env python3
"""Pinned, unprivileged Debian Xvfb preparation and a real X11 pixel smoke."""
from __future__ import annotations

import ctypes as C
import hashlib
import io
import json
import os
from pathlib import Path
import re
import select
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request

SCOPE = "X11 displayfd and pixel roundtrip only"
BASE = "https://security.debian.org/debian-security/pool/updates/main/x/xorg-server/"
FIELDS = {"kind", "platform", "minimum_free_bytes", "distribution", "version",
          "archive_url", "archive_sha256", "archive_bytes", "binary_sha256"}


def fail(kind, message):
    from provision import ProvisionError
    raise ProvisionError(kind, message)


def validate(recipe):
    if (set(recipe) != FIELDS or recipe["kind"] != "debian-xvfb" or
            recipe["distribution"] != "debian-13" or
            not re.fullmatch(r"2:21\.1\.[0-9]+-[0-9.]+\+deb13u[0-9]+", recipe["version"])):
        fail("invalid_recipe", "Require a pinned Debian13 Xvfb recipe")
    filename = "xvfb_" + recipe["version"].split(":", 1)[1] + "_amd64.deb"
    if recipe["archive_url"] != BASE + filename:
        fail("invalid_recipe", "Require the official versioned Debian security archive")
    for key in ("archive_sha256", "binary_sha256"):
        if not isinstance(recipe[key], str) or not re.fullmatch(r"[0-9a-f]{64}", recipe[key]):
            fail("invalid_recipe", "Require exact archive and binary hashes")
    if type(recipe["archive_bytes"]) is not int or not 1 <= recipe["archive_bytes"] <= 8 * 1024**2:
        fail("invalid_recipe", "Invalid Xvfb archive size budget")


def host_check(recipe, os_release=Path("/etc/os-release")):
    values = dict(line.split("=", 1) for line in os_release.read_text().splitlines()
                  if "=" in line and not line.startswith("#"))
    if values.get("ID", "").strip('"') != "debian" or values.get("VERSION_ID", "").strip('"') != "13":
        fail("unsupported_platform", "This Xvfb package requires Debian13 amd64; add a tested recipe for other distributions")
    for command in ("dpkg-deb", "dpkg-query", "dpkg", "xkbcomp"):
        if shutil.which(command, path=os.defpath) is None:
            fail("missing_host_dependency", "Managed preparation required for: " + command)
    result = subprocess.run(["dpkg-query", "-W", "-f=${Version}", "xserver-common"],
                            capture_output=True, text=True, timeout=10)
    if result.returncode or subprocess.run(
            ["dpkg", "--compare-versions", result.stdout.strip(), ">=", recipe["version"]],
            capture_output=True, timeout=10).returncode:
        fail("missing_host_dependency", "Managed preparation requires compatible xserver-common >= " + recipe["version"])
    try:
        C.CDLL("libX11.so.6")
        C.CDLL("libXfont2.so.2")
    except OSError:
        fail("missing_host_dependency", "Managed preparation requires X11/Xfont runtime libraries")


def unpack(archive, recipe, payload):
    if len(archive) != recipe["archive_bytes"] or hashlib.sha256(archive).hexdigest() != recipe["archive_sha256"]:
        fail("source_mismatch", "Xvfb package size/hash differs from the reviewed pin")
    package = payload.parent / "xvfb.deb"
    package.write_bytes(archive)
    result = subprocess.run(["dpkg-deb", "--fsys-tarfile", str(package)],
                            check=True, capture_output=True, timeout=20)
    with tarfile.open(fileobj=io.BytesIO(result.stdout)) as tar:
        member = tar.getmember("./usr/bin/Xvfb")
        if not member.isfile() or not 1 <= member.size <= 8 * 1024**2:
            fail("source_mismatch", "Xvfb package has no bounded regular binary")
        content = tar.extractfile(member).read()
    if hashlib.sha256(content).hexdigest() != recipe["binary_sha256"]:
        fail("source_mismatch", "Extracted Xvfb binary differs from the reviewed pin")
    binary = payload / "Xvfb"
    binary.write_bytes(content)
    binary.chmod(0o755)


def install(recipe, payload):
    validate(recipe)
    host_check(recipe)
    with urllib.request.urlopen(recipe["archive_url"], timeout=30) as response:
        if response.geturl() != recipe["archive_url"]:
            fail("source_mismatch", "Unexpected Xvfb download redirect")
        archive = response.read(recipe["archive_bytes"] + 1)
    unpack(archive, recipe, payload)


def pixel_roundtrip(display):
    x = C.CDLL("libX11.so.6")
    signatures = {
        "XOpenDisplay": ([C.c_char_p], C.c_void_p),
        "XDefaultScreen": ([C.c_void_p], C.c_int),
        "XDisplayWidth": ([C.c_void_p, C.c_int], C.c_int),
        "XDisplayHeight": ([C.c_void_p, C.c_int], C.c_int),
        "XDefaultDepth": ([C.c_void_p, C.c_int], C.c_int),
        "XRootWindow": ([C.c_void_p, C.c_int], C.c_ulong),
        "XCreateSimpleWindow": ([C.c_void_p, C.c_ulong, C.c_int, C.c_int,
                                 C.c_uint, C.c_uint, C.c_uint, C.c_ulong, C.c_ulong], C.c_ulong),
        "XMapWindow": ([C.c_void_p, C.c_ulong], C.c_int),
        "XSync": ([C.c_void_p, C.c_int], C.c_int),
        "XGetImage": ([C.c_void_p, C.c_ulong, C.c_int, C.c_int, C.c_uint,
                       C.c_uint, C.c_ulong, C.c_int], C.c_void_p),
        "XGetPixel": ([C.c_void_p, C.c_int, C.c_int], C.c_ulong),
        "XDestroyImage": ([C.c_void_p], C.c_int),
        "XCloseDisplay": ([C.c_void_p], C.c_int),
    }
    for name, (args, result) in signatures.items():
        function = getattr(x, name)
        function.argtypes, function.restype = args, result
    connection = x.XOpenDisplay(display.encode("ascii"))
    if not connection:
        fail("smoke_failed", "Xvfb announced a display but X11 could not connect")
    try:
        screen = x.XDefaultScreen(connection)
        dimensions = (x.XDisplayWidth(connection, screen), x.XDisplayHeight(connection, screen),
                      x.XDefaultDepth(connection, screen))
        if dimensions != (640, 480, 24):
            fail("smoke_failed", "Xvfb screen geometry/depth differs")
        window = x.XCreateSimpleWindow(connection, x.XRootWindow(connection, screen),
                                       0, 0, 8, 8, 0, 0, 0x123456)
        x.XMapWindow(connection, window)
        x.XSync(connection, 0)
        image = x.XGetImage(connection, window, 0, 0, 8, 8, C.c_ulong(-1), 2)
        if not image:
            fail("smoke_failed", "X11 framebuffer read failed")
        try:
            pixel = x.XGetPixel(image, 3, 3)
            if pixel != 0x123456:
                fail("smoke_failed", "X11 pixel roundtrip mismatch")
        finally:
            x.XDestroyImage(image)
        return {"scope": SCOPE, "width": 640, "height": 480, "depth": 24, "pixel": pixel}
    finally:
        x.XCloseDisplay(connection)


def probe(binary, log_path=None):
    read_fd, write_fd = os.pipe()
    process = None
    log = open(log_path, "xb") if log_path else tempfile.TemporaryFile()
    try:
        process = subprocess.Popen([str(binary), "-displayfd", str(write_fd), "-screen", "0",
                                    "640x480x24", "-nolisten", "tcp", "-noreset", "-fp", "built-ins"],
                                   stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                   pass_fds=(write_fd,))
        os.close(write_fd)
        write_fd = None
        if not select.select([read_fd], [], [], 8)[0]:
            fail("smoke_failed", "Xvfb displayfd startup timed out")
        display = os.read(read_fd, 32).decode("ascii")
        if not re.fullmatch(r"[0-9]{1,5}\n", display) or process.poll() is not None:
            fail("smoke_failed", "Xvfb failed before announcing a display")
        return pixel_roundtrip(":" + display.strip())
    finally:
        os.close(read_fd)
        if write_fd is not None:
            os.close(write_fd)
        if process is not None:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        log.close()


if __name__ == "__main__":
    try:
        if sys.argv[1] == "install":
            install(json.loads(Path(sys.argv[2]).read_text()), Path(sys.argv[3]))
        elif sys.argv[1] == "probe":
            print(json.dumps(probe(Path(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else None), sort_keys=True))
        else:
            raise ValueError("Unknown Xvfb operation")
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
