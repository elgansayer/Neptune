#!/usr/bin/env python3
"""Compare a Neptune SH-2 inventory with the pinned upstream discovery on the same bytes.

The upstream implementation (saturn-recomp ``recomp/discover.py``) is loaded only
after its exact source hashes match, in the same way ``probe_kernel.py`` loads
the pinned interpreter. Both tools are static: agreement is cross-implementation
consistency, not runtime proof, and neither result is used as the other's oracle.
No game bytes or upstream code are stored in this repository.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import types

import sh2_discover as neptune

SCHEMA = "neptune.sh2-discovery-comparison.v1"
UPSTREAM_REVISION = "f20de940e8013fc84103a5b39c4069ed8071b1f9"
UPSTREAM_SOURCES = {
    "hw.py": "a0a1e036358474b41fd594a1dd2fae9024e3e63059682367aca57eac257d231d",
    "sh2.py": "0add78272f1ee398881fbca2850d8d89b4cbd5a7767448299b39498f60d703dd",
    "recomp/discover.py": "359e5bfbdbe62434a2f0b026a76c6677d528d52e681de59a8297a39b607b7406",
}
LIMIT = 1 << 20


def _read(path: Path, limit: int) -> bytes:
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Input exceeds its size bound: " + path.name)
    return data


def load_upstream(root: Path, sources: dict | None = None):
    """Verify every pinned source, then execute exactly those bytes as a private package."""
    sources = UPSTREAM_SOURCES if sources is None else sources
    content = {}
    for name, expected in sources.items():
        data = _read(root / "src" / "saturnrecomp" / name, LIMIT)
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError("Upstream source mismatch: " + name)
        content[name] = data
    package_name = "_neptune_pinned_recomp"
    names = [package_name, package_name + ".hw", package_name + ".sh2",
             package_name + ".recomp", package_name + ".recomp.discover"]
    previous = {name: sys.modules.get(name) for name in names}
    try:
        package = types.ModuleType(package_name)
        package.__path__ = []
        sys.modules[package_name] = package
        for short in ("hw", "sh2"):
            module = types.ModuleType(package_name + "." + short)
            module.__package__ = package_name
            sys.modules[module.__name__] = module
            setattr(package, short, module)
            exec(compile(content[short + ".py"], "pinned-saturn-recomp/" + short + ".py", "exec"), module.__dict__)
        sub = types.ModuleType(package_name + ".recomp")
        sub.__path__ = []
        sub.__package__ = package_name + ".recomp"
        sys.modules[sub.__name__] = sub
        package.recomp = sub
        discover = types.ModuleType(package_name + ".recomp.discover")
        discover.__package__ = package_name + ".recomp"
        sys.modules[discover.__name__] = discover
        sub.discover = discover
        exec(compile(content["recomp/discover.py"], "pinned-saturn-recomp/recomp/discover.py", "exec"),
             discover.__dict__)
        return package.sh2, discover
    finally:
        for name, old in previous.items():
            if old is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old


def compare(data: bytes, base: int, seeds: list[int], inventory: dict, sh2, discover) -> dict:
    if inventory.get("schema") != neptune.SCHEMA:
        raise ValueError("Not a Neptune SH-2 inventory")
    if inventory["identity"]["source_sha256"] != hashlib.sha256(data).hexdigest():
        raise ValueError("Inventory describes different module bytes")
    if int(inventory["identity"]["base"], 16) != base:
        raise ValueError("Inventory describes a different load base")
    program = discover.Program(sh2.Image(data, base), list(seeds))
    upstream = set(program.funcs)
    replay = neptune.replay(neptune.Module(data, base), inventory)
    ours = {int(row["entry"], 16): row["tier"] for row in inventory["functions"]}
    only_upstream: dict[str, int] = {}
    for address in upstream - set(ours):
        kind = neptune.classify(replay, address)
        only_upstream[kind] = only_upstream.get(kind, 0) + 1
    only_ours: dict[str, int] = {}
    for address in set(ours) - upstream:
        kind = "upstream-code" if address in program.code else "upstream-data" if address in program.data else "upstream-unclassified"
        key = "tier-" + ours[address] + ":" + kind
        only_ours[key] = only_ours.get(key, 0) + 1
    by_tier = {t: {"neptune": sum(1 for v in ours.values() if v == t),
                   "also_upstream": sum(1 for a, v in ours.items() if v == t and a in upstream)} for t in "ABC"}
    neptune_code = set(replay.code)
    neptune_data = {a for a in set(replay.literal) | set(replay.table) if a not in neptune_code}
    halfwords = {
        "both_code": len(neptune_code & program.code),
        "neptune_code_upstream_data": len(neptune_code & program.data),
        "neptune_data_upstream_code": len(neptune_data & program.code),
        "both_data": len(neptune_data & program.data),
        "neptune_code_upstream_unclassified": len(neptune_code - program.code - program.data),
        "upstream_code_neptune_unclassified": len(program.code - neptune_code - neptune_data),
    }
    return {
        "schema": SCHEMA,
        "source_sha256": hashlib.sha256(data).hexdigest(), "base": neptune.h32(base),
        "seeds": [neptune.h32(s) for s in seeds],
        "neptune": {"inventory_entry_list_sha256": inventory["entry_list_sha256"],
                    "tool_sha256": inventory["identity"]["tool_sha256"], "functions": len(ours)},
        "upstream": {"revision": UPSTREAM_REVISION, "sources": UPSTREAM_SOURCES,
                     "summary": {k: int(v) for k, v in program.summary().items()},
                     "entry_list_sha256": hashlib.sha256("\n".join(neptune.h32(a) for a in sorted(upstream)).encode()).hexdigest()},
        "entries": {"both": len(upstream & set(ours)), "only_upstream": len(upstream - set(ours)),
                    "only_neptune": len(set(ours) - upstream), "by_neptune_tier": by_tier,
                    "only_upstream_by_neptune_class": dict(sorted(only_upstream.items())),
                    "only_neptune_by_upstream_class": dict(sorted(only_ours.items()))},
        "halfwords": halfwords,
        "only_upstream_entries": [neptune.h32(a) for a in sorted(upstream - set(ours))],
        "only_neptune_entries": [neptune.h32(a) for a in sorted(set(ours) - upstream)],
        "limitations": ["Both discoveries are static and share no runtime evidence",
                        "Agreement does not validate semantics, callers or residency",
                        "Disagreements are classified, not resolved by preferring either tool"],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--module", type=Path, required=True)
    parser.add_argument("--base", type=lambda text: int(text, 16), required=True)
    parser.add_argument("--seed", type=lambda text: int(text, 16), action="append", required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--saturn-recomp", type=Path, required=True, help="pinned checkout; never fetched")
    parser.add_argument("--report", type=Path, required=True, help="new private JSON report")
    args = parser.parse_args(argv)
    data = _read(args.module, neptune.MAX_MODULE)
    with args.inventory.open(encoding="utf-8") as stream:
        inventory = json.load(stream)
    sh2, discover = load_upstream(args.saturn_recomp)
    report = compare(data, args.base, args.seed, inventory, sh2, discover)
    report["tool_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with args.report.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(report, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"entries": report["entries"], "halfwords": report["halfwords"],
                      "upstream": report["upstream"]["summary"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
