# Power Bomberman: release inventory, features and eventual targets

Research date: **3 November 2026**. This chapter covers the unofficial fan game
**Power Bomberman**, separately from Hudson/Konami releases. It records public
developer statements and documented third-party modifications. No reference game
was launched, timed or network-tested during this survey. All Neptune targets
below remain aspirations until their existing implementation tasks supply evidence.

Read [the existing Power research contract](../POWER_BOMBERMAN.md),
[community-content contract](../COMMUNITY_CONTENT.md) and
[current factory/Saturn priority](../FACTORY_FIRST_GOAL.md) together with this
inventory. Power-inspired additions belong in selected extensible profiles;
they must preserve the measured Saturn default experience.

## Evidence and release identity

The current developer first post identifies **0.7.8c, 1 March 2026**, with separate
Windows, macOS and Linux client downloads and a matching optional server [PB01].
The title remains 0.7.8c on the final thread page inspected for this survey [PB02].
This establishes a publicly advertised version, not a cryptographically pinned
archive or proof that no newer distribution exists elsewhere.

| Release or evidence point | What the inspected source establishes | Important distinction |
| --- | --- | --- |
| Public thread, 8 March 2013 | Developer Jei opened the Power Bomberman thread on this date [PB01]. | The first post has since been edited; its current download version cannot be assigned to 2013. |
| 0.1.2, 12 March 2013 | Developer post #5 announces an update, bomb-hit interactions and disease ejection when collecting an item [PB01]. | Historical statement, not a current regression result. |
| 0.2.1, 4 April 2013 | Developer post #7 links this version and previews expanding content [PB01]. | No archive was obtained or compared. |
| 0.3.1, 4 May 2013 | Developer post #11 announces more stages/items and says online was then work in progress [PB01]. | This historical online limitation is superseded by the present advertised online mode. |
| Upcoming wide mode, May 2013 | Developer post #12 describes a Hi-Ten-inspired, Saturn-width, twelve-player arena and several variants [PB01]. | A development preview cannot prove every listed variant survives in 0.7.8c. |
| 0.7.7c showcase, 2022 | Developer-associated SAGE page describes the six named rules, Score/Turbo, Louies and older advertised content totals [PB03]. | Its heading says five rules but lists six; use the enumerated names, not that inconsistent heading. |
| 0.7.8b, 24 December 2025 | Developer post #902 announces Windows/macOS/server packages, then a Linger-explosion hotfix and three server hotfixes [PB02]. | Same display version can identify different bytes; retain archive hashes and hotfix identity. |
| 0.7.8c, 1 March 2026 | Current developer post advertises Windows/macOS/Linux clients and an optional matching server [PB01], [PB02]. | Actual minimum OS versions, runtime libraries and architecture support were not verified. |

This is one evolving fan game with multiple release versions and platform builds.
The server package is a companion distribution, not another gameplay title.
Third-party styles are modifications, not additional official Bomberman games.

## Currently advertised feature surface

The following are **developer-advertised 0.7.8 features**, as displayed alongside
the current 0.7.8c downloads [PB01]. The wording deliberately distinguishes a
claim from an executed observation.

| Category | Advertised feature | What still needs direct inventory or experiment |
| --- | --- | --- |
| Participants | Up to twelve players. | Exact limits for each arena/rule, local-human device topology, mixed local/online seats and bots. |
| Entry paths | Quick Battle, Local Battle and Online Battle. | Each menu route, saved presets, default settings and controller assignment. |
| Online setup | Connect to the main server without player port forwarding. | Actual transport, relay architecture, latency behavior, reconnect and hosting requirements. |
| Rules | Survival Battle, Reversi Battle, Dodge Battle, Hyper Bomber, King Battle and Battle Royale. | Full mode-specific scoring, timing, team, tie and reset contracts. |
| Solo | Score Mode inspired by NES Bomberman, including Turbo mode. | Complete stage/enemy/progression inventory and exact Turbo differences. |
| Items | Many familiar and original items; items can be turned off. | Actual item IDs, names, effect values, exclusion rules, stacking and drop tables. |
| Characters | Over 700 unlockable playable characters from the series, plus Konami guests. | Exact build-specific count, variants versus separate characters, unlock costs and gameplay differences. |
| Stages | Over 80 stages totaling around 700 variants. | Actual stage/variant list, identifiers, layouts, compatibility and rule restrictions. |
| Match options | Revenge Bomber and Sudden Death. | Each setting's allowed values and effects in every mode. |
| Detailed options | Bomb fuse, explosion timing and damage caused by Pressure Blocks. | Numerical values, time units, ordering and interaction with health/invulnerability. |
| Platforms | Windows, macOS and Linux clients. | Supported architectures, display/input behavior and platform-specific limitations. |
| Server choice | Main server plus an optional downloadable server. | Fully offline LAN setup, discovery, configuration, compatibility and operational requirements. |

The over-700/over-80/around-700 figures are marketing-scale advertised counts.
They are not measured completeness denominators or permission to redistribute
the character art, music or other reference resources.

## Battle entry paths and room lifecycle

**Quick Battle** is an advertised shortcut into battle [PB01]. An early user
requested fewer selection screens and the developer agreed a Quick Battle
activation would be useful; the current feature list now explicitly names it
[PB01] (posts #2–3). This history supports a useful product target: retain a fast
play route alongside detailed configuration. It does not establish the exact
current shortcut defaults.

**Local Battle** is separately advertised [PB01]. Treat local seat assignment,
keyboard sharing, controller selection, CPU fill, remapping, disconnect handling
and per-player options as separate inventory questions. Twelve advertised
participants do not prove twelve simultaneous mixed-brand controllers work.

**Online Battle** uses a main server and is advertised as needing no port
forwarding for players [PB01]. The SAGE description explicitly says players can
connect, make a room or join a room [PB03]. This establishes public room creation
and joining at the feature-description level. Passwords, spectators, host
migration, account persistence, moderation and matchmaking algorithms remain
unresolved in the inspected material.

**Optional server distribution** is explicitly offered for users who do not want
to use the main server [PB01]. A community member links a Docker wrapper in
post #908, and the developer acknowledges it in #909 [PB02]. Neither statement
proves that this wrapper is official, current, secure or necessary. The April
2026 LAN question in #915 is a user's unresolved question, not evidence that
LAN play is impossible.

## The six battle rules

The current release post names all six rules [PB01]. The inspected SAGE page
provides concise objectives for each [PB03]. Those objectives are enough for
feature discovery, but not enough for implementation parity.

### Survival Battle

- Developer description: last player standing wins [PB03].
- Catalogue the ordinary elimination loop separately from configurable health.
- Determine simultaneous elimination, surviving teams, draw and timeout results.
- Determine whether eliminated players enter Revenge Bomber under each option.
- Record item loss/drop and mount behavior on damage and death.
- Neptune acceptance idea: controlled elimination, simultaneous final deaths,
  timer expiry and team survivors produce the specified ordered results; replay
  and online clients agree with the authoritative simulation.

### Reversi Battle

- Developer description: paint as many tiles as possible [PB03].
- Exact ownership conversion, contested blasts, ownership persistence and tile
  eligibility are not specified by the inspected description.
- Determine whether scoring is final territory, accumulated time, or another
  rule; do not assume it from the word Reversi.
- Inventory neutral tiles, hard blocks, soft blocks and mode-specific geometry.
- Neptune acceptance idea: a small arena with scripted overlapping blasts
  demonstrates tile ownership, final score, equal-score ties and team accounting.

### Dodge Battle

- Developer description: avoid bombs falling from above [PB03].
- Inventory bomb generators, warning cues, target selection, cadence and RNG.
- Determine whether ordinary player bomb placement is available in this mode.
- Determine which defensive items, mounts and health options are compatible.
- Neptune acceptance idea: a pinned sequence produces the expected warning,
  landing, collision, blast and elimination events with equivalent bot perception.

### Hyper Bomber

- Developer description: collect key items and reach the gate [PB03].
- Number and identity of required items, gate placement and interaction timing
  remain unmeasured.
- Determine whether key items drop on damage/death and whether opponents can
  interrupt or steal progress.
- Determine team possession, simultaneous gate entry and timeout handling.
- Neptune acceptance idea: authored acquisition and gate-entry scenarios cover
  missing items, valid completion, interruption, duplicate pickup and a tie.

### King Battle

- Developer description: take the crown and protect it from opponents [PB03].
- Exact crown-transfer trigger and winning threshold remain unresolved.
- Determine held-time versus survival scoring, crown drops, owner death, hazard
  disposal and protection/invulnerability interactions.
- Determine whether the crown affects movement, abilities or item eligibility.
- Neptune acceptance idea: deterministic crown possession and transfer history
  produces reproducible per-player/team scores across death and timer boundaries.

### Battle Royale

- Developer description: score more frags than the others [PB03].
- The name does not establish a shrinking multi-arena or sixty-four-player mode.
- Respawn, spawn protection, kill attribution, suicides, team kills, assists,
  environmental deaths and score ties require direct observation.
- Determine score limit, time limit and whether round progression exists.
- Neptune acceptance idea: an explicit attribution table covers direct kills,
  kicked/thrown bombs, chain reactions, self-kills and hazards without double awards.

## Score Mode and Turbo

Score Mode is advertised as inspired by the NES Bomberman game [PB01]. The older
SAGE page calls it a remake and separately mentions an amped-up Turbo mode
[PB03]. Neither phrasing is evidence that all NES room layouts, enemy parameters,
secrets or timing match exactly.

Record the following as separate discovery tasks before claiming coverage:

1. Campaign room and stage progression, exit conditions and completion rules.
2. Enemy species, movement policies, spawn sources and score awards.
3. Lives, damage, death recovery, continues, checkpoint and save behavior.
4. Item persistence between rooms, between lives and between sessions.
5. Bonus objectives, hidden items, timer behavior and failure conditions.
6. Score multipliers, chains, extra lives and score-table persistence.
7. Turbo movement, bomb and enemy changes versus ordinary Score Mode.
8. Character availability and unlock-currency interaction in each mode.
9. Input mapping, pause, restart, results and return-to-menu routes.
10. Any co-op or multiplayer support: **unknown**, not advertised in the inspected
    Score description, and not ruled out by that silence.

For Neptune, a score-attack campaign is an eventual selectable profile. It must
not replace the faithful Saturn campaign or prevent creator-authored stories.

## Items, bombs, damage and movement: what is actually evidenced

The current announcement promises a large configurable item set without listing
each item [PB01]. The early developer posts expose concrete item and interaction
leads. These are **historical source statements**, not an audited 0.7.8c item list.
The current manual and reference build must reconcile them before parity claims.

| Named feature or interaction | Evidence in inspected material | Scope and remaining questions |
| --- | --- | --- |
| Bomb Up | Developer names it in Dungeon variant A's restricted pool [PB01] (#14). | Inventory capacity progression, caps and recovery. |
| Fire Up | Developer names it in the same restricted pool [PB01] (#14). | Inventory range units, caps and special-bomb overrides. |
| Speed Up | Developer names it in the same restricted pool [PB01] (#14). | Measure speed increments, collision/corner behavior and caps. |
| Configurable item pool | Developer says all items, including steeds, can be tweaked before a match [PB01] (#14). | Current setting granularity, per-mode exclusions and presets unknown. |
| Steeds/Louies | Early developer statement names steeds; SAGE explicitly names Louies [PB01], [PB03] (#14;). | Mount species/colors, abilities, hit absorption, dismounts and animations unknown. |
| Disease transfer/ejection | Developer says collecting an item makes disease fly out in 0.1.2 [PB01] (#5). | Disease types, contagion, cure timers and present behavior unknown. |
| Bomb impact | Developer says Bombermen can get hit by bombs in 0.1.2 [PB01] (#5). | Stun/damage distinction, immunity and impact timing unknown. |
| Gauntlet/bomb throw | A user's detailed request and developer-era discussion name throwing [PB01] (#15–20). | Treat detailed requested changes as proposals, not confirmed mechanics. |
| Kick/stop | User discussion names kick-stop and configurable actions [PB01] (#15–20). | Current button binding and stop-at-tile behavior need a manual/runtime check. |
| Remote bombs | Users discuss remote-bomb handling historically and in a 2025 Flower Zone report [PB01], [PB02] (#20;  #903). | User report supports a discovery lead, not verified current semantics or a confirmed defect. |
| Jelly and danger bombs | Historical user discussion asks about bomb collisions and danger-bomb creation [PB01] (#15). | Request alone does not verify implementation; keep unresolved. |
| Line bomb | Historical user discussion names an action and asks to change its binding [PB01] (#20). | Current availability, control and precedence unresolved. |
| Block-pass | Historical user report describes walking through blocks [PB01] (#20). | No current AI or safety claim follows from that old report. |
| Mines | Historical user proposes combining mines with remote detonation [PB01] (#20). | The proposed combination is not an established feature. |
| Tracing/Magnet bombs | A December 2025 user proposes smarter targeting options [PB02] (#905). | Presence is a strong lead; the requested smart AI setting is unconfirmed. |
| Health and Pressure Block damage | Current developer list explicitly advertises configurable Pressure Block damage [PB01]. | Exact health system, damage values and lethal override rules need direct observation. |
| Linger explosion type | Developer's December 2025 hotfix note names this explosion type [PB02] (#902). | Full flame model and current timing remain unmeasured. |

Avoid treating a feature request as proof that the proposed behavior was shipped.
For each retained lead, record its release, source role, actual menu/item ID and
captured interaction. A set of familiar Bomberman item names is insufficient to
establish the exact Power implementation.

### Interaction coverage needed for each item

- Pickup versus existing same-category powers; stacking, replacement and caps.
- Dropped, burned, hidden, thrown, airborne and conveyor-carried item behavior.
- Action-button precedence with kick, throw, line placement and detonation.
- Capacity accounting for carried, kicked, thrown, remote and transformed bombs.
- Fuse behavior while airborne, bouncing, transported, stunned or in transit.
- Blast propagation through soft blocks, special blocks, bombs and arena edges.
- Chain ownership and frag credit after another player moves or triggers a bomb.
- Damage, invulnerability, mounts, disease and item-loss event ordering.
- Death, respawn, round-end and disconnect cleanup of owned entities.
- CPU knowledge and legal moves under each item capability.
- Replay and client/server agreement for simultaneous boundary cases.

These are acceptance dimensions, not additional confirmed Power features.

## Arena geometry, stage variants and hazards

The current advertised scale is over eighty stages and approximately seven
hundred variants [PB01]. The older SAGE showcase says over seventy stages and
roughly five hundred variants [PB03]. Preserve these as dated advertisements;
do not merge them into an exact current total.

Developer post #12 previews the following wide-stage configurations [PB01].
They identify valuable reusable stage primitives even where current inclusion
still needs reconciliation:

| Historical wide-stage configuration | Reusable content capability | Required future measurement |
| --- | --- | --- |
| Basic | Explicit arena dimensions, spawns and block layout. | Exact collision grid, player capacities and framing. |
| Conveyor belts and warp points | Directional transport plus teleport destinations. | Speed, eligibility, exit selection and collision ordering. |
| Curve marks and screen-wrap passages | Bomb redirection and linked opposite boundaries. | Entering direction, wrapped trajectories and flame behavior. |
| Power variant with no soft blocks and starting power-ups | Per-variant initial loadouts and block generation. | Starting inventory and mode-specific overrides. |
| Trampolines, seesaws and screen-wrap passages | Launch/height transitions and interactive stage machinery. | Trigger contacts, timing, landing and damage handling. |
| Trolley cart, revolving door and screen-wrap passages | Vehicles and moving passage geometry. | Boarding, occupancy, movement, collision and release rules. |
| Enemy spawn point, double-hit soft blocks and curve marks | Arena enemies and multi-hit destructibles. | Spawn cadence, damage state and blast interruption. |
| Conveyors, screen wrap, curve marks and booster fields | Composable interacting stage effects. | Simultaneous transport/turn/boost resolution. |

The developer later says Robo Bomber from Party Edition was added as a city-stage
variant in post #19 [PB01]. This is a historical inclusion statement. Inventory
its robot path, obstruction, visual occlusion, stun and hazard interactions from
the actual selected build before implementing a faithful variant.

The current thread additionally contains a user's Flower Zone/truck/remote-bomb
report [PB02] (#903). Keep this as a named stage/interaction lead, not a validated
bug or evidence for a particular vehicle implementation.

For each current arena, the eventual inventory needs a stable stage ID and
variant ID, dimensions, seat capacity, legal modes, hard/soft-block placement,
spawn protection, item table, hazards, ambient entities, wrap links, transport
links, camera/HUD framing and audio/visual resources. Unknown layouts remain
unknown; a screenshot is not a collision or hazard contract.

## Match options and presets

The current developer list explicitly supports item toggles, Revenge Bomber,
Sudden Death, bomb fuse, explosion timing and Pressure Block damage [PB01].
Treat option serialization and interactions as part of the feature, not merely
the existence of a menu control.

| Option family | Established public evidence | Questions to resolve before implementation parity |
| --- | --- | --- |
| Rule selection | Six named battle rules [PB01], [PB03]. | Mode-specific defaults, arena filtering and validation. |
| Item availability | Current toggle promise and historical per-match tweaking [PB01]. | Binary versus weighted settings, saved presets, spawn and initial-loadout separation. |
| Revenge Bomber | Named current option [PB01]. | Cart positions, movement, throw range/rate, revival rules and mode compatibility. |
| Sudden Death | Named current option [PB01]. | Activation threshold, pressure-block patterns, rounds and ties. |
| Bomb fuse | Named detailed option [PB01]. | Units, minimum/maximum, special-bomb exceptions and airborne behavior. |
| Explosion timing | Named detailed option; Linger appears in hotfix notes [PB01], [PB02]. | Growth/hold/retract phases, damage windows and chain timing. |
| Pressure Block damage | Named detailed option [PB01]. | Numeric domain, crush versus damage, immunity and mounts. |
| Sound style | Mod author instructs setting sounds to Saturn [PB04]. | Complete built-in style list and current compatibility unverified. |
| Controller configuration | October 2026 user mentions config.ini/controller mapping [PB02] (#917). | This is user evidence; supported schema and backend limits need direct inspection. |
| Team settings | Historical user references Tag Match [PB02] (#905). | Current team modes, friendly fire and player/team scoring need verification. |

The current evidence does not establish per-player handicaps, independent CPU
difficulties, all starting-loadout options or the complete advanced-settings
schema. Some were requested historically; they must not be silently promoted
to confirmed current options.

## Characters, progression and saved data

The current developer post advertises more than seven hundred **unlockable**
playable characters spanning the Bomberman series with some Konami guests
[PB01]. The SAGE showcase's older count is more than six hundred and fifty
[PB03]. Count and identity must be scoped to a pinned build.

The final page contains a user's question about retaining Bombercoin purchases.
Developer reply #909 states that save files live in AppData and a newly unpacked
version loads them automatically while they remain there [PB02]. This supports
a Windows save-location/migration statement at that date. It does not establish
all platform paths, every upgrade path or cloud synchronization.

Inventory separately:

- Character versus skin/variant identity and default roster.
- Cosmetic differences versus simulation-affecting abilities.
- Unlock currency earning, purchases, prices and persistence.
- Character selection availability in local, online and Score modes.
- Selection grid, search/filtering, favorites and duplicate-selection behavior.
- Palette/readability handling when several players choose similar characters.
- Voices, portraits, animation states, hitboxes and mount attachment points.
- Save format, backups, corruption recovery and migration across builds.
- Guest-character provenance and redistribution permissions.

**Neptune intentional choice:** installed compatible permitted characters should
be freely selectable without compulsory unlock grinding. Optional collections
and progression must not block custom avatars [community contract](../COMMUNITY_CONTENT.md).
This is a product decision, not a claim that Power behaves identically.

## Input, platform compatibility and accessibility questions

Windows/macOS/Linux packages are explicitly advertised [PB01]. No tested
accessibility or device-compatibility matrix was produced in this survey.

A user on 11 October 2026 reports difficulty using ten mixed controllers together
on Windows 11 despite each working alone [PB02] (#917). The report lists several
controller families and suggests device-order sensitivity. It does **not** prove
the root cause, a global device limit, a specific input API or reproducibility.
Treat it as a useful test case for Neptune's large local rooms.

Other final-page users report launch issues and discuss DirectX/SDL or Windows 7
[PB02]. A developer offers a tentative DirectX diagnosis in #909. User claims
about the game's SDL versions are not a verified technical inventory.

Future input/accessibility inventory should cover remappable controls, separate
action bindings, keyboard rollover, mixed controllers, hotplug/disconnect,
duplicate device identifiers, repeat/dead-zone behavior, readable seat markers,
color-independent teams, flash reduction, text scale, audio cues and assistive
input. Their presence in Power is unresolved unless directly documented.

## Modifications and creator support

Do not claim that Power Bomberman has no mods. A mod author's page explicitly
documents style modifications that replace bomb, item and explosion graphics
plus corresponding sounds [PB04]. Its installation instructions replace
`data.win` and a sounds directory. Listed styles include Super Bomberman 5,
Panic Bomber PCE, Bomberman '94, Bomberman '90/Mega, Bomberman Jetters GBA and
custom styles. Those examples are named third-party releases, not claims that
every style works with 0.7.8c.

The documented replacement approach establishes that modifications exist. It
does not establish an official public pack API, additive namespaced registration,
arbitrary maps/rules/power-ups, automatic online distribution, a workshop or
cross-version compatibility. Those questions remain open.

For Neptune, follow the existing additions-only contract: namespaced immutable
content, explicit selected variants, collision rejection, exact-version session
locks and automatic permitted server/character downloads. Do not overwrite base
or other authors' content to reproduce a style mod.

## Eventual feature candidates and acceptance ideas

These chapter-local IDs are research/aspiration references. They are **not a
second factory intake schema**, new implementation issues or evidence of finished
work. Reconcile them with the existing catalogue and issue owners before dispatch.
The current factory and Saturn-code priorities remain in effect.

| Candidate | Eventual capability | Meaningful acceptance idea | Existing scope to reuse |
| --- | --- | --- | --- |
| PWR-001 | Pin Power client/server/manual releases. | Archive and extracted-file hashes distinguish 0.7.8c platform builds and same-version hotfixes. | #41, #498, RPWR input/recovery scope. |
| PWR-002 | Repeatable desktop reference capture. | Known configuration navigates to a chosen match; timestamps, focus errors and capture uncertainty are retained. | #42 and Power lab. |
| PWR-003 | Twelve-seat selected profiles. | Valid standard/wide layouts accept legal seats and reject incompatible capacity before starting. | #43; room-capacity contract. |
| PWR-004 | Quick Battle route. | A saved valid preset enters play through a short route and produces the same locked settings as detailed setup. | Existing room/profile UI scope. |
| PWR-005 | Local human/CPU setup. | Mixed keyboard/controllers bind distinct seats; CPU fill does not displace humans or duplicate input. | Room/bot fill; existing input scope. |
| PWR-006 | Online room creation/join. | Clean clients discover/create/join, agree on content/profile locks and complete a match. | Multiplayer/community contract. |
| PWR-007 | Player-hosted server. | A clean client joins an independently hosted room with permitted exact-version downloads. | Existing hosting/content-sharing scope. |
| PWR-008 | Survival rule. | Elimination, final simultaneous deaths, timer and teams resolve according to a measured contract. | BATTLE-001 (#133); existing mode schema. |
| PWR-009 | Reversi territory rule. | Overlapping blasts, tile eligibility and ties produce specified ownership and scores. | #44 and later bounded mode children. |
| PWR-010 | Falling-bomb Dodge rule. | Controlled generator sequence reproduces warning, landing, damage and winner. | Existing extensible modes/hazards. |
| PWR-011 | Hyper Bomber objective. | Key acquisition, losses, gate validation and simultaneous completion are deterministic. | Existing extensible objective API. |
| PWR-012 | Crown possession rule. | Transfers, holder death and scoring boundaries preserve a replayable possession history. | Existing extensible objective API. |
| PWR-013 | Frag-score Battle Royale. | Chain ownership, moved bombs, self-kills, hazards and ties award exactly the authored score. | Existing elimination/settlement contracts. |
| PWR-014 | NES-inspired score campaign. | Authored rooms, enemies, exits, scoring and lives persist correctly across progression/death. | Campaign/creator scope; #53. |
| PWR-015 | Turbo score profile. | Explicit parameter differences preserve the ordinary profile and replay identity. | #43 and campaign profiles. |
| PWR-016 | Configurable item pools. | Pool/preset serialization, exclusions and match locks reproduce a seeded drop sequence. | Declarative power-ups; #52. |
| PWR-017 | Detailed bomb fuse settings. | Measured fuse settings match placement/airborne/chain boundaries in source units. | Existing bomb/timing contracts. |
| PWR-018 | Explosion models including Linger lead. | Growth/hold/damage/retract ordering is measured, then checked with deliberate timing mutations. | Existing explosion/simulation scope. |
| PWR-019 | Pressure Block damage options. | Health, mounts, immunity, crush timing and simultaneous hazards resolve without duplicated deaths. | Existing hurry-block/damage scope. |
| PWR-020 | Revenge Bomber. | Eliminated-player movement, throws, capacity and return rules match the selected measured profile. | Existing Saturn/Power battle scope. |
| PWR-021 | Sudden Death patterns. | Authored pressure-block schedule, safe area and final outcomes reproduce across replay/network. | Existing stage/timing scope. |
| PWR-022 | Louies/steeds. | Independently authored mount declares attachment, actions, damage and dismount behavior through public APIs. | Existing mount/pack scope. |
| PWR-023 | Disease/item interactions. | Acquisition, contagion, pickup ejection, expiration and death cleanup have explicit event ordering. | REF interaction programme; #52. |
| PWR-024 | Kick/throw/line/remote action composition. | Capability combinations resolve control precedence and capacity with boundary-case fixtures. | Existing bomb commands and REF interactions. |
| PWR-025 | Conveyor/warp primitives. | Transport preserves occupancy, fuse time and legal exits under concurrent movement. | Stage-pack API. |
| PWR-026 | Curve/wrap/booster composition. | A known trajectory crosses redirection and arena links with deterministic timing and collision. | Arena layouts and stage-pack API. |
| PWR-027 | Trampolines/seesaws and vehicles. | Public data-driven objects define launch, landing, occupancy and interruption without arbitrary scripts. | Declarative content/runtime scope. |
| PWR-028 | Double-hit blocks and enemy generators. | Damage state and spawn schedules survive snapshot/replay with correct drops. | Destructibles/campaign-enemy APIs. |
| PWR-029 | Robo Bomber style moving hazard. | Authored path, obstruction, damage and visibility cues work across layouts and seat counts. | Stage objects; historical lead needs measurement. |
| PWR-030 | Large character library selection. | Compatible installed custom characters remain freely selectable and readable in twelve-seat rooms. | Character/community contract. |
| PWR-031 | Optional progression/save migration. | New build migrates a copied test save, retains prior version and recovers from malformed data. | Profiles/stats/save scope. |
| PWR-032 | Mixed-controller local play. | Ten and twelve supported mixed devices bind deterministically through hotplug and disconnect. | Existing input/local-seat scope. |
| PWR-033 | Additive visual/audio styles. | Two packs coexist without replacing base IDs; selected style locks into replay/session metadata. | Additions-only public pack API. |
| PWR-034 | Current full item/stage manual census. | Every discovered menu/manual ID has a source/build, limitations and linked interaction tasks. | #498, REF-001–014 and RPWR inventories. |
| PWR-035 | Comparable owned-server netplay experiment. | Equivalent local/online conditions retain latency, correction, load and outcome samples. | #45; netplay benchmark contract. |
| PWR-036 | Accessibility/device options audit. | Presence is directly checked; Neptune presentation assists identify differences while preserving simulation. | Community/accessibility scope. |

## Missing evidence and next bounded research

The largest remaining gap is the **current included manual**. A mirrored 0.7.3b
manual was found through search, but its page returned a client challenge [PB06].
It was not read and cannot support detailed item/option claims. Obtain the manual
from a developer-linked 0.7.8c archive, fingerprint it and enumerate actual IDs.

The developer-linked current changelog returned **“Paste not found”** when fetched
[PB05]. Its earlier accessibility in project documents does not establish that it
was readable during this survey. Preserve existing historical observations as
historical; do not describe absent changelog contents as newly inspected evidence.

No current archive was downloaded, no `data.win` analyzed, and no server run was
performed. Current exact character/arena/item counts, mode parameter values,
complete settings, CPU policies, protocol, authoring support and platform paths
therefore remain incomplete. Some historical features may have changed or been
removed. The next useful result is a build-pinned menu/manual inventory followed
by one controlled local scenario under the existing Power lab, after the current
factory/Saturn critical path or an already active bounded owner permits it.

## Sources and access record

All access dates below are **3 November 2026**. Direct URLs are retained because
forum titles, editable first posts and external downloads can change.

- **PB01 — developer release thread and historical first-page posts:**
  <https://www.bombermanboard.com/viewtopic.php?t=1925>.
  Successfully fetched. Main source for current 0.7.8c identity, advertised
  counts/options and 2013 historical statements. User posts are distinguished
  from developer posts throughout this chapter.
- **PB02 — final release-thread page, posts #901–917:**
  <https://www.bombermanboard.com/viewtopic.php?start=900&t=1925>.
  Successfully fetched. Developer 0.7.8b/hotfix/save statements and 2026 public
  reports/questions. User diagnoses and requests are discovery leads only.
- **PB03 — SAGE 2022 Power Bomberman 0.7.7c showcase:**
  <https://sonicfangameshq.com/forums/showcase/power-bomberman-0-7-7c.1491/>.
  Successfully fetched. Explicit concise objectives for six rules, older content
  advertisements, Score/Turbo and Louies. Contains the noted five-versus-six
  heading inconsistency.
- **PB04 — mod author's Power Bomberman Styles page:**
  <https://www.moddb.com/mods/power-bomberman-styles-mods>.
  Successfully fetched. Evidence of replacement graphics/sound modifications,
  installation instructions and named 0.7.7c style examples; not proof of an
  official pack API or current compatibility.
- **PB05 — developer-linked 0.7.8c changelog:**
  <https://pastee.dev/p/5XtRWu50>.
  Fetched page says “Paste not found”; changelog text unavailable in this survey.
- **PB06 — search-discovered older mirrored manual:**
  <https://www.scribd.com/document/672718035/at-least-skim-over-this-please>.
  Search identifies a 0.7.3b guide; fetch returned “Client Challenge.” Not used
  as evidence for manual contents.

This chapter expands discoverable Power features and future acceptance questions.
It does not certify every feature, current compatibility or Neptune parity.

[PB01]: https://www.bombermanboard.com/viewtopic.php?t=1925
[PB02]: https://www.bombermanboard.com/viewtopic.php?start=900&t=1925
[PB03]: https://sonicfangameshq.com/forums/showcase/power-bomberman-0-7-7c.1491/
[PB04]: https://www.moddb.com/mods/power-bomberman-styles-mods
[PB05]: https://pastee.dev/p/5XtRWu50
[PB06]: https://www.scribd.com/document/672718035/at-least-skim-over-this-please
