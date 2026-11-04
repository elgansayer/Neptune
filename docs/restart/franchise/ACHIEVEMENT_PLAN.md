# Turning the franchise survey into eventual Neptune capabilities

This is the implementation reading guide for the [franchise dossier](README.md).
All capabilities below are desired outcomes, subject to code/evidence audit and
the existing [factory/Saturn-first priority](../FACTORY_FIRST_GOAL.md). They are
not claims that Neptune already implements them. The chapters contain finer
mechanical distinctions and the first proposed acceptance experiments.

## Reuse the existing work

The canonical implementation/research queue is
[backlog/catalogue.json](../backlog/catalogue.json), generated from its existing
TSV and linked issues. Keep its IDs, dependencies, acceptance revisions and active
owners. The franchise release registry and candidate tables are research indexes.
They do not replace that schema, create hundreds of issues or start workers.

| Franchise feature family | Existing work to inspect and extend | Eventual result |
| --- | --- | --- |
| Release identities, editions, aliases and confidence | REF-001–014; RLAB-002, RLAB-008 | Every claimed rule belongs to a pinned release and has visible evidence and unknowns. |
| Exact Saturn code, content and behavior | RSAT-001–020; SATURN-001–014; #477 | Original campaign, Master and Battle contracts remain the baseline and primary recovery work. |
| Power release, code, media and protocol | RPWR-001–010; REF-007–010; POWER-001–006 | Measure actual Power rules before independently implementing its breadth in compatible profiles. |
| Clocks, RNG, simultaneous events and replay | SIM-001–016; REPLAY-001–010 | Seeded scenarios retain placement, impact, damage, scoring and transition order across compatible clients. |
| Movement, collision and varied field sizes | SIM-005–008; ARENA-002, ARENA-015–016 | Grid, scrolling, wide and height-aware arenas declare geometry and camera requirements. |
| Ordinary/remote/piercing/bouncy/mine/line bombs | BOMB-001–019 | Bomb behavior composes through explicit movement, fuse, blast and ownership contracts. |
| Unusual shapes, targeting and bomb fusion | BOMB-013, BOMB-015; EFFECT-001–014; PACK-011 | Directed, seeking, elemental, circular, charged and combined bombs get bounded declarative capabilities. |
| Pickup caps, illness, protection and scatter | ITEM-001–022; SIM-009–010 | Multiple effects have explicit stacking, replacement, curing, damage and death/reset rules. |
| Terrain, weather and changing stages | ARENA-001–020 | Belts, warps, arrows, launchers, ice/water/lava, darkness, pressure and arena transformations share stage APIs. |
| Mounts, eggs, companions and special actions | MOUNT-001–010; PACK-009, PACK-013; BOT-008–009 | Author distinct mount/companion mechanics without embedding a fixed roster into engine code. |
| Survival, teams and objective battles | BATTLE-001–016; BOT-014 | Elimination, floor paint, dodge, collection/delivery, king and other objectives expose scoring and bot goals. |
| Story routes, quests, shops and equipment | STORY-001–018; EFFECT-001–014 | Campaigns can declare objectives, persistent variables, inventories, NPC services and branching routes. |
| Enemy/boss behavior and companions | STORY-007–009; BOT-001–018; REF-003 | Enemy roles and fair battle CPUs consume the supported mechanics and declared observations. |
| Local/online authored co-op | COOP-001–012; ROOM-002, ROOM-009 | Lives, revival, joining, checkpoints, companion substitution and camera rules work as authored. |
| Rooms, guests, spectators and matchmaking | ROOM-001–016; SOCIAL-001–010 | Humans, bots and guests agree on room settings and content before play; lifecycle failures stay recoverable. |
| Networking and cross-play | NET-001–014; OPS-001–012 | Browser/native clients share authoritative outcomes, exact version locks and measured network behavior. |
| Map, character, mode and campaign creation | PACK-001–018; EDITOR-001–018; WORKSHOP-001–016 | Creators publish portable additions; clean clients automatically acquire the exact compatible versions. |
| Profiles, progression, ranks and records | STATS-001–012; SOCIAL-007; POWER-002–004 | Optional progression records meaningful results without compulsory grinding for custom content. |
| Input, help and readable presentation | UX-001–016; MEDIA-001–012 | Controls and cues remain understandable across devices; faithful simulation differences stay explicit. |
| Puzzle, racing, sports, rhythm and asymmetric classes | EXP-001–010, especially EXP-003/004/006/007 | Optional profiles prove one useful complete slice before any larger subsystem is scheduled. |

The table identifies **work to inspect**, not a guarantee that every new
mechanical detail is already accepted in those issues. For example, Charabom
breeding, a match-three puzzle board, rhythm charts or a vehicle handling model
may exceed an existing issue's scope. Reuse a compatible interface; otherwise
propose a bounded child through the existing intake fields and preserve the
parent's accepted revision.

## Capabilities to aim for

### Bomb and item semantics

Represent the full lifecycle: acquisition, active equipment, placement legality,
owner overlap, movement/airborne/held state, fuse policy, trigger/chain priority,
blast geometry, hit layers, secondary hazards, expiry and death/round cleanup.
Treat ability and visual identity separately. A piercing bomb, full-range bomb
and spherical blast are different mechanics even when a translated name calls
all three “power bombs.”

Candidate families include stopped kicks, punches, throws, catches, line and
tower placement, wrapping trajectories, contact mines, homing/steered bombs,
charge/impact attacks, remote ownership, elemental effects, fusion and partial
destruction. Item policies include positive/negative stat changes, temporary
and permanent effects, mutually exclusive gear, ejected items, concurrent
diseases, contagious status, global events and protection-layer precedence.

The first useful experiment changes one variable, includes a boundary/countercase
and verifies the final state plus ordered events. An authored native scenario
proves an original Neptune capability. Reference parity additionally needs pinned
original observations and the applicable exact comparison gate.

### Stage and actor composition

Separate logical topology, collision, terrain/hazard rules, visuals and capacity.
Support ordinary/wide/scrolling/multi-region layouts through explicit dimensions,
spawn positions, camera/HUD framing and visibility policies. Height, platforming,
first-person and vehicle profiles need their own validated movement and blast
contracts rather than a cosmetic camera switch.

Eventually compose conveyors and reversals, directional arrows, warps, wrap
edges, trampolines/seesaws, rails, moving floors, doors/switches, slippery/slow
terrain, water/lava, changing weather, darkness, regenerating blocks, collapses,
pressure patterns and moving hazards. Moving actors, bombs and flames can have
different traversal permissions.

Mounts and companions need ownership, extra-hit precedence, abilities, growth,
feeding/evolution, dismounting, unattended persistence, spare eggs and any
sacrifice/death behavior. Distinguish campaign companions, autonomous enemies,
battle CPU policy and character appearance. A Charabom ability catalogue is
evidence for those mechanics, not automatic evidence for all breeding recipes.

### Mode and campaign variety

Aim for reusable objectives: eliminate, survive, paint tiles, gather/deposit,
hold a position, carry a crown, escape, clear only designated targets, protect,
rescue and assault a base. Every mode specifies teams, attribution, scoring,
ties, timeout, overtime, respawn/revenge, loadouts, resets, bots and replay.
An online advertised population must be separated from seats in one arena.
Battle 64's connected rooms are not one enormous simultaneous 64-seat board.

Campaign data should represent connected rooms, non-linear world selection,
keys/gates, NPC services, shops, inventory/equipment budgets, collectible
companions, side quests, checkpoints, multiple endings, repeat passes and
completion records. Co-op declares objective ownership, lives, revival, shared
camera, join/leave policy, save ownership and party-wipe handling.

Optional puzzle boards need their own piece/match/gravity/garbage/chain/top-out
rules. Racing needs checkpoints, laps, handling and finish validation. Rhythm
battles need chart identities and authoritative event timing. Sports and
attraction collections need authored controls, scoring and progression adapters.
These remain explicit experiments until a complete slice proves feasibility.

### Participation, creation and presentation

Provide local guests, bots and remote participants through one command path.
Freeze the rules/content contract before starting; preserve protocol and content
versions in replays and saves. Room/server discovery, invitations, reconnect,
spectating and rematches remain distinct capabilities. Historical link cables,
download play and modem services inspire participation goals; they do not imply
we must reproduce obsolete hardware protocols in the public product.

Prefer public data-only pack APIs for authored characters, arenas, bombs, items,
mounts, objectives and complete stories. First-party content should exercise
the same path. Editors need validation, preview/playtest, undo/save and immutable
version publication. Demonstrate automatic sharing with two clean clients,
including a joining player's custom character and a server's map/mode/item pack.

Preserve clear player markers, color/shape cues, remappable input, control help,
independent sound controls and the existing accessibility goals. Voice, touch,
motion and dual-screen controls should map to supported commands with practical
alternatives. Collection-style solo rewind/save states require a trustworthy
boundary from online rankings and multiplayer authority. They do not relax the
faithful reference's simulation rules.

## Promote a finding into bounded work

1. Locate the game/edition in [games.tsv](games.tsv) and read the linked chapter.
   Resolve the actual build, platform, region and mode before specifying behavior.
2. Search the existing backlog, current code, open PRs and ownership. Reuse an
   existing result or accepted task; do not dispatch overlapping work.
3. Retain sources and separate documented claims from actual observations.
   Pin original inputs and run a controlled scenario when reference fidelity is
   required. Record contradictory observations and precision limits.
4. Specify one observable capability using the existing acceptance/evidence
   fields: inputs, state transitions, interactions, failure cases, time units,
   output identities, profile and meaningful regression controls.
5. Implement through shared extension points using an original/permitted
   fixture. Demonstrate additive coexistence, bot compatibility, replay and
   clean-client sharing where applicable. State why unrelated gates do not apply.
6. Run the required deterministic and applicable runtime checks at the exact
   candidate head/current base. Missing, failed or skipped applicable evidence
   leaves the feature open. Follow [the merge policy](../MERGE_POLICY.md).
7. Update only the supported scope: documented, measured, implemented and
   verified are separate states. Link evidence and preserve old pack/save/replay
   versions. One successful example does not close the whole family.

## Completion remains a discovered denominator

For each release, maintain a reconciled list of modes, options, items, combinations,
maps/variants, actors, enemy/boss states, progression routes, controls and
presentation states. New discoveries expand that denominator. A hundred passing
known scenarios cannot establish that an unsearched hidden mode does not exist.

Use the existing REF inventories and idempotent child expansion for Saturn and
Power. For another game, first establish a bounded inventory through the same
intake contract. Record what remains unsearched, inaccessible or disputed. The
eventual goal is broad capability coverage and independently evidenced fidelity
where selected; documentation volume alone cannot satisfy either.
