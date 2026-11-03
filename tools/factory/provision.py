#!/usr/bin/env python3
"""Prepare trusted pinned tools before offline verification; never uses sudo.

Run only from coordinator-trusted source in an unprivileged, network-enabled
preparation sandbox. This command is not itself an OS sandbox or scheduler.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid
import provision_xvfb as xvfb
import provision_ocr as ocr
import provision_ghidra as ghidra

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "neptune.tool-install.v1"
MAX_LOG = 8 * 1024 * 1024


class ProvisionError(ValueError):
    def __init__(self, kind, message):
        super().__init__(message)
        self.kind = kind


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def safe_path(path):
    path = Path(os.path.abspath(path))
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ProvisionError("unsafe_path", "Symlinked preparation paths are not supported")
    return path


def write_json(path, value):
    temp = path.with_name(path.name + ".tmp")
    if path.is_symlink() or temp.is_symlink():
        raise ProvisionError("unsafe_path", "Refusing symlinked receipt")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temp.replace(path)


def identity(tool, root):
    if tool not in ("godot", "beetle-saturn", "beetle-saturn-call-trace", "beetle-saturn-context-trace", "beetle-saturn-init-trace", "beetle-saturn-command-trace", "xvfb", "tesseract", "ghidra"):
        raise ProvisionError("needs_recipe", "Create/reuse a bounded trusted recipe task for: " + tool)
    path = root / "tools/factory/provision-lock.json"
    lock = json.loads(path.read_text())
    if lock.get("schema") != "neptune.tool-recipes.v1" or set(lock.get("tools", {})) != {"godot", "beetle-saturn", "beetle-saturn-call-trace", "beetle-saturn-context-trace", "beetle-saturn-init-trace", "beetle-saturn-command-trace", "xvfb", "tesseract", "ghidra"}:
        raise ProvisionError("invalid_recipe", "Unsupported recipe registry")
    recipe = lock["tools"][tool]
    fields = {"kind", "platform", "minimum_free_bytes"}
    if tool in ("beetle-saturn", "beetle-saturn-call-trace", "beetle-saturn-context-trace", "beetle-saturn-init-trace", "beetle-saturn-command-trace"):
        fields |= {"repository", "commit"}
    if tool == "xvfb":
        xvfb.validate(recipe)
        fields = xvfb.FIELDS
    if tool == "tesseract":
        ocr.validate(recipe)
        fields = ocr.FIELDS
    if tool == "ghidra":
        ghidra.validate(recipe)
        fields = ghidra.FIELDS
    if set(recipe) != fields or recipe["kind"] != {"godot": "godot-locked", "beetle-saturn": "beetle-source", "beetle-saturn-call-trace": "beetle-call-trace", "beetle-saturn-context-trace": "beetle-context-trace", "beetle-saturn-init-trace": "beetle-init-trace", "beetle-saturn-command-trace": "beetle-command-trace", "xvfb": "debian-xvfb", "tesseract": "tesseract-source", "ghidra": "ghidra-jdk"}[tool]:
        raise ProvisionError("invalid_recipe", "Unsupported installer/recipe fields")
    if recipe["platform"] != "linux-x86_64":
        raise ProvisionError("invalid_recipe", "Unsupported recipe platform")
    if type(recipe["minimum_free_bytes"]) is not int or not 256 * 1024**2 <= recipe["minimum_free_bytes"] <= 16 * 1024**3:
        raise ProvisionError("invalid_recipe", "Invalid disk budget")
    if tool in ("beetle-saturn", "beetle-saturn-call-trace", "beetle-saturn-context-trace", "beetle-saturn-init-trace", "beetle-saturn-command-trace") and (recipe["repository"] != "https://github.com/libretro/beetle-saturn-libretro.git" or
                                    not re.fullmatch(r"[0-9a-f]{40}", recipe["commit"])):
        raise ProvisionError("invalid_recipe", "Require official repository and exact source commit")
    sources = ["tools/factory/provision.py", "tools/factory/provision_probe.py"]
    if tool == "godot":
        sources += ["tools/godot/install.py", "tools/godot/toolchain.json"]
    if tool == "ghidra":
        sources += ["tools/factory/provision_ghidra.py", "tools/factory/provision_ghidra_smoke.java"]
    if tool == "xvfb":
        sources += ["tools/factory/provision_xvfb.py"]
    if tool == "tesseract":
        sources += ["tools/factory/provision_ocr.py"]
    if tool == "beetle-saturn-call-trace":
        sources += ["tools/factory/provision_call_trace.py", "tools/factory/provision_call_trace.h",
                    "tools/factory/provision_call_trace_abi.py"]
    if tool == "beetle-saturn-context-trace":
        sources += ["tools/factory/provision_call_trace.py", "tools/factory/provision_context_trace.py",
                    "tools/factory/provision_context_trace.h", "tools/factory/provision_context_trace_abi.py"]
    if tool == "beetle-saturn-init-trace":
        sources += ["tools/factory/provision_call_trace.py", "tools/factory/provision_init_trace.py",
                    "tools/factory/provision_init_trace.h", "tools/factory/provision_init_trace_abi.py"]
    if tool == "beetle-saturn-command-trace":
        sources += ["tools/factory/provision_call_trace.py", "tools/factory/provision_command_trace.py",
                    "tools/factory/provision_command_trace.h", "tools/factory/provision_command_trace_abi.py"]
    record = {"tool": tool, "recipe": recipe, "installer_sources": {p: digest(root / p) for p in sources}}
    key = hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()
    return recipe, record, key


def environment(work):
    # Preserve configured TLS/proxy routing; never inherit provider/Git credentials.
    result = {"PATH": os.defpath, "HOME": str(work / "home"), "TMPDIR": str(work / "tmp"),
              "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "GIT_TERMINAL_PROMPT": "0",
              "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null"}
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "http_proxy", "https_proxy",
                 "all_proxy", "no_proxy", "SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE",
                 "CURL_CA_BUNDLE", "GIT_SSL_CAINFO"):
        if name in os.environ:
            result[name] = os.environ[name]
    for directory in (work / "home", work / "tmp"):
        directory.mkdir(exist_ok=True)
    return result


class Runner:
    def __init__(self, evidence, report, work, deadline):
        self.evidence, self.report, self.env, self.deadline = evidence, report, environment(work), deadline

    def run(self, argv, cwd, timeout=60):
        remaining = min(timeout, self.deadline - time.monotonic())
        if remaining <= 0:
            raise ProvisionError("timed_out", "Preparation time budget exhausted")
        item = {"argv": list(argv), "cwd": str(cwd), "status": "running"}
        self.report["commands"].append(item)
        log = self.evidence / (str(len(self.report["commands"])) + ".log")
        item["log"] = log.name
        write_json(self.evidence / "report.json", self.report)
        started = time.monotonic()
        with log.open("wb") as output:
            try:
                process = subprocess.Popen(argv, cwd=cwd, env=self.env, stdin=subprocess.DEVNULL,
                                           stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
            except OSError:
                item.update(status="failure", exit=None)
                write_json(self.evidence / "report.json", self.report)
                raise
            try:
                while process.poll() is None:
                    if time.monotonic() - started > remaining:
                        raise ProvisionError("timed_out", "Tool command exceeded its deadline")
                    if log.stat().st_size > MAX_LOG:
                        raise ProvisionError("log_limit", "Tool command exceeded log budget")
                    time.sleep(0.05)
                if log.stat().st_size > MAX_LOG:
                    raise ProvisionError("log_limit", "Tool command exceeded log budget")
                if process.returncode != 0:
                    raise ProvisionError("command_failed", "Tool command failed; inspect bounded evidence log")
                item.update(status="success", exit=0)
            except BaseException:
                item.update(status="failure", exit=process.poll())
                raise
            finally:
                # Reap descendants too, including children left by a failed build.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
                item["seconds"] = round(time.monotonic() - started, 3)
                write_json(self.evidence / "report.json", self.report)
        with log.open() as source:
            return source.read(65536).strip()


def binary_name(tool, root):
    if tool == "ghidra":
        return "ghidra-headless"
    if tool == "tesseract":
        return "tesseract"
    if tool == "xvfb":
        return "Xvfb"
    if tool in ("beetle-saturn", "beetle-saturn-call-trace", "beetle-saturn-context-trace", "beetle-saturn-init-trace", "beetle-saturn-command-trace"):
        return "mednafen_saturn_libretro.so"
    lock = json.loads((root / "tools/godot/toolchain.json").read_text())
    name = lock.get("binary_name")
    if not isinstance(name, str) or not re.fullmatch(r"Godot_v[0-9]+\.[0-9]+(?:\.[0-9]+)?-stable_linux\.x86_64", name):
        raise ProvisionError("invalid_recipe", "Unexpected Godot output name")
    return name


def smoke(tool, binary, runner, root):
    if tool == "ghidra":
        return ghidra.smoke(identity(tool, root)[0], binary, runner, root)
    if tool == "tesseract":
        return ocr.smoke(identity(tool, root)[0], binary, runner)
    if tool == "xvfb":
        recipe = identity(tool, root)[0]
        xvfb.host_check(recipe)
        if digest(binary) != recipe["binary_sha256"]:
            raise ProvisionError("smoke_failed", "Xvfb binary differs from pinned upstream hash")
        result = json.loads(runner.run([sys.executable, str(root / "tools/factory/provision_xvfb.py"),
                                        "probe", str(binary), str(runner.evidence / "xvfb-server.log")], binary.parent, 20))
        if result != {"scope": xvfb.SCOPE, "width": 640, "height": 480, "depth": 24, "pixel": 0x123456}:
            raise ProvisionError("smoke_failed", "Missing actual X11 display/pixel observation")
        return result
    if tool in ("beetle-saturn", "beetle-saturn-call-trace", "beetle-saturn-context-trace", "beetle-saturn-init-trace", "beetle-saturn-command-trace"):
        result = json.loads(runner.run([sys.executable, str(root / "tools/factory/provision_probe.py"), str(binary)], binary.parent, 30))
        if result.get("scope") != "no-media ABI smoke only" or result.get("api") != 1:
            raise ProvisionError("smoke_failed", "Missing real libretro probe result")
        if tool == "beetle-saturn-call-trace":
            observer = json.loads(runner.run([sys.executable, str(root / "tools/factory/provision_call_trace_abi.py"),
                                              "--probe-core", str(binary)], binary.parent, 30))
            if (observer.get("abi") != 2 or observer.get("record_bytes") != 120 or
                    observer.get("rejected_invalid_entry_budget_and_frame") is not True):
                raise ProvisionError("smoke_failed", "Missing actual bounded observer ABI/fence result")
            return {"libretro": result, "observer": observer}
        if tool == "beetle-saturn-context-trace":
            observer = json.loads(runner.run([sys.executable, str(root / "tools/factory/provision_context_trace_abi.py"),
                                              "--probe-core", str(binary)], binary.parent, 30))
            if (observer.get("abi") != 2 or observer.get("record_bytes") != 1996 or
                    observer.get("rejected_invalid_profile_budget_witness_and_frame") is not True):
                raise ProvisionError("smoke_failed", "Missing actual bounded context observer ABI/fence result")
            return {"libretro": result, "observer": observer}
        if tool == "beetle-saturn-init-trace":
            observer = json.loads(runner.run([sys.executable, str(root / "tools/factory/provision_init_trace_abi.py"),
                                              "--probe-core", str(binary)], binary.parent, 30))
            if (observer.get("abi") != 1 or observer.get("record_bytes") != 824 or
                    observer.get("rejected_invalid_profile_budget_witness_and_frame") is not True):
                raise ProvisionError("smoke_failed", "Missing actual bounded initialization observer ABI/fence result")
            return {"libretro": result, "observer": observer}
        if tool == "beetle-saturn-command-trace":
            observer = json.loads(runner.run([sys.executable, str(root / "tools/factory/provision_command_trace_abi.py"),
                                              "--probe-core", str(binary)], binary.parent, 30))
            if (observer.get("abi") != 1 or observer.get("record_bytes") != 216 or
                    observer.get("capacity") != 128 or observer.get("witness_words") != 424 or
                    observer.get("rejected_invalid_profile_witness_and_frame") is not True):
                raise ProvisionError("smoke_failed", "Missing actual bounded command observer ABI/fence result")
            return {"libretro": result, "observer": observer}
        return result
    lock = json.loads((root / "tools/godot/toolchain.json").read_text())
    if digest(binary) != lock["binary_sha256"]:
        raise ProvisionError("smoke_failed", "Godot binary differs from pinned upstream hash")
    for relative, expected in lock["addons"].items():
        candidate = safe_path(root / relative)
        if not candidate.is_relative_to(root) or digest(candidate) != expected:
            raise ProvisionError("smoke_failed", "Native addon identity mismatch")
    version = runner.run([str(binary), "--headless", "--version"], binary.parent, 30)
    if version != lock["godot_version"]:
        raise ProvisionError("smoke_failed", "Godot runtime version differs")
    return {"scope": "version and pinned addon identity only", "version": version}


def install(tool, recipe, payload, work, runner, root):
    if tool == "ghidra":
        return ghidra.install(recipe, payload, work, runner, root)
    if tool == "tesseract":
        return ocr.install(recipe, payload, work, runner, root)
    if tool == "xvfb":
        xvfb.host_check(recipe)
        recipe_path = work / "xvfb-recipe.json"
        write_json(recipe_path, recipe)
        runner.run([sys.executable, str(root / "tools/factory/provision_xvfb.py"),
                    "install", str(recipe_path), str(payload)], work, 90)
        return
    if tool == "godot":
        runner.run([sys.executable, str(root / "tools/godot/install.py"), "--directory", str(payload)], root, 180)
        return
    for program in ("git", "make", "cc", "c++"):
        if shutil.which(program, path=os.defpath) is None:
            raise ProvisionError("missing_host_dependency", "Managed provisioning required for: " + program)
        runner.run([program, "--version"], work, 15)
    source = work / "source"
    source.mkdir()
    runner.run(["git", "init", "--quiet"], source)
    runner.run(["git", "remote", "add", "origin", recipe["repository"]], source)
    runner.run(["git", "fetch", "--depth=1", "origin", recipe["commit"]], source, 180)
    runner.run(["git", "checkout", "--detach", "FETCH_HEAD"], source)
    actual = runner.run(["git", "rev-parse", "HEAD"], source)
    if actual != recipe["commit"]:
        raise ProvisionError("source_mismatch", "Fetched source differs from the pinned commit")
    if tool == "beetle-saturn-call-trace":
        patched = json.loads(runner.run([sys.executable, str(root / "tools/factory/provision_call_trace.py"),
                                        "--source", str(source)], work, 30))
        if patched.get("reference_revision") != actual or patched.get("observer_abi") != 2:
            raise ProvisionError("source_mismatch", "Observer patch identity mismatch")
        write_json(payload / "call-trace-build.json", patched)
    if tool in ("beetle-saturn-context-trace", "beetle-saturn-init-trace"):
        name = "context" if tool == "beetle-saturn-context-trace" else "init"
        patched = json.loads(runner.run([sys.executable, str(root / ("tools/factory/provision_" + name + "_trace.py")),
                                        "--source", str(source)], work, 30))
        if patched.get("reference_revision") != actual or patched.get("observer_abi") != (2 if name == "context" else 1):
            raise ProvisionError("source_mismatch", "Separate observer patch identity mismatch")
        # CI may export this separate native payload. Include corresponding
        # patched source and upstream notices, before any compilation products.
        archive_path = payload / "corresponding-source.tar.gz"
        with tarfile.open(archive_path, "w:gz") as archive:
            archive.add(source, arcname="beetle-saturn", filter=lambda item:
                        None if ".git" in Path(item.name).parts else item)
        shutil.copy2(source / "COPYING", payload / "COPYING")
        patched["corresponding_source_sha256"] = digest(archive_path)
        patched["licence_sha256"] = digest(payload / "COPYING")
        write_json(payload / (name + "-trace-build.json"), patched)
    if tool == "beetle-saturn-command-trace":
        patched = json.loads(runner.run([sys.executable, str(root / "tools/factory/provision_command_trace.py"),
                                        "--source", str(source), "--header", str(root / "tools/factory/provision_command_trace.h")], work, 30))
        if (patched.get("reference_revision") != actual or patched.get("schema") != "neptune.command-trace-patch-component.v1" or
                patched.get("component_only") is not True or patched.get("native_tool_ready") is not False):
            raise ProvisionError("source_mismatch", "Separate command observer patch identity mismatch")
        archive_path = payload / "corresponding-source.tar.gz"
        with tarfile.open(archive_path, "w:gz") as archive:
            archive.add(source, arcname="beetle-saturn", filter=lambda item:
                        None if ".git" in Path(item.name).parts else item)
        shutil.copy2(source / "COPYING", payload / "COPYING")
        patched["corresponding_source_sha256"] = digest(archive_path)
        patched["licence_sha256"] = digest(payload / "COPYING")
        write_json(payload / "command-trace-build.json", patched)
    runner.run(["make", "-j1", "platform=unix", "LTO=0", "HAVE_OPENGL=0", "HAVE_CHD=1"], source, 1200)
    binary = safe_path(source / binary_name(tool, root))
    if not binary.is_file():
        raise ProvisionError("missing_output", "Build produced no core")
    shutil.copy2(binary, payload / binary.name)


def cached(target, tool, key, root):
    receipt = safe_path(target / "receipt.json")
    binary = safe_path(target / binary_name(tool, root))
    data = json.loads(receipt.read_text())
    if (data.get("schema") != SCHEMA or data.get("tool") != tool or data.get("recipe_sha256") != key or
            data.get("conclusion") != "success" or not binary.is_file() or
            data.get("binary_sha256") != digest(binary)):
        raise ProvisionError("invalid_cache", "Cache identity/receipt mismatch")
    return binary


def ensure(tool, cache, evidence, *, timeout=1200, root=ROOT, installer=install, prober=smoke):
    cache, evidence, root = safe_path(cache), safe_path(evidence), safe_path(root)
    if evidence.exists():
        raise ProvisionError("existing_evidence", "Use a fresh evidence directory")
    evidence.mkdir(parents=True, mode=0o700)
    report = {"schema": SCHEMA, "tool": tool, "commands": [], "conclusion": "running",
              "started_at": time.time()}
    try:
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", tool):
            raise ProvisionError("needs_recipe", "Invalid tool capability ID")
        if type(timeout) is not int or not 10 <= timeout <= 1800:
            raise ProvisionError("invalid_budget", "Timeout must be 10..1800 seconds")
        if platform.system() != "Linux" or platform.machine() not in ("x86_64", "AMD64"):
            raise ProvisionError("unsupported_platform", "These recipes require Linux x86_64")
        recipe, inputs, key = identity(tool, root)
        report.update(recipe_sha256=key, inputs=inputs, host={"system": platform.system(), "machine": platform.machine()})
        cache.mkdir(parents=True, exist_ok=True, mode=0o700)
        if cache.stat().st_uid != os.geteuid() or cache.stat().st_mode & 0o022:
            raise ProvisionError("unsafe_path", "Preparation cache must be owned by this user and not group/world writable")
        target = safe_path(cache / (tool + "-" + key))
        report["directory"] = str(target)
        lock_path = safe_path(cache / (tool + ".lock"))
        with lock_path.open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise ProvisionError("busy", "Another installer owns this tool; requeue without duplicate build") from error
            with tempfile.TemporaryDirectory(prefix=".prepare-" + tool + "-", dir=cache) as temporary:
                work = Path(temporary)
                runner = Runner(evidence, report, work, time.monotonic() + timeout)
                reused = False
                if target.exists():
                    try:
                        binary = cached(target, tool, key, root)
                        observation = prober(tool, binary, runner, root)
                        reused = True
                    except (ValueError, OSError, KeyError) as error:
                        # Preserve the invalid generation and regenerate at most once.
                        previous = target.with_name(target.name + ".replaced-" + uuid.uuid4().hex)
                        target.rename(previous)
                        report["replaced_cache"] = {"path": str(previous), "reason": str(error)}
                if not reused:
                    if shutil.disk_usage(cache).free < recipe["minimum_free_bytes"]:
                        raise ProvisionError("disk_budget", "Insufficient free space for bounded preparation")
                    payload = work / "payload"
                    payload.mkdir()
                    installer(tool, recipe, payload, work, runner, root)
                    candidate = safe_path(payload / binary_name(tool, root))
                    if not candidate.is_file() or not candidate.stat().st_size:
                        raise ProvisionError("missing_output", "Installer did not produce a nonempty binary")
                    observation = prober(tool, candidate, runner, root)
                    write_json(payload / "receipt.json", {"schema": SCHEMA, "tool": tool,
                               "recipe_sha256": key, "inputs": inputs, "binary_sha256": digest(candidate),
                               "smoke": observation, "conclusion": "success"})
                    payload.rename(target)
                    binary = cached(target, tool, key, root)
                report.update(conclusion="success", reused=reused, binary=str(binary),
                              binary_sha256=digest(binary), smoke=observation,
                              receipt_sha256=digest(target / "receipt.json"))
        return report
    except Exception as error:
        report.update(conclusion="failure", kind=getattr(error, "kind", "preparation_failed"), error=str(error))
        raise
    finally:
        write_json(evidence / "report.json", report)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tool", required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=1200)
    args = parser.parse_args(argv)
    try:
        report = ensure(args.tool, args.cache, args.evidence, timeout=args.timeout)
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print("FAIL: " + str(error), file=sys.stderr)
        return 1
    print("NEPTUNE_TOOL_READY=" + json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
