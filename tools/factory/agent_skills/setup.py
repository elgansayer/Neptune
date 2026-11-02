#!/usr/bin/env python3
"""Expose the pinned skill library globally across supported harnesses."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

import install as recipe

HERE = Path(__file__).resolve().parent


def run(arguments, **kwargs):
    # Node's process.exit can truncate large JSON written to a pipe. Regular
    # output files make the CLI's writes synchronous and preserve all records.
    with tempfile.TemporaryFile(mode="w+") as output, tempfile.TemporaryFile(mode="w+") as errors:
        result = subprocess.run(arguments, check=False, stdout=output, stderr=errors, text=True, timeout=180, **kwargs)
        output.seek(0)
        errors.seek(0)
        stdout, stderr = output.read(8 * 1024**2 + 1), errors.read(8 * 1024**2 + 1)
    if len(stdout) > 8 * 1024**2 or len(stderr) > 8 * 1024**2:
        raise ValueError("Setup command output exceeds its diagnostic budget")
    if result.returncode:
        diagnostic = stderr[-2000:]
        try:
            parsed = json.loads(stdout)
            if isinstance(parsed, list):
                diagnostic = json.dumps([item for item in parsed if item.get("status") != "installed"][:3])
        except (ValueError, AttributeError):
            pass
        raise ValueError(f"Command failed: {arguments[0]}: {diagnostic}")
    return stdout


def roots(registry, user, environment):
    config = Path(environment.get("XDG_CONFIG_HOME") or user / ".config")
    bases = {"home": user, "configHome": config}
    for key, variable, fallback in [
        ("claudeHome", "CLAUDE_CONFIG_DIR", ".claude"),
        ("autohandHome", "AUTOHAND_HOME", ".autohand"),
        ("grokHome", "GROK_HOME", ".grok"),
        ("hermesHome", "HERMES_HOME", ".hermes"),
        ("vibeHome", "VIBE_HOME", ".vibe"),
    ]:
        bases[key] = Path(environment.get(variable) or user / fallback)
    bases["openclawHome"] = next((user / x for x in (".openclaw", ".clawdbot", ".moltbot") if (user / x).exists()), user / ".openclaw")
    result = {}
    for harness in registry["harnesses"]:
        definition = harness["global"]
        if definition:
            result[harness["id"]] = bases[definition["base"]].joinpath(*definition["parts"])
    # Current Antigravity App uses this path; the CLI registry retains legacy paths.
    result["antigravity-current"] = user / ".gemini/config/skills"
    result["pi-compatibility"] = user / ".pi/agent/skills"
    # Preserve CODEX_HOME and bridge older helpers that refer to its skills folder.
    result["codex-helper-compatibility"] = Path(environment.get("CODEX_HOME") or user / ".codex") / "skills"
    result["codex-default-compatibility"] = user / ".codex/skills"
    return result


def ensure_registrations(names, expected, destinations, canonical, verify=False, publish=False):
    checked = {}
    # Check every conflict before publishing any new aliases.
    for destination in set(destinations.values()) | {canonical}:
        for name in names:
            target = destination / name
            if target.exists():
                actual = target.resolve()
                if actual not in checked:
                    checked[actual] = recipe.tree_digest(actual)
                if checked[actual] != expected[name]:
                    raise ValueError(f"Preserve conflicting installed skill: {target}")
            elif target.is_symlink() or verify:
                raise ValueError(f"Missing or broken registration: {target}")
    if verify or not publish:
        return
    for destination in set(destinations.values()):
        if destination == canonical:
            continue
        destination.mkdir(parents=True, exist_ok=True)
        for name in names:
            target = destination / name
            if not target.exists():
                target.symlink_to(os.path.relpath(canonical / name, destination), target_is_directory=True)


def merge_mcp(path, entry, verify=False):
    if path.is_symlink():
        raise ValueError(f"Refuse linked client configuration: {path}")
    original = path.read_text() if path.exists() else None
    data = json.loads(original) if original is not None else {}
    if not isinstance(data, dict) or not isinstance(data.get("mcpServers", {}), dict):
        raise TypeError(f"Malformed MCP configuration: {path}")
    servers = data.setdefault("mcpServers", {})
    current = servers.get("rea")
    if current is not None:
        if not isinstance(current, dict) or current.get("command") != entry["command"] or current.get("args") != entry["args"]:
            raise ValueError(f"Preserve conflicting REA registration: {path}")
        updated = dict(current)
        updated.update(entry)
        updated["env"] = {**current.get("env", {}), **entry.get("env", {})}
    else:
        updated = entry
    if verify:
        if current != updated:
            raise ValueError(f"Missing or stale REA registration: {path}")
        return
    servers["rea"] = updated
    if original is not None and data == json.loads(original):
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if original is not None:
        backup = path.with_name(path.name + ".before-agent-skills")
        if not backup.exists():
            backup.write_text(original)
            backup.chmod(0o600)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(data, stream, indent=2)
        stream.write("\n")
    temporary.replace(path)


def configure_mcp(command, user, environment, verify=False):
    entry = {"command": str(command), "args": ["mcp"], "env": {
        "REA_MCP_INPUT_SCHEMA_PROFILE": "compact", "REA_MCP_OUTPUT_SCHEMA_PROFILE": "off"}}
    claude_config = Path(environment.get("CLAUDE_CONFIG_DIR") or user) / ".claude.json"
    merge_mcp(claude_config, {"type": "stdio", **entry}, verify)
    merge_mcp(user / ".gemini/config/mcp_config.json", {**entry, "timeoutSeconds": 600}, verify)
    legacy = user / ".gemini/antigravity/mcp_config.json"
    if legacy.exists():
        merge_mcp(legacy, {**entry, "timeoutSeconds": 600}, verify)
    codex = shutil.which("codex")
    if codex:
        config = Path(environment.get("CODEX_HOME") or user / ".codex") / "config.toml"
        data = tomllib.loads(config.read_text()) if config.exists() else {}
        current = data.get("mcp_servers", {}).get("rea")
        aligned = current and current.get("command") == entry["command"] and current.get("args") == entry["args"] and all(current.get("env", {}).get(k) == v for k, v in entry["env"].items())
        if verify and not aligned:
            raise ValueError("Codex global REA registration is missing or stale")
        if not verify and not aligned:
            if current:
                raise ValueError("Preserve conflicting Codex REA registration")
            run([codex, "mcp", "add", "rea", "--env", "REA_MCP_INPUT_SCHEMA_PROFILE=compact",
                 "--env", "REA_MCP_OUTPUT_SCHEMA_PROFILE=off", "--", str(command), "mcp"])
    return ["claude-code", "antigravity"] + (["codex"] if codex else [])


def configure_project_mcp(project, command, verify=False):
    entry = {"command": str(command), "args": ["mcp"], "env": {
        "REA_MCP_INPUT_SCHEMA_PROFILE": "compact", "REA_MCP_OUTPUT_SCHEMA_PROFILE": "off"}}
    merge_mcp(project / ".mcp.json", {"type": "stdio", **entry}, verify)
    merge_mcp(project / ".agents/mcp_config.json", {**entry, "timeoutSeconds": 600}, verify)


def install_commands(cache, node):
    if cache.is_relative_to(HERE):
        raise ValueError("Shared cache must be outside the setup source directory")
    identities = [recipe.digest(HERE / name) for name in (
        "setup.py", "install.py", "skills-lock.json", "harnesses.json",
        "skills-package.json", "skills-package-lock.json")]
    version = hashlib.sha256("\n".join(identities).encode()).hexdigest()
    bootstrap = cache / "bootstraps" / version
    if not bootstrap.exists():
        shutil.copytree(HERE, bootstrap, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    directory = cache / "bin"
    directory.mkdir(parents=True, exist_ok=True)
    commands = {
        "skills-setup": [sys.executable, str(bootstrap / "setup.py"), "--global", "--all-harnesses", "--cache", str(cache)],
        "skills": [node, str(cache / "cli/node_modules/skills/bin/cli.mjs")],
    }
    for name, arguments in commands.items():
        path = directory / name
        path.write_text("#!/bin/sh\nexec " + " ".join(shlex.quote(x) for x in arguments) + ' "$@"\n')
        path.chmod(0o755)
    return str(directory / "skills-setup")


def setup(cache, download=False, verify=False, rea_command=None, projects=()):
    user = Path.home()
    lock_path = HERE / "skills-lock.json"
    lock = json.loads(lock_path.read_text())
    registry = json.loads((HERE / "harnesses.json").read_text())
    expected = {x["name"]: x["tree_sha256"] for x in recipe.all_skills(lock)}
    destinations = roots(registry, user, os.environ)
    canonical = user / ".agents/skills"
    receipt_path = cache / "setup-receipt.json"
    old_receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
    command = rea_command or old_receipt.get("rea_command") or shutil.which("rea")
    if command and not Path(command).is_file():
        raise ValueError(f"REA launcher not found: {command}")
    for project in projects:
        if not project.is_dir():
            raise ValueError(f"Project does not exist: {project}")
        destinations[str(project / ".agents/skills")] = project / ".agents/skills"
        destinations[str(project / ".claude/skills")] = project / ".claude/skills"
        for harness in registry["harnesses"]:
            if harness["global"] is None:
                destination = project / recipe.relative(harness["project"])
                destinations[str(destination)] = destination
    if verify:
        if old_receipt.get("lock_sha256") != recipe.digest(lock_path):
            raise ValueError("Shared setup receipt is missing or references a different skill lock")
        if recipe.tree_digest(cache / "cli/node_modules/skills") != registry["cli_tree_sha256"]:
            raise ValueError("Skills CLI package identity mismatch")
        ensure_registrations(expected, expected, destinations, canonical, True)
        clients = configure_mcp(command, user, os.environ, True) if command else []
        if command:
            for project in projects:
                configure_project_mcp(project, command, True)
        return {"status": "verified", "skills": len(expected), "global_harnesses": len([x for x in registry["harnesses"] if x["global"]]), "mcp_clients": clients}
    node, npm = shutil.which("node"), shutil.which("npm")
    if not node or not npm:
        raise ValueError("Node.js >=22.20 and npm are required for the pinned skills CLI")
    prefix = cache / "cli"
    cli = prefix / "node_modules/skills/bin/cli.mjs"
    if not cli.exists():
        if not download:
            raise ValueError("Missing skills CLI; run setup with --download in preparation")
        prefix.mkdir(parents=True, exist_ok=True)
        shutil.copy2(HERE / "skills-package.json", prefix / "package.json")
        shutil.copy2(HERE / "skills-package-lock.json", prefix / "package-lock.json")
        run([npm, "ci", "--prefix", str(prefix), "--ignore-scripts", "--no-fund", "--no-audit"])
    version = json.loads((prefix / "node_modules/skills/package.json").read_text())["version"]
    if version != registry["skills_cli_version"]:
        raise ValueError("Skills CLI and reviewed harness registry versions differ")
    if recipe.tree_digest(prefix / "node_modules/skills") != registry["cli_tree_sha256"]:
        raise ValueError("Skills CLI package identity mismatch")
    prepared = recipe.install(lock_path, cache / "sources", cache / "catalog", download)
    source = Path(prepared["generation"]) / "skills"
    # The official CLI replaces by name. Refuse foreign content before invoking it.
    ensure_registrations(expected, expected, destinations, canonical)
    environment = {**os.environ, "DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1"}
    global_agents = [x["id"] for x in registry["harnesses"] if x["global"]]
    results = json.loads(run([node, str(cli), "add", str(source), "--global", "--skill", "*",
                              "--agent", *global_agents, "--yes", "--json"], env=environment))
    if {x.get("name") for x in results if x.get("status") == "installed"} != set(expected):
        raise ValueError("Skills CLI did not report the complete pinned selection")
    ensure_registrations(expected, expected, destinations, canonical, publish=True)
    clients = configure_mcp(command, user, os.environ) if command else []
    if command:
        for project in projects:
            configure_project_mcp(project, command)
    cache.mkdir(parents=True, exist_ok=True)
    receipt = {"lock_sha256": recipe.digest(lock_path), "cli_version": version,
               "rea_command": str(command) if command else None,
               "skills": len(expected), "global_harnesses": len([x for x in registry["harnesses"] if x["global"]]),
               "projects": [str(p) for p in projects], "setup_command": install_commands(cache, node)}
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    ensure_registrations(expected, expected, destinations, canonical, True)
    return {"status": "installed", "skills": len(expected), "global_harnesses": receipt["global_harnesses"], "mcp_clients": clients, "setup_command": receipt["setup_command"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--global", dest="global_scope", action="store_true", required=True)
    parser.add_argument("--all-harnesses", action="store_true", required=True)
    parser.add_argument("--cache", type=Path, default=Path(os.environ.get("AGENT_SKILLS_CACHE") or Path.home() / ".local/share/agent-skills"))
    parser.add_argument("--project", type=Path, action="append", default=[])
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--rea-command", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(setup(args.cache.resolve(), args.download, args.verify, args.rea_command, [p.resolve() for p in args.project]), sort_keys=True))
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as error:
        parser.exit(1, f"Shared skill setup failed: {error}\n")


if __name__ == "__main__":
    main()
