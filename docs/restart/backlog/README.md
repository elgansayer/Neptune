# Community Bomberman feature backlog

Master issue: [#69](https://github.com/elgansayer/Neptune-Bomberman/issues/69).
Start with the [issue index](INDEX.md) and machine-readable [catalogue](catalogue.json).
The existing restart epic [#23](https://github.com/elgansayer/Neptune-Bomberman/issues/23)
and its implementation issues retain their scope and history.

This catalogue contains 379 feature specifications in 26 domains. Seven matching
existing issues are reused; the remaining 372 are new bounded implementation or
research issues. These are desired outcomes, not claims that the game already has
them. A worker must inspect current code, active PRs and evidence before deciding
whether to implement, extend, or close an already-satisfied feature.

## Product direction

Multiplayer and strong, fair bots are the first product milestone. Local guests,
remote humans and bots should coexist in extensible rooms, including browser and
native clients. Preserve faithful Saturn presets separately from enhanced Neptune
rules and independently measured Power-inspired profiles. Installed compatible
characters remain freely selectable without compulsory unlocks.

The community builds characters, maps, items, bomb behaviours, modes, mounts,
enemies and complete campaigns through a public, versioned content API. First-party
content uses the same API. Solo stories and explicitly authored local/online co-op
stories are first-class pack types. Compatibility must describe party size,
objectives, checkpoints, joining and companion support; merely labelling a pack
"co-op" does not make it playable cooperatively.

Custom power-ups start with a typed, data-only effect system: bounded triggers,
conditions, stat modifiers, projectiles, hazards, movement and expiry. The server
owns execution, networking and saves. Bots consume declared capabilities and
conservative forecasts. Unsupported effects are rejected for affected sessions
rather than pretending bots can understand arbitrary code. Ice Bomb is the first
complete example. A possible future sandbox is a separate P3 evaluation; downloaded
GDScript, scene scripts and native libraries remain outside the supported pack API.

## Execution order

| Wave | Outcome |
| --- | --- |
| 1 | Reliable simulation, bot safety, bounded factory work and test evidence |
| 2 | Fun multiplayer rooms, cross-play, battle rules, useful bots and controls |
| 3 | Portable packs, custom effects, replays, packaging and original starter media |
| 4 | Solo/co-op campaigns, editors, workshop, identity and community services |
| 5 | Exhaustive measured Saturn/Power content and reference comparisons |
| 6 | Optional original modes, larger rooms and exploratory ideas |

Waves describe emphasis, not a rigid dependency schedule. The 573 explicit
dependency edges take precedence; foundational pack interfaces or reference
measurements may be needed earlier. P0 means foundation/critical-path work, P1 core
product capability, P2 breadth/polish, and P3 optional experiment. Priority does not
override prerequisites or authorise simultaneous execution of every issue.

Parent issues group work; waiting for an entire parent epic before starting its
children would create a deadlock. Depend on the specific deliverable IDs instead.
An issue's closed state alone is insufficient: the required contract must have
linked implementation and applicable executable evidence. Existing issue bodies
retain their original acceptance requirements when a catalogue entry links them.

## Factory handoff

1. Read `AGENTS.md` and the restart contracts. Audit the chosen issue against current
   code and active PRs. Preserve active worker ownership and isolated checkouts.
2. Resolve its concrete prerequisites and available inputs. Select one bounded
   deliverable. Split oversized implementation work into linked children with
   explicit acceptance; do not mark a whole feature complete after a prototype.
3. Implement an original permitted fixture through production paths. Add useful
   regression coverage for the changed behaviour and failure cases.
4. Run applicable native, browser, network, pack and replay checks. Record exact
   versions, seeds, head/base commits, commands, logs and results. Missing, skipped,
   empty and failed applicable checks are failures, not acceptable substitutes.
5. Merge only through the repository's tests-gated policy, with current-base
   validation. No mandatory AI/human approving review is added. Preserve dependent
   branch ancestry and never bypass a failing check.
6. Link evidence, update feature status and close only the acceptance actually met.
   Failed experiments and blocked inputs remain visible.

The repository currently has tests-gated GitHub merging. That is distinct from a
running continuous implementation factory. This backlog does not start workers,
buy infrastructure, authorise unlimited provider spend, or change deployment
permissions. Those remain explicit bounded operator settings and existing #48.

## Reference evidence

The catalogue deliberately separates:

- `reference-research`: inventories, measurements and uncertainty tracking.
- `reference-candidate`: proposed reference mechanics that require pinned evidence.
- `neptune-requirement`: original platform/product design requirements.
- `neptune-experiment`: optional original prototypes, not parity commitments.

Research starting points consulted on 29 October 2026:

- [Power Bomberman developer release thread](https://www.bombermanboard.com/viewtopic.php?t=1925).
  Its version and advertised feature totals are discovery leads, not a verified
  inventory or permission to redistribute its characters and art. Pin the actual
  developer-distributed build and bundled manual before recording parity.
- [Saturn Bomberman US instruction manual scan](https://segaretro.org/images/a/ae/Saturnbomberman_sat_us_manual.pdf).
  Direct retrieval was unavailable during planning. The
  [manual OCR mirror](https://manualzz.com/doc/23194932/sega-saturn-bomberman-video-game-instruction-manual)
  supplied broad mode/control leads; OCR is not reliable evidence for exact timing,
  collision or every regional difference. Confirm against the pinned primary scan
  and executable reference.
- [User-supplied video](https://www.youtube.com/watch?v=S1xMwFb_jGg).
  Retrieval was throttled; no complete viewing, transcript or timestamped analysis
  is claimed. REF-012 tracks reconciliation when footage becomes available.

Follow `REVERSE_ENGINEERING.md`, `POWER_BOMBERMAN.md`,
`OPEN_SOURCE_AND_CONTENT.md` and `NETPLAY_BENCHMARKS.md`. Keep private reference
media outside Git. A title such as a Tirra ability, Power mode or unusual bomb type
is a measurement target, not an assertion that the wording precisely matches every
reference release. Confidence, counterexamples and unresolved semantics must remain
visible. Original fixtures can progress while reference inputs are unavailable.

## Exhaustive content without invented entries

This is a comprehensive system-level backlog, not a claim that all individual
rooms, characters, sounds, enemies or variants have been enumerated. REF-002 through
REF-010 and REF-014 produce versioned inventories and one bounded child issue per
observed entity/variant. Each child needs a stable source identifier, evidence,
mechanical or presentation contract, provenance, dependencies and a comparison
fixture. Re-running inventory expansion must not create duplicates.

Never create hundreds of guessed character names or mark a published feature total
as measured coverage. Cosmetic characters can share animation-validation work;
distinct mechanics and boss phases require separate executable comparisons. This
process lets the backlog grow to real content completeness as evidence arrives.

## Maintaining the catalogue

`features.tsv` is the human-authored scope and acceptance source. `build_catalogue.py`
defines explicit dependencies and existing-issue mappings. `issue-links.json`
records published issue numbers. Generated `catalogue.json` and `INDEX.md` are
committed; temporary API payloads are not.

```sh
python3 docs/restart/backlog/build_catalogue.py
python3 docs/restart/backlog/build_catalogue.py --check
```

The validator checks IDs, titles, links, dependency references, acyclicity and
generated metadata consistency. It cannot certify gameplay, reference fidelity,
asset permissions, service deployment or a running factory. Preserve IDs and issue
history when editing scope. Audit related issues before adding a new feature.
