#!/usr/bin/env python3
"""Build and validate the planning catalogue. This never certifies gameplay."""
import argparse
import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = "elgansayer/Neptune-Bomberman"
URL = f"https://github.com/{REPO}"
GROUPS = {
    "REF": "Reference research and exhaustive inventories",
    "SIM": "Authoritative simulation",
    "BOMB": "Bomb mechanics",
    "ITEM": "Items, abilities and illnesses",
    "MOUNT": "Mounts and companions",
    "ARENA": "Maps, terrain and stage mechanisms",
    "BATTLE": "Battle modes and rules",
    "SATURN": "Saturn campaign, Master and presentation",
    "POWER": "Power-inspired profiles and modes",
    "BOT": "Competitive bots, companions and enemies",
    "ROOM": "Rooms, parties and mixed participants",
    "NET": "Browser/native networking and cross-play",
    "PACK": "Portable community content platform",
    "EFFECT": "Custom power-up and effect system",
    "STORY": "Creator-authored solo campaigns",
    "COOP": "Local and online co-op stories",
    "EDITOR": "Creation tools",
    "WORKSHOP": "Sharing, discovery and creator services",
    "SOCIAL": "Community and tournaments",
    "STATS": "Identity, progression and trusted statistics",
    "UX": "Controls, onboarding and accessibility",
    "MEDIA": "Rendering, animation, sound and original assets",
    "REPLAY": "Replays, spectating and broadcast",
    "FACTORY": "Continuous implementation and merge automation",
    "OPS": "Packaging, hosting and operations",
    "EXP": "Optional original modes and experiments",
}

# Existing issues remain the source of their original scope and history.
REUSE = {"BATTLE-003": 44, "BOT-018": 32, "ROOM-003": 31,
         "NET-010": 45, "EFFECT-007": 52, "COOP-004": 54,
         "WORKSHOP-016": 57}

# These are concrete deliverable dependencies, not entire parent epics.
# Phase is a suggested delivery wave; dependencies always take precedence.
BASE_DEPS = {
    "REF": [], "SIM": ["SIM-001"], "BOMB": ["SIM-004", "SIM-006"],
    "ITEM": ["SIM-003", "SIM-009"], "MOUNT": ["SIM-006", "SIM-010"],
    "ARENA": ["SIM-006"], "BATTLE": ["SIM-011", "SIM-012"],
    "SATURN": ["REF-001", "STORY-001"], "POWER": ["REF-007", "BATTLE-001"],
    "BOT": ["BOT-001"], "ROOM": ["ROOM-001"], "NET": ["SIM-015"],
    "PACK": ["PACK-001"], "EFFECT": ["EFFECT-001"],
    "STORY": ["PACK-013"], "COOP": ["COOP-001", "STORY-001"],
    "EDITOR": ["PACK-017"], "WORKSHOP": ["WORKSHOP-001"],
    "SOCIAL": ["SOCIAL-001"], "STATS": ["STATS-001", "STATS-002"],
    "UX": [], "MEDIA": ["PACK-001"], "REPLAY": ["REPLAY-001"],
    "FACTORY": ["FACTORY-001"], "OPS": [],
    "EXP": ["PACK-012", "BOT-014"],
}
DEPS = {
    "REF-002": ["REF-001"], "REF-003": ["REF-001"], "REF-004": ["REF-001"],
    "REF-005": ["REF-001"], "REF-006": ["REF-001"], "REF-008": ["REF-007"],
    "REF-009": ["REF-007"], "REF-010": ["REF-007"],
    "REF-011": ["REF-005", "REF-008"], "REF-014": ["REF-013"],
    "SIM-001": [], "SIM-004": ["SIM-001", "SIM-006"],
    "SIM-009": ["SIM-003", "SIM-008"], "SIM-010": ["SIM-009"],
    "SIM-012": ["SIM-003", "SIM-009"], "SIM-013": ["SIM-002", "SIM-008"],
    "BOMB-003": ["BOMB-001", "BOMB-002", "BOMB-004"],
    "BOMB-007": ["BOMB-006"], "BOMB-008": ["BOMB-007", "ARENA-016"],
    "BOMB-013": ["REF-008"], "BOMB-015": ["REF-008", "BOMB-003"],
    "BOMB-018": ["BOMB-003", "BOMB-005", "BOMB-006"],
    "ITEM-002": ["BOMB-001"], "ITEM-003": ["BOMB-004", "NET-005"],
    "ITEM-009": ["ITEM-008", "BOMB-002"], "ITEM-010": ["ITEM-008", "BOMB-001"],
    "ITEM-011": ["ITEM-008", "SIM-005"], "ITEM-012": ["ITEM-008", "ITEM-002", "ITEM-003"],
    "MOUNT-002": ["MOUNT-001"], "MOUNT-003": ["MOUNT-002", "BOMB-007"],
    "MOUNT-004": ["MOUNT-002"], "MOUNT-005": ["MOUNT-002"],
    "MOUNT-006": ["MOUNT-002"], "MOUNT-007": ["MOUNT-002"],
    "MOUNT-008": ["MOUNT-001", "SIM-010"], "MOUNT-009": ["REF-007"],
    "MOUNT-010": ["MOUNT-001", "PACK-007", "EFFECT-001"],
    "ARENA-017": ["ARENA-001", "PACK-010"],
    "ARENA-018": ["ARENA-019", "SIM-002"],
    "BATTLE-003": ["SIM-012", "ARENA-001"],
    "BATTLE-008": ["BOMB-007", "SIM-009"],
    "BATTLE-010": ["BATTLE-001", "BATTLE-011"],
    "SATURN-005": ["REF-002", "REF-003", "STORY-007"],
    "SATURN-006": ["REF-003", "STORY-008"],
    "SATURN-007": ["REF-002", "STORY-005"],
    "SATURN-008": ["REF-002", "STORY-001"],
    "SATURN-014": ["REF-001", "BOT-001", "BOT-010"],
    "BOT-001": ["SIM-004", "SIM-006"],
    "BOT-002": ["BOT-001", "BOMB-003"],
    "BOT-003": ["BOT-002", "SIM-005"],
    "BOT-004": ["BOT-003"], "BOT-005": ["BOT-003"],
    "BOT-006": ["BOT-003"], "BOT-007": ["BOT-004"],
    "BOT-008": ["BOT-004", "BOMB-005", "BOMB-007", "BOMB-009"],
    "BOT-009": ["BOT-003", "MOUNT-001", "ARENA-008"],
    "BOT-014": ["BOT-001", "PACK-012"],
    "BOT-018": ["BOT-017", "REPLAY-002"],
    "ROOM-001": ["SIM-007", "SIM-015"],
    "ROOM-003": ["ROOM-001", "BOT-001"],
    "ROOM-006": ["ROOM-001", "PACK-005"],
    "ROOM-009": ["ROOM-008", "BOT-001"],
    "ROOM-010": ["REPLAY-006"], "ROOM-014": ["ROOM-004", "SOCIAL-003"],
    "ROOM-015": ["ROOM-008", "COOP-005"],
    "NET-003": ["NET-002", "SIM-005"], "NET-004": ["NET-005", "NET-006"],
    "NET-005": ["SIM-013", "SIM-015"], "NET-007": ["NET-003", "NET-010"],
    "NET-008": ["NET-005", "ROOM-008"], "NET-010": ["NET-001", "NET-003"],
    "NET-013": ["SIM-013", "NET-001"],
    "PACK-001": [], "PACK-003": ["PACK-002", "PACK-004"],
    "PACK-005": ["PACK-001", "PACK-002"],
    "PACK-007": ["PACK-006"], "PACK-008": ["PACK-007"],
    "PACK-009": ["PACK-007", "PACK-012"],
    "PACK-010": ["PACK-006", "ARENA-001"],
    "PACK-011": ["EFFECT-001", "PACK-006"],
    "PACK-012": ["PACK-006", "SIM-012"], "PACK-013": ["PACK-006"],
    "PACK-014": ["PACK-002", "PACK-003", "SIM-015"],
    "PACK-016": ["PACK-007", "PACK-010", "PACK-011", "PACK-012"],
    "PACK-017": ["PACK-001", "PACK-006"],
    "EFFECT-001": ["PACK-001", "SIM-003", "SIM-014"],
    "EFFECT-007": ["EFFECT-002", "EFFECT-003", "EFFECT-010"],
    "EFFECT-010": ["EFFECT-001", "BOT-002"],
    "EFFECT-014": ["EFFECT-011", "NET-013"],
    "STORY-003": ["STORY-001", "STORY-002"],
    "STORY-004": ["STORY-002"], "STORY-006": ["STORY-003", "STORY-004"],
    "STORY-008": ["STORY-007", "EFFECT-001"],
    "STORY-010": ["STORY-001", "SIM-013", "SIM-015"],
    "STORY-015": ["STORY-010"], "STORY-016": ["STORY-001", "STORY-007", "SIM-002"],
    "STORY-018": ["STORY-003", "STORY-008", "STORY-009", "COOP-004"],
    "COOP-001": ["PACK-013", "STORY-001"],
    "COOP-002": ["COOP-001", "ROOM-002", "NET-001"],
    "COOP-004": ["COOP-001", "STORY-010", "NET-008"],
    "COOP-005": ["COOP-001", "ROOM-008"],
    "COOP-008": ["COOP-001", "STORY-004"],
    "COOP-009": ["COOP-001", "STORY-009", "BOT-012"],
    "COOP-010": ["COOP-005", "ROOM-009"],
    "COOP-012": ["COOP-002", "COOP-004", "COOP-009"],
    "EDITOR-001": ["PACK-010", "PACK-017"],
    "EDITOR-004": ["EDITOR-001", "BOT-001"],
    "EDITOR-005": ["PACK-007", "PACK-017"],
    "EDITOR-006": ["EFFECT-001", "PACK-017"],
    "EDITOR-007": ["PACK-012", "PACK-017"],
    "EDITOR-008": ["STORY-001", "PACK-017"],
    "EDITOR-009": ["STORY-004", "PACK-017"],
    "EDITOR-010": ["STORY-008", "PACK-017"],
    "EDITOR-011": ["COOP-009", "EDITOR-008"],
    "WORKSHOP-001": ["PACK-003", "PACK-017", "SOCIAL-001"],
    "WORKSHOP-004": ["WORKSHOP-001", "PACK-014"],
    "WORKSHOP-005": ["WORKSHOP-001", "PACK-003"],
    "WORKSHOP-009": ["WORKSHOP-007", "PACK-014"],
    "WORKSHOP-016": ["EDITOR-017", "WORKSHOP-002", "WORKSHOP-005", "COOP-012", "EFFECT-007"],
    "SOCIAL-001": [], "SOCIAL-003": ["SOCIAL-001", "ROOM-001"],
    "SOCIAL-008": ["SOCIAL-001", "STATS-002"],
    "SOCIAL-009": ["SOCIAL-008", "STATS-003"],
    "STATS-001": ["SIM-009", "SIM-012"],
    "STATS-002": ["STATS-001", "SOCIAL-001"],
    "STATS-004": ["STATS-002", "STATS-003"],
    "STATS-005": ["STATS-004", "ROOM-014"],
    "STATS-008": ["STATS-002", "REPLAY-002"],
    "UX-001": ["ROOM-004"], "UX-013": ["UX-002", "PACK-005"],
    "UX-014": ["PACK-005"],
    "MEDIA-002": ["PACK-007"], "MEDIA-003": ["SIM-001"],
    "MEDIA-004": ["PACK-007", "MOUNT-001"], "MEDIA-012": ["PACK-016", "PACK-018"],
    "REPLAY-001": ["SIM-002", "SIM-013", "PACK-002"],
    "REPLAY-002": ["REPLAY-001"], "REPLAY-003": ["REPLAY-002"],
    "REPLAY-006": ["NET-005"], "REPLAY-007": ["REPLAY-006", "SOCIAL-009"],
    "REPLAY-009": ["REPLAY-002", "STORY-010"],
    "FACTORY-001": [], "FACTORY-003": ["FACTORY-001", "FACTORY-002"],
    "FACTORY-006": ["FACTORY-005"], "FACTORY-007": ["FACTORY-006", "NET-001", "COOP-012"],
    "FACTORY-008": ["FACTORY-006"], "FACTORY-009": ["FACTORY-004", "FACTORY-008"],
    "FACTORY-010": ["FACTORY-008", "FACTORY-012"],
    "FACTORY-013": ["FACTORY-002", "FACTORY-012"],
    "FACTORY-016": ["FACTORY-001", "FACTORY-012"],
    "OPS-003": ["OPS-001", "OPS-002"], "OPS-005": ["OPS-003", "STATS-001"],
    "OPS-006": ["OPS-002"], "OPS-007": ["OPS-001", "BOT-016"],
    "OPS-008": ["OPS-001", "SIM-015"], "OPS-010": ["NET-001", "PACK-003"],
    "EXP-001": ["STORY-007", "COOP-011"], "EXP-002": ["STORY-016", "STORY-010"],
    "EXP-003": ["STORY-003", "REPLAY-002"], "EXP-004": ["PACK-009", "EFFECT-009"],
    "EXP-005": ["STORY-008", "COOP-011"],
    "EXP-008": ["WORKSHOP-011", "STATS-008"],
    "EXP-009": ["WORKSHOP-011", "SOCIAL-010"],
    "EXP-010": ["ROOM-001", "OPS-007", "NET-011"],
}

INTEGRATION = {
    "REF": "Deliver a pinned source manifest, bounded measurement/capture procedure, evidence paths, uncertainty and reproducible comparison. Metadata validation is not gameplay proof.",
    "BOT": "Use the production simulation and public observations. Include seeded adversarial scenarios, failure traces, CPU bounds and the existing native suite. Never weaken survival assertions to accept a policy.",
    "NET": "Exercise actual supported native and browser clients against the authoritative server. Record RTT/loss/jitter, versions and exact content locks. Local serialisation tests alone do not prove cross-play.",
    "PACK": "Validate one permitted original fixture and malformed/incompatible inputs. Exercise runtime loading, offline installation and compatibility diagnostics; no downloaded executable scripts.",
    "EFFECT": "Run the effect through authoritative gameplay, replay/state restore and bot forecast fixtures. Test malformed graphs and bounded execution; presentation must not decide damage.",
    "STORY": "Provide an original playable pack, deterministic objective/transition tests and save/restore coverage. State which party sizes and entry paths were actually exercised.",
    "COOP": "Exercise two actual clients or local seats, companion participation where supported, and disconnect/checkpoint boundaries. Compare authoritative party and world state after recovery.",
    "EDITOR": "Create, export, validate and play an original fixture through public pack APIs. Check undo/reload and source-field diagnostics; editor-only previews do not prove runtime compatibility.",
    "WORKSHOP": "Exercise submit-to-install using immutable pack versions, dependency failure and permission boundaries. Keep tests isolated from real community records and preserve permitted source/provenance.",
    "FACTORY": "Demonstrate bounded successful, failing, interrupted and recovered runs with exact head/base identities. A workflow file or a model completion message is not evidence that automation is running.",
    "OPS": "Use an isolated environment and reproducible commands. Record actual resource limits, exit codes and recovery evidence; separate a tested package from a deployed production service.",
    "UX": "Exercise representative keyboard, controller and supported browser layouts. Preserve server rules and provide accessible errors. Report device/platform coverage rather than claiming universal support.",
    "EXP": "Ship a bounded original playable prototype and measured evaluation. This is optional P3 work, not a prerequisite for multiplayer/bot/modding milestones; promote only after an explicit product decision.",
}
DEFAULT_INTEGRATION = "Use production paths with a permitted original fixture. Add focused regression tests for normal, boundary and failure cases, then run applicable existing native/network/pack checks. Record versions, seeds, commands and evidence; never weaken reference tolerances to obtain a pass."


def read_features():
    result = []
    counts = collections.Counter()
    context = None
    for line_no, line in enumerate((ROOT / "features.tsv").read_text().splitlines(), 1):
        if not line or line.startswith("#"):
            continue
        if line.startswith("@"):
            group, priority, phase, parent, provenance = line[1:].split("|")
            context = (group, priority, int(phase), int(parent), provenance)
            continue
        if context is None or line.count("|") != 1:
            raise ValueError(f"Malformed row {line_no}")
        title, acceptance = line.split("|")
        group, priority, phase, parent, provenance = context
        counts[group] += 1
        fid = f"{group}-{counts[group]:03d}"
        criteria = [x.strip().removesuffix(".") for x in acceptance.split(";")]
        if len(criteria) < 2 or not all(criteria):
            raise ValueError(f"Insufficient concrete acceptance criteria for {fid}")
        if fid in ("EFFECT-014", "NET-007"):
            priority, phase = "P3", 6
        deps = DEPS.get(fid, BASE_DEPS[group])
        result.append(dict(id=fid, domain=group, domain_name=GROUPS[group],
                           priority=priority, phase=phase, parent_issue=parent,
                           provenance=provenance, title=title, acceptance=criteria,
                           depends_on=deps, existing_issue=REUSE.get(fid),
                           implementation_status="needs-code-and-evidence-audit"))
    if set(counts) != set(GROUPS):
        raise ValueError("Missing or unexpected domains")
    ids = {x["id"] for x in result}
    titles = [x["title"].casefold() for x in result]
    if len(ids) != len(result) or len(set(titles)) != len(titles):
        raise ValueError("Duplicate feature ID or title")
    if set(DEPS) - ids or set(REUSE) - ids:
        raise ValueError("Configuration references unknown features")
    for feature in result:
        if set(feature["depends_on"]) - ids or feature["id"] in feature["depends_on"]:
            raise ValueError(f"Invalid dependency for {feature['id']}")
    # Stable Kahn ordering: this is also a safe issue publication order.
    pending = {x["id"]: x for x in result}
    ordered = []
    done = set()
    while pending:
        ready = [x for x in pending.values() if set(x["depends_on"]) <= done]
        if not ready:
            raise ValueError(f"Dependency cycle involving {sorted(pending)}")
        ready.sort(key=lambda x: (x["phase"], x["priority"], x["id"]))
        chosen = ready[0]
        ordered.append(chosen)
        done.add(chosen["id"])
        del pending[chosen["id"]]
    return result, ordered


def issue_body(feature, numbers):
    deps = feature["depends_on"]
    links = [f"{d} (#{numbers[d]})" if d in numbers else d for d in deps]
    readiness = ", ".join(links) or "No new catalogue prerequisite; audit the current baseline and applicable existing issues first."
    source = feature["provenance"]
    reference = ""
    if source in ("reference-candidate", "reference-research") or feature["domain"] in ("POWER", "SATURN"):
        reference = "\nReference semantics must be measured against a pinned release before a fidelity claim. This title is a research/implementation target, not proof that every named behaviour exists in every reference. An original Neptune fixture may proceed independently and must be labelled as such. See [source and confidence policy](" + URL + "/blob/roadmap/comprehensive-feature-backlog/docs/restart/backlog/README.md#reference-evidence).\n"
    elif source == "neptune-experiment":
        reference = "\nThis is an optional original Neptune experiment, not a Saturn or Power parity claim.\n"
    else:
        reference = "\nThis is a proposed Neptune product/platform requirement, not a claim about a reference game's implementation.\n"
    criteria = "\n".join(f"- [ ] {x}." for x in feature["acceptance"])
    return f"""<!-- neptune-feature:{feature['id']} -->
Feature ID: **{feature['id']}** · {feature['priority']} · delivery wave {feature['phase']} · provenance: `{source}`

Roadmap: #69 · existing coordination parent: #{feature['parent_issue']}. The parent is a grouping issue, not an instruction to wait for the entire epic.

## Outcome

{feature['title']}.
{reference}
## Prerequisites and scope

{readiness}

Audit current code, open PRs and linked evidence before implementing. Reuse working components. If these criteria are already satisfied, link exact evidence and close this issue instead of rebuilding. Dependency completion means the needed contract is demonstrated, not merely that an issue is closed. Keep the first change bounded; split independently testable follow-ups while retaining this feature ID and dependencies. Never silently expand an active worker's task.

## Acceptance

{criteria}

## Verification and handoff

{INTEGRATION.get(feature['domain'], DEFAULT_INTEGRATION)}

Link the implementation PR and exact-head/current-base test evidence. Missing, empty, skipped or failed applicable checks are not success. Follow `AGENTS.md` and `docs/restart/MERGE_POLICY.md`; no mandatory AI/human approval is added. Creating this issue does not authorise unlimited provider spend, production deployment or concurrency.
"""


def render_index(features, numbers):
    lines = ["# Feature issue index", "", f"Master roadmap: [#69]({URL}/issues/69). {len(features)} bounded feature specifications across {len(GROUPS)} domains.", "", "This is a planning index, not a completion report. Dependency edges in `catalogue.json` take precedence over suggested waves. Existing issues are reused where their scope matches.", ""]
    for group, name in GROUPS.items():
        lines.extend([f"## {group}: {name}", "", "| ID | Priority / wave | Feature | GitHub |", "| --- | --- | --- | --- |"])
        for f in features:
            if f["domain"] != group:
                continue
            n = numbers.get(f["id"])
            link = f"[#{n}]({URL}/issues/{n})" if n else "Pending publication"
            lines.append(f"| {f['id']} | {f['priority']} / {f['phase']} | {f['title']} | {link} |")
        lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    features, ordered = read_features()
    journal_path = ROOT / "issue-links.json"
    numbers = json.loads(journal_path.read_text()) if journal_path.exists() else dict(REUSE)
    if set(numbers) - {x["id"] for x in features}:
        raise ValueError("Journal contains unknown IDs")
    for fid, n in REUSE.items():
        if numbers.get(fid, n) != n:
            raise ValueError(f"Existing issue remapped: {fid}")
        numbers[fid] = n
    if len(set(numbers.values())) != len(numbers):
        raise ValueError("Two features linked to the same issue")
    if any(type(n) is not int or n <= 0 for n in numbers.values()):
        raise ValueError("Invalid issue number")
    for feature in features:
        if feature["id"] in numbers:
            feature["issue_number"] = numbers[feature["id"]]
            feature["issue_url"] = f"{URL}/issues/{feature['issue_number']}"
    catalog = dict(schema_version=1, repository=REPO, roadmap_issue=69,
                   status_note="Planning metadata only; no gameplay completion is certified.",
                   features=features, publication_order=[x["id"] for x in ordered])
    content = json.dumps(catalog, indent=2, ensure_ascii=False) + "\n"
    target = ROOT / "catalogue.json"
    index_content = render_index(features, numbers)
    if args.check:
        if not target.exists() or target.read_text() != content:
            raise ValueError("catalogue.json is stale; run build_catalogue.py")
        if len(numbers) != len(features):
            raise ValueError("Not all features have published or reused issue links")
        if not (ROOT / "INDEX.md").exists() or (ROOT / "INDEX.md").read_text() != index_content:
            raise ValueError("INDEX.md is stale; run build_catalogue.py")
    else:
        target.write_text(content)
        journal_path.write_text(json.dumps(numbers, indent=2, sort_keys=True) + "\n")
        payloads = [dict(id=x["id"], existing_issue=x["existing_issue"],
                         title=f"[{x['priority']}][{x['id']}] {x['title']}",
                         body=issue_body(x, numbers)) for x in ordered]
        (ROOT / "issue-payloads.json").write_text(json.dumps(payloads, indent=2, ensure_ascii=False) + "\n")
        (ROOT / "INDEX.md").write_text(index_content)
    counts = collections.Counter(x["domain"] for x in features)
    print(json.dumps(dict(features=len(features), domains=len(counts), reused=len(REUSE),
                          linked=len(numbers), unpublished=len(features)-len(numbers),
                          dependency_edges=sum(len(x["depends_on"]) for x in features),
                          cycles=0, duplicate_ids=0, duplicate_titles=0, per_domain=dict(counts))))


if __name__ == "__main__":
    main()
