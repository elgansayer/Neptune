# Bomberman franchise research and eventual feature goals

Research date: **3 November 2026**. Requested scope: every discoverable Bomberman
game and feature, including **Power Bomberman**, recorded as things Neptune can
eventually achieve.

This dossier brings together a release register, detailed game-by-game feature
inventories and proposed capabilities with acceptance experiments. It covers
computer, console, handheld, arcade, phone, smartphone and online games, as well
as spin-offs, compilations, promotional editions and cancelled projects. Related
crossovers and machines are identified separately. Power Bomberman is explicitly
identified as an unofficial fan game.

**This is a broad public-source survey, with open coverage debt.** It does not
establish that every game, carrier build, item, enemy, map, option or hidden state
has been discovered. Sparse releases remain named records with explicit gaps.
Published descriptions are research evidence; none of the original games was
newly executed for this survey. These documents do not certify Neptune feature
completion or reference parity.

The current snapshot contains **222 release/edition discovery records**,
**287 reusable feature candidates** and roughly **51,000 words** across the
Markdown documentation, with **266 distinct external source links**. These are
survey counts, not a claim of 222 unique official games or 287 total mechanics.

## Start here

| Document | What it provides |
| --- | --- |
| [Release index](release-index.md) | Searchable title register, years, platforms, aliases, edition boundaries and unresolved release identities. |
| [Release records](games.tsv) | Machine-readable discovery records; the index explains why record count is not a count of unique official games. |
| [Classic games](classic.md) | Early computers, NES, PC Engine, Mega Drive, Super Bomberman 1–5, Hi-Ten, Saturn, Irem/Neo Geo arcade and Atomic Bomberman. |
| [Handheld games](handheld.md) | Game Boy through DS/PSP, N-Gage, RPGs, Charaboms, equipment, paired editions, link/download play and Land games. |
| [Later console and modern games](console-modern.md) | 3D adventures, PlayStation/GameCube/Dreamcast, Land, sports/racing, downloadable battles and the R series through the 2026 Collection. |
| [Mobile, arcade and spin-offs](mobile-arcade-spinoffs.md) | Carrier-game ledger, smartphone modes, regional PC services, Panic Bomber, Bombergirl, B-Daman, LCD/medal games and cancelled projects. |
| [Power Bomberman](power-bomberman.md) | Version-aware developer claims, battle modes, options, items, stages, progression, netplay and modding evidence. |
| [Feature candidate index](feature-candidates.tsv) | Proposed reusable capabilities and their first meaningful acceptance experiments, extracted from the chapters. |
| [Achievement plan](ACHIEVEMENT_PLAN.md) | How these findings connect to Neptune's existing backlog and eventual implementation. |
| [Research notes](RESEARCH_NOTES.md) | Source quality, conflicting claims, failed retrievals and the next work needed for deeper coverage. |

Each game chapter distinguishes its release identities, gameplay features,
proposed reusable capabilities and remaining research. Use the full section when
implementing a feature: a short candidate title cannot carry every edition caveat.

## What “a feature” includes

The inventories include movement/collision/camera, bomb placement and explosion
geometry, fuses and chains, item caps and combinations, diseases, damage and
protection, mounts and companions, character abilities, terrain and hazards,
campaign objectives and routes, enemies and bosses, scoring/progression/saves,
battle modes and teams, local and online participation, CPU behavior, controls,
menus, presentation, editors, sharing and version-specific additions. Some
chapters enumerate individual abilities or parts; others have only documented
families because the per-entity evidence is missing.

One capability can have many different implementations. “Throw” may suspend a
fuse in one game, continue it in another, wrap at a border, collide with heights,
stun a player, knock out items or be caught. Those are separate contracts, not
permission to choose one generic behavior and claim franchise-wide parity.

An advertised roster of hundreds of characters is not hundreds of distinct
mechanics. A carrier game with a name in a database is not an audited feature
inventory. A planned game is not a shipped feature set. Counts retain these
distinctions throughout.

## Product commitment and delivery order

These are **eventual goals and design references**. The established product is
still Saturn Bomberman's starting look and behavior, extended through namespaced,
versioned community content and explicitly selected profiles. Preserve the
[Saturn fidelity contract](../SATURN_FIDELITY.md),
[community-content contract](../COMMUNITY_CONTENT.md) and
[current factory/Saturn-first delivery priority](../FACTORY_FIRST_GOAL.md).
This requested documentation expansion does not activate a new implementation
queue or change an active owner's accepted work.

Use the same authoritative simulation and public pack interfaces wherever they
can represent a mechanic. Features that require another topology, camera, puzzle
board or movement model need an explicit capability and feasibility slice.
Optional rhythm, racing, puzzle, sports or class-based profiles can remain later
experiments. They must not silently alter the faithful baseline.

Reuse [the existing 418-feature backlog](../backlog/README.md) and its issue
history. Chapter IDs such as `CLASSIC-001`, `HAND-001`, `OBS-001` and the modern and
Power equivalents identify **research/design candidates**, not new factory tasks.
The candidate TSV is a snapshot of the chapter tables; update both together.
It is a reading index, not a second scheduler or acceptance schema.
Deduplicate before creating bounded implementation work.

Installed compatible custom characters remain freely selectable. Original-game
unlock economies can be optional progression profiles. Reference art, binaries,
music and decompiled code are not included in this documentation commit;
content reuse follows [the existing provenance contract](../OPEN_SOURCE_AND_CONTENT.md).

## Keeping the survey useful

Append release IDs rather than renumbering them. Split a regional edition when
mechanics, controls, content or protocol differ. Record a source's actual date
and distinguish an announcement, release, patch, service shutdown and revival.
For every discovered item, stage, enemy, boss phase and option, preserve its
release/build, evidence, exact rule, interaction cases and uncertainty before
promoting it into a measured reference contract. Follow the
[achievement plan](ACHIEVEMENT_PLAN.md) for that handoff.
