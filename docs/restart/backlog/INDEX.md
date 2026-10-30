# Feature issue index

Master roadmap: [#69](https://github.com/elgansayer/Neptune-Bomberman/issues/69). 418 bounded feature specifications across 29 domains.

This is a planning index, not a completion report. Dependency edges in `catalogue.json` take precedence over suggested waves. Existing issues are reused where their scope matches.

## RSAT: Saturn code, extraction and original execution

| ID | Priority / wave | Feature | GitHub |
| --- | --- | --- | --- |
| RSAT-001 | P0 / 1 | Evaluate and reuse the existing AI-assisted Saturn Bomberman recompilation | [#478](https://github.com/elgansayer/Neptune-Bomberman/issues/478) |
| RSAT-002 | P1 / 1 | Benchmark emulator debugging and extraction capabilities | [#479](https://github.com/elgansayer/Neptune-Bomberman/issues/479) |
| RSAT-003 | P1 / 1 | Map every Saturn executable module, overlay and code-bearing bank | [#480](https://github.com/elgansayer/Neptune-Bomberman/issues/480) |
| RSAT-004 | P1 / 1 | Create reproducible Ghidra projects and validated Saturn symbols | [#481](https://github.com/elgansayer/Neptune-Bomberman/issues/481) |
| RSAT-005 | P1 / 1 | Instrument bounded instruction, memory, DMA and resource-load traces | [#482](https://github.com/elgansayer/Neptune-Bomberman/issues/482) |
| RSAT-006 | P1 / 1 | Validate recovered Saturn functions through decompilation and recompilation | [#483](https://github.com/elgansayer/Neptune-Bomberman/issues/483) |
| RSAT-007 | P0 / 1 | Decode PROGRAM.BIN banks against their resident memory images | [#484](https://github.com/elgansayer/Neptune-Bomberman/issues/484) |
| RSAT-008 | P0 / 1 | Capture and reconstruct VDP1 textures, palettes and draw commands | [#485](https://github.com/elgansayer/Neptune-Bomberman/issues/485) |
| RSAT-009 | P1 / 1 | Capture and reconstruct VDP2 tiles, maps and backgrounds | [#486](https://github.com/elgansayer/Neptune-Bomberman/issues/486) |
| RSAT-010 | P1 / 1 | Compile faithful sprite atlases and animation state metadata | [#487](https://github.com/elgansayer/Neptune-Bomberman/issues/487) |
| RSAT-011 | P1 / 1 | Recover SCSP samples, sequences, sound drivers and trigger semantics | [#488](https://github.com/elgansayer/Neptune-Bomberman/issues/488) |
| RSAT-012 | P1 / 1 | Decode CD audio, FILM movies and streamed audio with exact timing | [#489](https://github.com/elgansayer/Neptune-Bomberman/issues/489) |
| RSAT-013 | P1 / 1 | Build autonomous original-game navigation and campaign/battle exploration | [#490](https://github.com/elgansayer/Neptune-Bomberman/issues/490) |
| RSAT-014 | P1 / 1 | Expose validated typed observations from Saturn game state | [#491](https://github.com/elgansayer/Neptune-Bomberman/issues/491) |
| RSAT-015 | P1 / 1 | Recover Saturn RNG, task scheduling and timing domains | [#492](https://github.com/elgansayer/Neptune-Bomberman/issues/492) |
| RSAT-016 | P1 / 1 | Measure exact Saturn movement, bomb and collision contracts | [#493](https://github.com/elgansayer/Neptune-Bomberman/issues/493) |
| RSAT-017 | P1 / 1 | Recover Saturn save, continue and campaign persistence formats | [#494](https://github.com/elgansayer/Neptune-Bomberman/issues/494) |
| RSAT-018 | P1 / 1 | Recover UI, text, fonts, camera and presentation state machines | [#495](https://github.com/elgansayer/Neptune-Bomberman/issues/495) |
| RSAT-019 | P1 / 1 | Reverse-engineer Saturn NetLink and XBAND code and resources offline | [#496](https://github.com/elgansayer/Neptune-Bomberman/issues/496) |
| RSAT-020 | P1 / 1 | Account for hidden, unused and dynamically discovered Saturn code/content | [#497](https://github.com/elgansayer/Neptune-Bomberman/issues/497) |

## RPWR: Power code, extraction and original execution

| ID | Priority / wave | Feature | GitHub |
| --- | --- | --- | --- |
| RPWR-001 | P0 / 1 | Identify Power binaries and reconcile existing GameMaker exports | [#498](https://github.com/elgansayer/Neptune-Bomberman/issues/498) |
| RPWR-002 | P1 / 1 | Recover Power gameplay code, object events and call graphs | [#499](https://github.com/elgansayer/Neptune-Bomberman/issues/499) |
| RPWR-003 | P1 / 1 | Extract Power texture pages, characters and animation metadata | [#500](https://github.com/elgansayer/Neptune-Bomberman/issues/500) |
| RPWR-004 | P1 / 1 | Extract Power audio, fonts, text and interface resources | [#501](https://github.com/elgansayer/Neptune-Bomberman/issues/501) |
| RPWR-005 | P1 / 1 | Recover Power room layouts, stages, hazards and variant data | [#502](https://github.com/elgansayer/Neptune-Bomberman/issues/502) |
| RPWR-006 | P1 / 1 | Instrument Power updates, inputs, RNG and deterministic experiment boundaries | [#503](https://github.com/elgansayer/Neptune-Bomberman/issues/503) |
| RPWR-007 | P1 / 1 | Recover Power mode, scoring, progression and reset state machines | [#504](https://github.com/elgansayer/Neptune-Bomberman/issues/504) |
| RPWR-008 | P1 / 1 | Recover Power CPU policies and difficulty behaviour | [#505](https://github.com/elgansayer/Neptune-Bomberman/issues/505) |
| RPWR-009 | P1 / 1 | Recover the Power local client/server protocol and synchronisation | [#506](https://github.com/elgansayer/Neptune-Bomberman/issues/506) |
| RPWR-010 | P1 / 1 | Reverse-engineer Power custom-content formats and authoring workflows | [#507](https://github.com/elgansayer/Neptune-Bomberman/issues/507) |

## RLAB: Research tooling, evidence and factory integration

| ID | Priority / wave | Feature | GitHub |
| --- | --- | --- | --- |
| RLAB-001 | P1 / 1 | Build tested reusable research skills and local analysis adapters | [#508](https://github.com/elgansayer/Neptune-Bomberman/issues/508) |
| RLAB-002 | P1 / 1 | Maintain a verified prior-art and research-source registry | [#509](https://github.com/elgansayer/Neptune-Bomberman/issues/509) |
| RLAB-003 | P0 / 1 | Route Saturn and Power research jobs through the existing Repo Factory | [#510](https://github.com/elgansayer/Neptune-Bomberman/issues/510) |
| RLAB-004 | P0 / 1 | Verify private reference experiments through trusted reproducible receipts | [#511](https://github.com/elgansayer/Neptune-Bomberman/issues/511) |
| RLAB-005 | P0 / 1 | Publish extracted content to the private assets repository with regeneration gates | [#512](https://github.com/elgansayer/Neptune-Bomberman/issues/512) |
| RLAB-006 | P1 / 1 | Reproduce reference results across independent engines and measurement methods | [#513](https://github.com/elgansayer/Neptune-Bomberman/issues/513) |
| RLAB-007 | P1 / 1 | Recover long-running research safely within disk and provider budgets | [#514](https://github.com/elgansayer/Neptune-Bomberman/issues/514) |
| RLAB-008 | P1 / 1 | Prove whole-program and content reconstruction coverage without false completeness | [#515](https://github.com/elgansayer/Neptune-Bomberman/issues/515) |

## REF: Reference research and exhaustive inventories

| ID | Priority / wave | Feature | GitHub |
| --- | --- | --- | --- |
| REF-001 | P1 / 1 | Pin regional Saturn releases and timing profiles | [#394](https://github.com/elgansayer/Neptune-Bomberman/issues/394) |
| REF-002 | P1 / 1 | Index every Saturn campaign room and transition | [#395](https://github.com/elgansayer/Neptune-Bomberman/issues/395) |
| REF-003 | P1 / 1 | Index every Saturn enemy and boss phase | [#396](https://github.com/elgansayer/Neptune-Bomberman/issues/396) |
| REF-004 | P1 / 1 | Index Saturn battle stages and hidden variants | [#397](https://github.com/elgansayer/Neptune-Bomberman/issues/397) |
| REF-005 | P1 / 1 | Inventory Saturn items and illnesses by mode | [#398](https://github.com/elgansayer/Neptune-Bomberman/issues/398) |
| REF-006 | P1 / 1 | Inventory Saturn animation and sound states | [#399](https://github.com/elgansayer/Neptune-Bomberman/issues/399) |
| REF-007 | P1 / 1 | Pin the current Power manual and settings inventory | [#400](https://github.com/elgansayer/Neptune-Bomberman/issues/400) |
| REF-008 | P1 / 1 | Inventory Power items and combination rules | [#402](https://github.com/elgansayer/Neptune-Bomberman/issues/402) |
| REF-009 | P1 / 1 | Inventory Power stages and variant restrictions | [#405](https://github.com/elgansayer/Neptune-Bomberman/issues/405) |
| REF-010 | P1 / 1 | Inventory Power characters and presentation metadata | [#406](https://github.com/elgansayer/Neptune-Bomberman/issues/406) |
| REF-011 | P1 / 1 | Create a reference interaction experiment matrix | [#407](https://github.com/elgansayer/Neptune-Bomberman/issues/407) |
| REF-012 | P1 / 1 | Reconcile video claims with playable references | [#408](https://github.com/elgansayer/Neptune-Bomberman/issues/408) |
| REF-013 | P1 / 1 | Maintain evidence confidence and coverage reports | [#409](https://github.com/elgansayer/Neptune-Bomberman/issues/409) |
| REF-014 | P1 / 1 | Generate bounded tasks from verified content inventories | [#410](https://github.com/elgansayer/Neptune-Bomberman/issues/410) |

## SIM: Authoritative simulation

| ID | Priority / wave | Feature | GitHub |
| --- | --- | --- | --- |
| SIM-001 | P1 / 1 | Drive gameplay from an authoritative simulation clock | [#86](https://github.com/elgansayer/Neptune-Bomberman/issues/86) |
| SIM-002 | P1 / 1 | Partition seeded random streams by subsystem | [#87](https://github.com/elgansayer/Neptune-Bomberman/issues/87) |
| SIM-003 | P1 / 1 | Define deterministic simultaneous-event ordering | [#88](https://github.com/elgansayer/Neptune-Bomberman/issues/88) |
| SIM-004 | P1 / 1 | Validate human and bot actions through one command path | [#91](https://github.com/elgansayer/Neptune-Bomberman/issues/91) |
| SIM-005 | P1 / 1 | Implement fixed-point movement and corner assistance profiles | [#89](https://github.com/elgansayer/Neptune-Bomberman/issues/89) |
| SIM-006 | P1 / 1 | Specify tile occupancy and collision layers | [#90](https://github.com/elgansayer/Neptune-Bomberman/issues/90) |
| SIM-007 | P1 / 1 | Implement spawn selection and safe spawn reservations | [#100](https://github.com/elgansayer/Neptune-Bomberman/issues/100) |
| SIM-008 | P1 / 1 | Make entity identities stable across snapshots | [#101](https://github.com/elgansayer/Neptune-Bomberman/issues/101) |
| SIM-009 | P1 / 1 | Implement damage attribution and elimination events | [#102](https://github.com/elgansayer/Neptune-Bomberman/issues/102) |
| SIM-010 | P1 / 1 | Define lives, hearts and invulnerability lifecycle | [#103](https://github.com/elgansayer/Neptune-Bomberman/issues/103) |
| SIM-011 | P1 / 1 | Implement round start, countdown and clean reset | [#104](https://github.com/elgansayer/Neptune-Bomberman/issues/104) |
| SIM-012 | P1 / 1 | Resolve wins, draws and team elimination atomically | [#105](https://github.com/elgansayer/Neptune-Bomberman/issues/105) |
| SIM-013 | P1 / 1 | Expose simulation snapshots and state hashes | [#106](https://github.com/elgansayer/Neptune-Bomberman/issues/106) |
| SIM-014 | P1 / 1 | Add bounded event queues and entity budgets | [#107](https://github.com/elgansayer/Neptune-Bomberman/issues/107) |
| SIM-015 | P1 / 1 | Version gameplay protocol and save schemas | [#108](https://github.com/elgansayer/Neptune-Bomberman/issues/108) |
| SIM-016 | P1 / 1 | Implement pause and time-scale rules by session type | [#109](https://github.com/elgansayer/Neptune-Bomberman/issues/109) |

## BOMB: Bomb mechanics

| ID | Priority / wave | Feature | GitHub |
| --- | --- | --- | --- |
| BOMB-001 | P1 / 2 | Specify normal bomb placement and owner overlap | [#147](https://github.com/elgansayer/Neptune-Bomberman/issues/147) |
| BOMB-002 | P1 / 2 | Specify fuse expiry and flame lifetime profiles | [#148](https://github.com/elgansayer/Neptune-Bomberman/issues/148) |
| BOMB-003 | P1 / 2 | Resolve multi-bomb chains and ownership | [#150](https://github.com/elgansayer/Neptune-Bomberman/issues/150) |
| BOMB-004 | P1 / 2 | Define solid and destructible blast obstruction | [#149](https://github.com/elgansayer/Neptune-Bomberman/issues/149) |
| BOMB-005 | P1 / 2 | Implement bomb kicking and deliberate stopping | [#157](https://github.com/elgansayer/Neptune-Bomberman/issues/157) |
| BOMB-006 | P1 / 2 | Implement pickup and carried-bomb lifecycle | [#158](https://github.com/elgansayer/Neptune-Bomberman/issues/158) |
| BOMB-007 | P1 / 2 | Implement throws, landing and chained bounces | [#159](https://github.com/elgansayer/Neptune-Bomberman/issues/159) |
| BOMB-008 | P1 / 2 | Implement wraparound bomb trajectories | [#201](https://github.com/elgansayer/Neptune-Bomberman/issues/201) |
| BOMB-009 | P1 / 2 | Implement remote detonation ownership | [#161](https://github.com/elgansayer/Neptune-Bomberman/issues/161) |
| BOMB-010 | P1 / 2 | Implement penetrating power bombs | [#163](https://github.com/elgansayer/Neptune-Bomberman/issues/163) |
| BOMB-011 | P1 / 2 | Implement rubber and bouncing bomb profiles | [#164](https://github.com/elgansayer/Neptune-Bomberman/issues/164) |
| BOMB-012 | P1 / 2 | Implement line-bomb placement | [#165](https://github.com/elgansayer/Neptune-Bomberman/issues/165) |
| BOMB-013 | P1 / 2 | Investigate bead or rolling-chain bomb mechanics | [#403](https://github.com/elgansayer/Neptune-Bomberman/issues/403) |
| BOMB-014 | P1 / 2 | Implement landmine placement and triggering | [#166](https://github.com/elgansayer/Neptune-Bomberman/issues/166) |
| BOMB-015 | P1 / 2 | Investigate dangerous bomb fusion | [#404](https://github.com/elgansayer/Neptune-Bomberman/issues/404) |
| BOMB-016 | P1 / 2 | Implement bomb punch and aerial redirection | [#167](https://github.com/elgansayer/Neptune-Bomberman/issues/167) |
| BOMB-017 | P1 / 2 | Implement bomb pushing and collision arbitration | [#168](https://github.com/elgansayer/Neptune-Bomberman/issues/168) |
| BOMB-018 | P1 / 2 | Specify fire interactions with moving and carried bombs | [#169](https://github.com/elgansayer/Neptune-Bomberman/issues/169) |
| BOMB-019 | P1 / 2 | Implement bomb preview and placement feedback | [#170](https://github.com/elgansayer/Neptune-Bomberman/issues/170) |

## ITEM: Items, abilities and illnesses

| ID | Priority / wave | Feature | GitHub |
| --- | --- | --- | --- |
| ITEM-001 | P2 / 2 | Implement item pools and weighted hidden drops | [#205](https://github.com/elgansayer/Neptune-Bomberman/issues/205) |
| ITEM-002 | P2 / 2 | Implement bomb-capacity upgrades and caps | [#206](https://github.com/elgansayer/Neptune-Bomberman/issues/206) |
| ITEM-003 | P2 / 2 | Implement fire-range upgrades and Full Fire | [#207](https://github.com/elgansayer/Neptune-Bomberman/issues/207) |
| ITEM-004 | P2 / 2 | Implement skate upgrades and speed reduction items | [#208](https://github.com/elgansayer/Neptune-Bomberman/issues/208) |
| ITEM-005 | P2 / 2 | Implement kick, glove and line-bomb ability pickups | [#209](https://github.com/elgansayer/Neptune-Bomberman/issues/209) |
| ITEM-006 | P2 / 2 | Implement heart and shield protection rules | [#210](https://github.com/elgansayer/Neptune-Bomberman/issues/210) |
| ITEM-007 | P2 / 2 | Implement temporary invincibility and flashing feedback | [#211](https://github.com/elgansayer/Neptune-Bomberman/issues/211) |
| ITEM-008 | P2 / 2 | Implement illness/status selection and transmission | [#212](https://github.com/elgansayer/Neptune-Bomberman/issues/212) |
| ITEM-009 | P2 / 2 | Implement short-fuse and long-fuse illnesses | [#213](https://github.com/elgansayer/Neptune-Bomberman/issues/213) |
| ITEM-010 | P2 / 2 | Implement forced-planting and inability-to-plant illnesses | [#214](https://github.com/elgansayer/Neptune-Bomberman/issues/214) |
| ITEM-011 | P2 / 2 | Implement slow, fast and reversed-control illnesses | [#215](https://github.com/elgansayer/Neptune-Bomberman/issues/215) |
| ITEM-012 | P2 / 2 | Implement range/capacity restriction illnesses | [#216](https://github.com/elgansayer/Neptune-Bomberman/issues/216) |
| ITEM-013 | P2 / 2 | Implement illness cleansing and global Devil-style events | [#217](https://github.com/elgansayer/Neptune-Bomberman/issues/217) |
| ITEM-014 | P2 / 2 | Implement item scatter and loss on damage | [#218](https://github.com/elgansayer/Neptune-Bomberman/issues/218) |
| ITEM-015 | P2 / 2 | Implement item burn, relocation and respawn rules | [#219](https://github.com/elgansayer/Neptune-Bomberman/issues/219) |
| ITEM-016 | P2 / 2 | Implement score pickups and combo accounting | [#220](https://github.com/elgansayer/Neptune-Bomberman/issues/220) |
| ITEM-017 | P2 / 2 | Implement clock and time-stop effects | [#221](https://github.com/elgansayer/Neptune-Bomberman/issues/221) |
| ITEM-018 | P2 / 2 | Implement block-pass and bomb-pass abilities | [#222](https://github.com/elgansayer/Neptune-Bomberman/issues/222) |
| ITEM-019 | P2 / 2 | Implement limited-use dash and movement abilities | [#223](https://github.com/elgansayer/Neptune-Bomberman/issues/223) |
| ITEM-020 | P2 / 2 | Implement item-slot action priority and selection | [#224](https://github.com/elgansayer/Neptune-Bomberman/issues/224) |
| ITEM-021 | P2 / 2 | Implement pickup race and team sharing policies | [#225](https://github.com/elgansayer/Neptune-Bomberman/issues/225) |
| ITEM-022 | P2 / 2 | Build item help and interactive demonstrations | [#226](https://github.com/elgansayer/Neptune-Bomberman/issues/226) |

## MOUNT: Mounts and companions

| ID | Priority / wave | Feature | GitHub |
| --- | --- | --- | --- |
| MOUNT-001 | P2 / 3 | Implement reusable mount and rider state | [#293](https://github.com/elgansayer/Neptune-Bomberman/issues/293) |
| MOUNT-002 | P2 / 3 | Implement eggs, hatching and growth progression | [#296](https://github.com/elgansayer/Neptune-Bomberman/issues/296) |
| MOUNT-003 | P2 / 3 | Implement blue Tirra-style bomb launch capability | [#297](https://github.com/elgansayer/Neptune-Bomberman/issues/297) |
| MOUNT-004 | P2 / 3 | Implement green Tirra-style dash capability | [#298](https://github.com/elgansayer/Neptune-Bomberman/issues/298) |
| MOUNT-005 | P2 / 3 | Implement yellow Tirra-style stun capability | [#299](https://github.com/elgansayer/Neptune-Bomberman/issues/299) |
| MOUNT-006 | P2 / 3 | Implement pink Tirra-style jump capability | [#300](https://github.com/elgansayer/Neptune-Bomberman/issues/300) |
| MOUNT-007 | P2 / 3 | Implement purple Tirra-style sonar capability | [#301](https://github.com/elgansayer/Neptune-Bomberman/issues/301) |
| MOUNT-008 | P2 / 3 | Implement mount damage and sacrifice lifecycle | [#302](https://github.com/elgansayer/Neptune-Bomberman/issues/302) |
| MOUNT-009 | P2 / 3 | Inventory Power Louie and other steed abilities | [#401](https://github.com/elgansayer/Neptune-Bomberman/issues/401) |
| MOUNT-010 | P2 / 3 | Expose community-authored mounts through packs | [#303](https://github.com/elgansayer/Neptune-Bomberman/issues/303) |

## ARENA: Maps, terrain and stage mechanisms

| ID | Priority / wave | Feature | GitHub |
| --- | --- | --- | --- |
| ARENA-001 | P2 / 2 | Implement logical tile layers and visual themes | [#185](https://github.com/elgansayer/Neptune-Bomberman/issues/185) |
| ARENA-002 | P2 / 2 | Implement normal and wide arena layouts | [#186](https://github.com/elgansayer/Neptune-Bomberman/issues/186) |
| ARENA-003 | P2 / 2 | Implement destructible block variants | [#187](https://github.com/elgansayer/Neptune-Bomberman/issues/187) |
| ARENA-004 | P2 / 2 | Implement conveyor belts | [#188](https://github.com/elgansayer/Neptune-Bomberman/issues/188) |
| ARENA-005 | P2 / 2 | Implement warp pads and teleport routing | [#189](https://github.com/elgansayer/Neptune-Bomberman/issues/189) |
| ARENA-006 | P2 / 2 | Implement directional arrows and bomb curve tiles | [#190](https://github.com/elgansayer/Neptune-Bomberman/issues/190) |
| ARENA-007 | P2 / 2 | Implement trampolines, launchers and seesaws | [#191](https://github.com/elgansayer/Neptune-Bomberman/issues/191) |
| ARENA-008 | P2 / 2 | Implement rails, carts and moving platforms | [#192](https://github.com/elgansayer/Neptune-Bomberman/issues/192) |
| ARENA-009 | P2 / 2 | Implement doors, switches and rotating barriers | [#193](https://github.com/elgansayer/Neptune-Bomberman/issues/193) |
| ARENA-010 | P2 / 2 | Implement ice, water, lava and terrain effects | [#194](https://github.com/elgansayer/Neptune-Bomberman/issues/194) |
| ARENA-011 | P2 / 2 | Implement timed lasers, vents and floor traps | [#195](https://github.com/elgansayer/Neptune-Bomberman/issues/195) |
| ARENA-012 | P2 / 2 | Implement moving stage enemies and large obstacles | [#196](https://github.com/elgansayer/Neptune-Bomberman/issues/196) |
| ARENA-013 | P2 / 2 | Implement pressure-block patterns and warnings | [#197](https://github.com/elgansayer/Neptune-Bomberman/issues/197) |
| ARENA-014 | P2 / 2 | Implement collapsing floors and shrinking arenas | [#198](https://github.com/elgansayer/Neptune-Bomberman/issues/198) |
| ARENA-015 | P2 / 2 | Implement vertical layers and height restrictions | [#199](https://github.com/elgansayer/Neptune-Bomberman/issues/199) |
| ARENA-016 | P2 / 2 | Implement wraparound arena topology | [#200](https://github.com/elgansayer/Neptune-Bomberman/issues/200) |
| ARENA-017 | P2 / 2 | Implement arena variants and deterministic presets | [#262](https://github.com/elgansayer/Neptune-Bomberman/issues/262) |
| ARENA-018 | P2 / 2 | Implement seeded procedural arena generation | [#203](https://github.com/elgansayer/Neptune-Bomberman/issues/203) |
| ARENA-019 | P2 / 2 | Implement arena reachability and spawn fairness checks | [#202](https://github.com/elgansayer/Neptune-Bomberman/issues/202) |
| ARENA-020 | P2 / 2 | Implement hazard composition and event ordering | [#204](https://github.com/elgansayer/Neptune-Bomberman/issues/204) |

## BATTLE: Battle modes and rules

| ID | Priority / wave | Feature | GitHub |
| --- | --- | --- | --- |
| BATTLE-001 | P1 / 2 | Implement configurable free-for-all survival | [#133](https://github.com/elgansayer/Neptune-Bomberman/issues/133) |
| BATTLE-002 | P1 / 2 | Implement team survival and friendly-fire profiles | [#134](https://github.com/elgansayer/Neptune-Bomberman/issues/134) |
| BATTLE-003 | P1 / 2 | Implement tile-conversion Reversi battles | [#44](https://github.com/elgansayer/Neptune-Bomberman/issues/44) |
| BATTLE-004 | P1 / 2 | Implement Dodge-style avoidance battles | [#135](https://github.com/elgansayer/Neptune-Bomberman/issues/135) |
| BATTLE-005 | P1 / 2 | Implement Hyper Bomber-style objective battles | [#136](https://github.com/elgansayer/Neptune-Bomberman/issues/136) |
| BATTLE-006 | P1 / 2 | Implement King-style scoring battles | [#137](https://github.com/elgansayer/Neptune-Bomberman/issues/137) |
| BATTLE-007 | P1 / 2 | Implement Battle Royale rule profiles | [#138](https://github.com/elgansayer/Neptune-Bomberman/issues/138) |
| BATTLE-008 | P1 / 2 | Implement elimination revenge vehicles | [#160](https://github.com/elgansayer/Neptune-Bomberman/issues/160) |
| BATTLE-009 | P1 / 2 | Implement sudden-death and overtime options | [#139](https://github.com/elgansayer/Neptune-Bomberman/issues/139) |
| BATTLE-010 | P1 / 2 | Implement a configurable series and points table | [#141](https://github.com/elgansayer/Neptune-Bomberman/issues/141) |
| BATTLE-011 | P1 / 2 | Implement stage voting, shuffle and rotation | [#140](https://github.com/elgansayer/Neptune-Bomberman/issues/140) |
| BATTLE-012 | P1 / 2 | Implement starting loadouts and item bans | [#142](https://github.com/elgansayer/Neptune-Bomberman/issues/142) |
| BATTLE-013 | P1 / 2 | Implement handicaps and asymmetric teams | [#143](https://github.com/elgansayer/Neptune-Bomberman/issues/143) |
| BATTLE-014 | P1 / 2 | Implement training matches and restart controls | [#144](https://github.com/elgansayer/Neptune-Bomberman/issues/144) |
| BATTLE-015 | P1 / 2 | Implement original capture-the-flag battles | [#145](https://github.com/elgansayer/Neptune-Bomberman/issues/145) |
| BATTLE-016 | P1 / 2 | Implement original payload and zone-control battles | [#146](https://github.com/elgansayer/Neptune-Bomberman/issues/146) |

## SATURN: Saturn campaign, Master and presentation

| ID | Priority / wave | Feature | GitHub |
| --- | --- | --- | --- |
| SATURN-001 | P2 / 5 | Build Saturn Normal-mode campaign progression | [#417](https://github.com/elgansayer/Neptune-Bomberman/issues/417) |
| SATURN-002 | P2 / 5 | Build Saturn Normal-mode two-player rules | [#418](https://github.com/elgansayer/Neptune-Bomberman/issues/418) |
| SATURN-003 | P2 / 5 | Implement Saturn Master-mode stage progression | [#419](https://github.com/elgansayer/Neptune-Bomberman/issues/419) |
| SATURN-004 | P2 / 5 | Implement Master-mode grading and score breakdown | [#420](https://github.com/elgansayer/Neptune-Bomberman/issues/420) |
| SATURN-005 | P2 / 5 | Implement campaign enemy spawning and room clear rules | [#421](https://github.com/elgansayer/Neptune-Bomberman/issues/421) |
| SATURN-006 | P2 / 5 | Implement campaign bosses with explicit phase graphs | [#422](https://github.com/elgansayer/Neptune-Bomberman/issues/422) |
| SATURN-007 | P2 / 5 | Implement campaign cutscenes and transition timing | [#423](https://github.com/elgansayer/Neptune-Bomberman/issues/423) |
| SATURN-008 | P2 / 5 | Implement campaign secrets and bonus entrances | [#424](https://github.com/elgansayer/Neptune-Bomberman/issues/424) |
| SATURN-009 | P2 / 5 | Implement the Saturn bonus-game framework | [#425](https://github.com/elgansayer/Neptune-Bomberman/issues/425) |
| SATURN-010 | P2 / 5 | Implement Saturn battle setup options | [#426](https://github.com/elgansayer/Neptune-Bomberman/issues/426) |
| SATURN-011 | P2 / 5 | Implement Saturn hidden settings and selection gestures | [#427](https://github.com/elgansayer/Neptune-Bomberman/issues/427) |
| SATURN-012 | P2 / 5 | Implement Saturn save, continue and game-over behaviour | [#428](https://github.com/elgansayer/Neptune-Bomberman/issues/428) |
| SATURN-013 | P2 / 5 | Implement Saturn presentation and camera comparisons | [#429](https://github.com/elgansayer/Neptune-Bomberman/issues/429) |
| SATURN-014 | P2 / 5 | Implement Saturn CPU behaviour comparison scenarios | [#430](https://github.com/elgansayer/Neptune-Bomberman/issues/430) |

## POWER: Power-inspired profiles and modes

| ID | Priority / wave | Feature | GitHub |
| --- | --- | --- | --- |
| POWER-001 | P2 / 5 | Implement the pinned Power battle preset library | [#411](https://github.com/elgansayer/Neptune-Bomberman/issues/411) |
| POWER-002 | P2 / 5 | Implement Power Score-mode progression | [#412](https://github.com/elgansayer/Neptune-Bomberman/issues/412) |
| POWER-003 | P2 / 5 | Implement Power Turbo timing and progression | [#413](https://github.com/elgansayer/Neptune-Bomberman/issues/413) |
| POWER-004 | P2 / 5 | Implement Power character-selection ergonomics | [#414](https://github.com/elgansayer/Neptune-Bomberman/issues/414) |
| POWER-005 | P2 / 5 | Implement Power taunts and battle expressions | [#415](https://github.com/elgansayer/Neptune-Bomberman/issues/415) |
| POWER-006 | P2 / 5 | Implement Power settings compatibility reports | [#416](https://github.com/elgansayer/Neptune-Bomberman/issues/416) |

## BOT: Competitive bots, companions and enemies

| ID | Priority / wave | Feature | GitHub |
| --- | --- | --- | --- |
| BOT-001 | P0 / 1 | Provide bots with an explicit public observation model | [#92](https://github.com/elgansayer/Neptune-Bomberman/issues/92) |
| BOT-002 | P0 / 1 | Predict space-time danger for all supported hazards | [#151](https://github.com/elgansayer/Neptune-Bomberman/issues/151) |
| BOT-003 | P0 / 1 | Plan escape routes with travel and reaction time | [#152](https://github.com/elgansayer/Neptune-Bomberman/issues/152) |
| BOT-004 | P0 / 1 | Require a viable post-placement escape plan | [#153](https://github.com/elgansayer/Neptune-Bomberman/issues/153) |
| BOT-005 | P0 / 1 | Coordinate path reservations between team bots | [#154](https://github.com/elgansayer/Neptune-Bomberman/issues/154) |
| BOT-006 | P0 / 1 | Plan destructible-block farming and item collection | [#155](https://github.com/elgansayer/Neptune-Bomberman/issues/155) |
| BOT-007 | P0 / 1 | Build opponent-trapping and tactical bomb planning | [#156](https://github.com/elgansayer/Neptune-Bomberman/issues/156) |
| BOT-008 | P0 / 1 | Teach bots kick, carry, throw and remote abilities | [#162](https://github.com/elgansayer/Neptune-Bomberman/issues/162) |
| BOT-009 | P0 / 1 | Teach bots mounts, terrain and stage mechanisms | [#294](https://github.com/elgansayer/Neptune-Bomberman/issues/294) |
| BOT-010 | P0 / 1 | Create difficulty profiles without hidden-information cheats | [#93](https://github.com/elgansayer/Neptune-Bomberman/issues/93) |
| BOT-011 | P0 / 1 | Create distinct and reproducible bot personalities | [#94](https://github.com/elgansayer/Neptune-Bomberman/issues/94) |
| BOT-012 | P0 / 1 | Support companion follow, defend and assist commands | [#95](https://github.com/elgansayer/Neptune-Bomberman/issues/95) |
| BOT-013 | P0 / 1 | Support authored enemy perception and attack policies | [#96](https://github.com/elgansayer/Neptune-Bomberman/issues/96) |
| BOT-014 | P0 / 1 | Expose objectives to bots through a common interface | [#265](https://github.com/elgansayer/Neptune-Bomberman/issues/265) |
| BOT-015 | P0 / 1 | Recover bots from stuck, oscillating and invalid paths | [#97](https://github.com/elgansayer/Neptune-Bomberman/issues/97) |
| BOT-016 | P0 / 1 | Budget bot planning across large rooms | [#98](https://github.com/elgansayer/Neptune-Bomberman/issues/98) |
| BOT-017 | P0 / 1 | Build bot explanations and replay overlays | [#99](https://github.com/elgansayer/Neptune-Bomberman/issues/99) |
| BOT-018 | P0 / 1 | Build seeded bot tournaments and promotion thresholds | [#32](https://github.com/elgansayer/Neptune-Bomberman/issues/32) |

## ROOM: Rooms, parties and mixed participants

| ID | Priority / wave | Feature | GitHub |
| --- | --- | --- | --- |
| ROOM-001 | P0 / 2 | Implement twelve-seat extensible room capacity | [#121](https://github.com/elgansayer/Neptune-Bomberman/issues/121) |
| ROOM-002 | P0 / 2 | Implement local guest seats inside online rooms | [#122](https://github.com/elgansayer/Neptune-Bomberman/issues/122) |
| ROOM-003 | P0 / 2 | Implement host-controlled and automatic bot filling | [#31](https://github.com/elgansayer/Neptune-Bomberman/issues/31) |
| ROOM-004 | P0 / 2 | Implement public and private room discovery | [#123](https://github.com/elgansayer/Neptune-Bomberman/issues/123) |
| ROOM-005 | P0 / 2 | Implement invite codes and direct joins | [#124](https://github.com/elgansayer/Neptune-Bomberman/issues/124) |
| ROOM-006 | P0 / 2 | Implement ready checks with a frozen session contract | [#255](https://github.com/elgansayer/Neptune-Bomberman/issues/255) |
| ROOM-007 | P0 / 2 | Implement host transfer within a surviving server session | [#125](https://github.com/elgansayer/Neptune-Bomberman/issues/125) |
| ROOM-008 | P0 / 2 | Implement reconnect grace and seat reclaim | [#126](https://github.com/elgansayer/Neptune-Bomberman/issues/126) |
| ROOM-009 | P0 / 2 | Implement human-to-bot takeover and handback | [#128](https://github.com/elgansayer/Neptune-Bomberman/issues/128) |
| ROOM-010 | P0 / 2 | Implement spectator seats and admission rules | [#279](https://github.com/elgansayer/Neptune-Bomberman/issues/279) |
| ROOM-011 | P0 / 2 | Implement rematches and persistent room settings | [#129](https://github.com/elgansayer/Neptune-Bomberman/issues/129) |
| ROOM-012 | P0 / 2 | Implement room moderation and host permissions | [#130](https://github.com/elgansayer/Neptune-Bomberman/issues/130) |
| ROOM-013 | P0 / 2 | Implement room region and server selection | [#131](https://github.com/elgansayer/Neptune-Bomberman/issues/131) |
| ROOM-014 | P0 / 2 | Implement queue matchmaking with party constraints | [#372](https://github.com/elgansayer/Neptune-Bomberman/issues/372) |
| ROOM-015 | P0 / 2 | Implement seamless late join policy by mode | [#323](https://github.com/elgansayer/Neptune-Bomberman/issues/323) |
| ROOM-016 | P0 / 2 | Implement authoritative room lifecycle and cleanup | [#132](https://github.com/elgansayer/Neptune-Bomberman/issues/132) |

## NET: Browser/native networking and cross-play

| ID | Priority / wave | Feature | GitHub |
| --- | --- | --- | --- |
| NET-001 | P0 / 2 | Provide browser and native transport parity | [#110](https://github.com/elgansayer/Neptune-Bomberman/issues/110) |
| NET-002 | P0 / 2 | Implement command sequencing and duplicate suppression | [#111](https://github.com/elgansayer/Neptune-Bomberman/issues/111) |
| NET-003 | P0 / 2 | Implement movement prediction and reconciliation | [#112](https://github.com/elgansayer/Neptune-Bomberman/issues/112) |
| NET-004 | P0 / 2 | Implement interpolation for remote actors and bombs | [#115](https://github.com/elgansayer/Neptune-Bomberman/issues/115) |
| NET-005 | P0 / 2 | Implement full and delta snapshot consistency | [#113](https://github.com/elgansayer/Neptune-Bomberman/issues/113) |
| NET-006 | P0 / 2 | Synchronise server time and input deadlines | [#114](https://github.com/elgansayer/Neptune-Bomberman/issues/114) |
| NET-007 | P3 / 6 | Define rollback scope and evaluate its tradeoffs | [#442](https://github.com/elgansayer/Neptune-Bomberman/issues/442) |
| NET-008 | P0 / 2 | Implement reconnect state resynchronisation | [#127](https://github.com/elgansayer/Neptune-Bomberman/issues/127) |
| NET-009 | P0 / 2 | Implement reliable event delivery and idempotence | [#116](https://github.com/elgansayer/Neptune-Bomberman/issues/116) |
| NET-010 | P0 / 2 | Benchmark netplay under controlled impairment | [#45](https://github.com/elgansayer/Neptune-Bomberman/issues/45) |
| NET-011 | P0 / 2 | Implement bandwidth and interest-management budgets | [#117](https://github.com/elgansayer/Neptune-Bomberman/issues/117) |
| NET-012 | P0 / 2 | Validate all client requests and rate limits | [#118](https://github.com/elgansayer/Neptune-Bomberman/issues/118) |
| NET-013 | P0 / 2 | Implement cross-platform determinism diagnostics | [#119](https://github.com/elgansayer/Neptune-Bomberman/issues/119) |
| NET-014 | P0 / 2 | Implement degraded-connection UX and recovery | [#120](https://github.com/elgansayer/Neptune-Bomberman/issues/120) |

## PACK: Portable community content platform

| ID | Priority / wave | Feature | GitHub |
| --- | --- | --- | --- |
| PACK-001 | P1 / 3 | Define versioned pack manifests and stable identifiers | [#237](https://github.com/elgansayer/Neptune-Bomberman/issues/237) |
| PACK-002 | P1 / 3 | Implement deterministic dependency resolution and locks | [#250](https://github.com/elgansayer/Neptune-Bomberman/issues/250) |
| PACK-003 | P1 / 3 | Implement content-addressed pack installation | [#252](https://github.com/elgansayer/Neptune-Bomberman/issues/252) |
| PACK-004 | P1 / 3 | Validate archive paths and expansion budgets | [#251](https://github.com/elgansayer/Neptune-Bomberman/issues/251) |
| PACK-005 | P1 / 3 | Implement pack capabilities and compatibility negotiation | [#254](https://github.com/elgansayer/Neptune-Bomberman/issues/254) |
| PACK-006 | P1 / 3 | Implement data-only resource loading boundaries | [#258](https://github.com/elgansayer/Neptune-Bomberman/issues/258) |
| PACK-007 | P1 / 3 | Define character sprite and animation contracts | [#259](https://github.com/elgansayer/Neptune-Bomberman/issues/259) |
| PACK-008 | P1 / 3 | Define character palettes, portraits and voice metadata | [#260](https://github.com/elgansayer/Neptune-Bomberman/issues/260) |
| PACK-009 | P1 / 3 | Separate cosmetic character identity from gameplay classes | [#266](https://github.com/elgansayer/Neptune-Bomberman/issues/266) |
| PACK-010 | P1 / 3 | Define portable map and tile-set schemas | [#261](https://github.com/elgansayer/Neptune-Bomberman/issues/261) |
| PACK-011 | P1 / 3 | Define portable item and bomb schemas | [#263](https://github.com/elgansayer/Neptune-Bomberman/issues/263) |
| PACK-012 | P1 / 3 | Define portable mode and ruleset schemas | [#264](https://github.com/elgansayer/Neptune-Bomberman/issues/264) |
| PACK-013 | P1 / 3 | Define campaign and encounter pack schemas | [#267](https://github.com/elgansayer/Neptune-Bomberman/issues/267) |
| PACK-014 | P1 / 3 | Implement pack upgrades, rollback and save compatibility | [#268](https://github.com/elgansayer/Neptune-Bomberman/issues/268) |
| PACK-015 | P1 / 3 | Implement pack enablement, profiles and conflict diagnostics | [#269](https://github.com/elgansayer/Neptune-Bomberman/issues/269) |
| PACK-016 | P1 / 3 | Migrate first-party fixtures to the public pack API | [#270](https://github.com/elgansayer/Neptune-Bomberman/issues/270) |
| PACK-017 | P1 / 3 | Publish a pack SDK, examples and command-line validator | [#271](https://github.com/elgansayer/Neptune-Bomberman/issues/271) |
| PACK-018 | P1 / 3 | Implement reproducible pack builds and provenance manifests | [#272](https://github.com/elgansayer/Neptune-Bomberman/issues/272) |

## EFFECT: Custom power-up and effect system

| ID | Priority / wave | Feature | GitHub |
| --- | --- | --- | --- |
| EFFECT-001 | P1 / 3 | Define a typed declarative effect graph | [#238](https://github.com/elgansayer/Neptune-Bomberman/issues/238) |
| EFFECT-002 | P1 / 3 | Implement effect triggers and filters | [#239](https://github.com/elgansayer/Neptune-Bomberman/issues/239) |
| EFFECT-003 | P1 / 3 | Implement stat modifiers with stacking policies | [#240](https://github.com/elgansayer/Neptune-Bomberman/issues/240) |
| EFFECT-004 | P1 / 3 | Implement bounded area and target queries | [#241](https://github.com/elgansayer/Neptune-Bomberman/issues/241) |
| EFFECT-005 | P1 / 3 | Implement projectile, hazard and entity spawn actions | [#242](https://github.com/elgansayer/Neptune-Bomberman/issues/242) |
| EFFECT-006 | P1 / 3 | Implement movement, teleport and force actions | [#243](https://github.com/elgansayer/Neptune-Bomberman/issues/243) |
| EFFECT-007 | P1 / 3 | Implement freeze and Ice Bomb as a complete example | [#52](https://github.com/elgansayer/Neptune-Bomberman/issues/52) |
| EFFECT-008 | P1 / 3 | Implement cooldowns, charges and consumable actions | [#244](https://github.com/elgansayer/Neptune-Bomberman/issues/244) |
| EFFECT-009 | P1 / 3 | Implement effect composition and conflict policies | [#245](https://github.com/elgansayer/Neptune-Bomberman/issues/245) |
| EFFECT-010 | P1 / 3 | Expose conservative bot forecasts for custom effects | [#246](https://github.com/elgansayer/Neptune-Bomberman/issues/246) |
| EFFECT-011 | P1 / 3 | Enforce per-pack runtime budgets and failure isolation | [#247](https://github.com/elgansayer/Neptune-Bomberman/issues/247) |
| EFFECT-012 | P1 / 3 | Add effect graph inspection and debugging traces | [#248](https://github.com/elgansayer/Neptune-Bomberman/issues/248) |
| EFFECT-013 | P1 / 3 | Version effect semantics and migration adapters | [#249](https://github.com/elgansayer/Neptune-Bomberman/issues/249) |
| EFFECT-014 | P3 / 6 | Evaluate a future sandboxed scripting extension | [#431](https://github.com/elgansayer/Neptune-Bomberman/issues/431) |

## STORY: Creator-authored solo campaigns

| ID | Priority / wave | Feature | GitHub |
| --- | --- | --- | --- |
| STORY-001 | P1 / 4 | Implement campaign graphs and branching transitions | [#318](https://github.com/elgansayer/Neptune-Bomberman/issues/318) |
| STORY-002 | P1 / 4 | Implement scoped campaign variables and conditions | [#329](https://github.com/elgansayer/Neptune-Bomberman/issues/329) |
| STORY-003 | P1 / 4 | Implement reusable quest and objective components | [#330](https://github.com/elgansayer/Neptune-Bomberman/issues/330) |
| STORY-004 | P1 / 4 | Implement dialogue, choices and localisation keys | [#331](https://github.com/elgansayer/Neptune-Bomberman/issues/331) |
| STORY-005 | P1 / 4 | Implement cutscene timelines and skip contracts | [#334](https://github.com/elgansayer/Neptune-Bomberman/issues/334) |
| STORY-006 | P1 / 4 | Implement NPC interaction and service templates | [#335](https://github.com/elgansayer/Neptune-Bomberman/issues/335) |
| STORY-007 | P1 / 4 | Implement encounters, waves and spawn directors | [#336](https://github.com/elgansayer/Neptune-Bomberman/issues/336) |
| STORY-008 | P1 / 4 | Implement reusable boss phase state machines | [#337](https://github.com/elgansayer/Neptune-Bomberman/issues/337) |
| STORY-009 | P1 / 4 | Implement keys, switches and cooperative puzzles | [#339](https://github.com/elgansayer/Neptune-Bomberman/issues/339) |
| STORY-010 | P1 / 4 | Implement checkpoint, retry and game-over policies | [#342](https://github.com/elgansayer/Neptune-Bomberman/issues/342) |
| STORY-011 | P1 / 4 | Implement campaign inventory and progression rewards | [#346](https://github.com/elgansayer/Neptune-Bomberman/issues/346) |
| STORY-012 | P1 / 4 | Implement chapter selection and completed-story replay | [#347](https://github.com/elgansayer/Neptune-Bomberman/issues/347) |
| STORY-013 | P1 / 4 | Implement campaign difficulty and accessibility modifiers | [#348](https://github.com/elgansayer/Neptune-Bomberman/issues/348) |
| STORY-014 | P1 / 4 | Implement authored endings and completion records | [#349](https://github.com/elgansayer/Neptune-Bomberman/issues/349) |
| STORY-015 | P1 / 4 | Implement campaign save slots and export/import | [#350](https://github.com/elgansayer/Neptune-Bomberman/issues/350) |
| STORY-016 | P1 / 4 | Implement procedural story episodes from authored pieces | [#351](https://github.com/elgansayer/Neptune-Bomberman/issues/351) |
| STORY-017 | P1 / 4 | Implement campaign content warnings and metadata | [#352](https://github.com/elgansayer/Neptune-Bomberman/issues/352) |
| STORY-018 | P1 / 4 | Build a complete original sample campaign | [#353](https://github.com/elgansayer/Neptune-Bomberman/issues/353) |

## COOP: Local and online co-op stories

| ID | Priority / wave | Feature | GitHub |
| --- | --- | --- | --- |
| COOP-001 | P1 / 4 | Define explicit co-op campaign compatibility | [#319](https://github.com/elgansayer/Neptune-Bomberman/issues/319) |
| COOP-002 | P1 / 4 | Implement local and online co-op in one session | [#320](https://github.com/elgansayer/Neptune-Bomberman/issues/320) |
| COOP-003 | P1 / 4 | Implement shared, personal and leader-owned objectives | [#321](https://github.com/elgansayer/Neptune-Bomberman/issues/321) |
| COOP-004 | P1 / 4 | Implement co-op checkpoint and restore consensus | [#54](https://github.com/elgansayer/Neptune-Bomberman/issues/54) |
| COOP-005 | P1 / 4 | Implement co-op join, leave and catch-up rules | [#322](https://github.com/elgansayer/Neptune-Bomberman/issues/322) |
| COOP-006 | P1 / 4 | Implement downed, revive and party-wipe states | [#324](https://github.com/elgansayer/Neptune-Bomberman/issues/324) |
| COOP-007 | P1 / 4 | Implement camera tethering and split-view policies | [#325](https://github.com/elgansayer/Neptune-Bomberman/issues/325) |
| COOP-008 | P1 / 4 | Implement dialogue and branch-choice arbitration | [#332](https://github.com/elgansayer/Neptune-Bomberman/issues/332) |
| COOP-009 | P1 / 4 | Implement co-op puzzle capability validation | [#340](https://github.com/elgansayer/Neptune-Bomberman/issues/340) |
| COOP-010 | P1 / 4 | Implement companion substitution without progress exploits | [#326](https://github.com/elgansayer/Neptune-Bomberman/issues/326) |
| COOP-011 | P1 / 4 | Implement scalable encounters and loot sharing | [#327](https://github.com/elgansayer/Neptune-Bomberman/issues/327) |
| COOP-012 | P1 / 4 | Build co-op authoring and regression fixtures | [#344](https://github.com/elgansayer/Neptune-Bomberman/issues/344) |

## EDITOR: Creation tools

| ID | Priority / wave | Feature | GitHub |
| --- | --- | --- | --- |
| EDITOR-001 | P1 / 4 | Build a map editor with layered tile painting | [#304](https://github.com/elgansayer/Neptune-Bomberman/issues/304) |
| EDITOR-002 | P1 / 4 | Implement editor undo, redo and autosave recovery | [#305](https://github.com/elgansayer/Neptune-Bomberman/issues/305) |
| EDITOR-003 | P1 / 4 | Implement selection, copy, transforms and reusable prefabs | [#306](https://github.com/elgansayer/Neptune-Bomberman/issues/306) |
| EDITOR-004 | P1 / 4 | Implement map preview and one-click bot playtesting | [#307](https://github.com/elgansayer/Neptune-Bomberman/issues/307) |
| EDITOR-005 | P1 / 4 | Build a character animation and anchor editor | [#308](https://github.com/elgansayer/Neptune-Bomberman/issues/308) |
| EDITOR-006 | P1 / 4 | Build an item and effect graph editor | [#309](https://github.com/elgansayer/Neptune-Bomberman/issues/309) |
| EDITOR-007 | P1 / 4 | Build a ruleset and battle-mode editor | [#310](https://github.com/elgansayer/Neptune-Bomberman/issues/310) |
| EDITOR-008 | P1 / 4 | Build a campaign graph and chapter editor | [#328](https://github.com/elgansayer/Neptune-Bomberman/issues/328) |
| EDITOR-009 | P1 / 4 | Build a dialogue and localisation editor | [#333](https://github.com/elgansayer/Neptune-Bomberman/issues/333) |
| EDITOR-010 | P1 / 4 | Build an encounter and boss-phase editor | [#338](https://github.com/elgansayer/Neptune-Bomberman/issues/338) |
| EDITOR-011 | P1 / 4 | Build a co-op scenario validator | [#341](https://github.com/elgansayer/Neptune-Bomberman/issues/341) |
| EDITOR-012 | P1 / 4 | Implement creator asset import and conversion | [#311](https://github.com/elgansayer/Neptune-Bomberman/issues/311) |
| EDITOR-013 | P1 / 4 | Implement creator preview profiles and device sizes | [#312](https://github.com/elgansayer/Neptune-Bomberman/issues/312) |
| EDITOR-014 | P1 / 4 | Implement pack project templates and guided onboarding | [#313](https://github.com/elgansayer/Neptune-Bomberman/issues/313) |
| EDITOR-015 | P1 / 4 | Implement editor diagnostics and machine-readable reports | [#314](https://github.com/elgansayer/Neptune-Bomberman/issues/314) |
| EDITOR-016 | P1 / 4 | Implement portable project source and collaborative diffs | [#315](https://github.com/elgansayer/Neptune-Bomberman/issues/315) |
| EDITOR-017 | P1 / 4 | Implement creator publish preparation and previews | [#316](https://github.com/elgansayer/Neptune-Bomberman/issues/316) |
| EDITOR-018 | P1 / 4 | Implement editor keyboard/controller accessibility | [#317](https://github.com/elgansayer/Neptune-Bomberman/issues/317) |

## WORKSHOP: Sharing, discovery and creator services

| ID | Priority / wave | Feature | GitHub |
| --- | --- | --- | --- |
| WORKSHOP-001 | P1 / 4 | Implement workshop pack submission and version records | [#355](https://github.com/elgansayer/Neptune-Bomberman/issues/355) |
| WORKSHOP-002 | P1 / 4 | Implement workshop browsing, search and filters | [#356](https://github.com/elgansayer/Neptune-Bomberman/issues/356) |
| WORKSHOP-003 | P1 / 4 | Implement pack pages with dependencies and provenance | [#357](https://github.com/elgansayer/Neptune-Bomberman/issues/357) |
| WORKSHOP-004 | P1 / 4 | Implement subscriptions and controlled updates | [#358](https://github.com/elgansayer/Neptune-Bomberman/issues/358) |
| WORKSHOP-005 | P1 / 4 | Implement dependency-aware downloads and offline use | [#359](https://github.com/elgansayer/Neptune-Bomberman/issues/359) |
| WORKSHOP-006 | P1 / 4 | Implement creator ownership and collaborator roles | [#360](https://github.com/elgansayer/Neptune-Bomberman/issues/360) |
| WORKSHOP-007 | P1 / 4 | Implement content reports and moderation queues | [#361](https://github.com/elgansayer/Neptune-Bomberman/issues/361) |
| WORKSHOP-008 | P1 / 4 | Implement asset provenance and licence compatibility checks | [#362](https://github.com/elgansayer/Neptune-Bomberman/issues/362) |
| WORKSHOP-009 | P1 / 4 | Implement pack quarantine and emergency disablement | [#363](https://github.com/elgansayer/Neptune-Bomberman/issues/363) |
| WORKSHOP-010 | P1 / 4 | Implement ratings, reviews and creator replies | [#364](https://github.com/elgansayer/Neptune-Bomberman/issues/364) |
| WORKSHOP-011 | P1 / 4 | Implement collections, playlists and share links | [#365](https://github.com/elgansayer/Neptune-Bomberman/issues/365) |
| WORKSHOP-012 | P1 / 4 | Implement featured content and discovery policies | [#366](https://github.com/elgansayer/Neptune-Bomberman/issues/366) |
| WORKSHOP-013 | P1 / 4 | Implement creator analytics with privacy controls | [#367](https://github.com/elgansayer/Neptune-Bomberman/issues/367) |
| WORKSHOP-014 | P1 / 4 | Implement pack retirement, forks and successor links | [#368](https://github.com/elgansayer/Neptune-Bomberman/issues/368) |
| WORKSHOP-015 | P1 / 4 | Implement service pagination, caching and abuse budgets | [#369](https://github.com/elgansayer/Neptune-Bomberman/issues/369) |
| WORKSHOP-016 | P1 / 4 | Build a full community creation acceptance journey | [#57](https://github.com/elgansayer/Neptune-Bomberman/issues/57) |

## SOCIAL: Community and tournaments

| ID | Priority / wave | Feature | GitHub |
| --- | --- | --- | --- |
| SOCIAL-001 | P2 / 4 | Implement guest and account identity transitions | [#354](https://github.com/elgansayer/Neptune-Bomberman/issues/354) |
| SOCIAL-002 | P2 / 4 | Implement friends, presence and invitations | [#370](https://github.com/elgansayer/Neptune-Bomberman/issues/370) |
| SOCIAL-003 | P2 / 4 | Implement persistent parties and party leadership | [#371](https://github.com/elgansayer/Neptune-Bomberman/issues/371) |
| SOCIAL-004 | P2 / 4 | Implement text chat with mute and channel scopes | [#373](https://github.com/elgansayer/Neptune-Bomberman/issues/373) |
| SOCIAL-005 | P2 / 4 | Implement pings and quick communication wheels | [#374](https://github.com/elgansayer/Neptune-Bomberman/issues/374) |
| SOCIAL-006 | P2 / 4 | Implement block and report controls | [#375](https://github.com/elgansayer/Neptune-Bomberman/issues/375) |
| SOCIAL-007 | P2 / 4 | Implement player profile visibility and privacy settings | [#376](https://github.com/elgansayer/Neptune-Bomberman/issues/376) |
| SOCIAL-008 | P2 / 4 | Implement tournament registration and brackets | [#381](https://github.com/elgansayer/Neptune-Bomberman/issues/381) |
| SOCIAL-009 | P2 / 4 | Implement tournament check-in, results and disputes | [#383](https://github.com/elgansayer/Neptune-Bomberman/issues/383) |
| SOCIAL-010 | P2 / 4 | Implement clubs and shared community collections | [#377](https://github.com/elgansayer/Neptune-Bomberman/issues/377) |

## STATS: Identity, progression and trusted statistics

| ID | Priority / wave | Feature | GitHub |
| --- | --- | --- | --- |
| STATS-001 | P2 / 4 | Define authoritative match statistics and event schemas | [#378](https://github.com/elgansayer/Neptune-Bomberman/issues/378) |
| STATS-002 | P2 / 4 | Separate verified, community and local result trust | [#380](https://github.com/elgansayer/Neptune-Bomberman/issues/380) |
| STATS-003 | P2 / 4 | Implement player match history and result detail | [#382](https://github.com/elgansayer/Neptune-Bomberman/issues/382) |
| STATS-004 | P2 / 4 | Implement skill ratings by compatible ruleset | [#385](https://github.com/elgansayer/Neptune-Bomberman/issues/385) |
| STATS-005 | P2 / 4 | Implement ranked queues and seasonal resets | [#386](https://github.com/elgansayer/Neptune-Bomberman/issues/386) |
| STATS-006 | P2 / 4 | Implement campaign completion and personal bests | [#387](https://github.com/elgansayer/Neptune-Bomberman/issues/387) |
| STATS-007 | P2 / 4 | Implement achievements and optional progression | [#388](https://github.com/elgansayer/Neptune-Bomberman/issues/388) |
| STATS-008 | P2 / 4 | Implement leaderboards with reproducible score validation | [#389](https://github.com/elgansayer/Neptune-Bomberman/issues/389) |
| STATS-009 | P2 / 4 | Implement aggregate balance and bot performance reports | [#390](https://github.com/elgansayer/Neptune-Bomberman/issues/390) |
| STATS-010 | P2 / 4 | Implement player data export and deletion workflows | [#391](https://github.com/elgansayer/Neptune-Bomberman/issues/391) |
| STATS-011 | P2 / 4 | Implement statistics schema migrations and backfills | [#392](https://github.com/elgansayer/Neptune-Bomberman/issues/392) |
| STATS-012 | P2 / 4 | Implement custom-mode statistics declarations | [#393](https://github.com/elgansayer/Neptune-Bomberman/issues/393) |

## UX: Controls, onboarding and accessibility

| ID | Priority / wave | Feature | GitHub |
| --- | --- | --- | --- |
| UX-001 | P1 / 2 | Build a multiplayer-first home and navigation flow | [#171](https://github.com/elgansayer/Neptune-Bomberman/issues/171) |
| UX-002 | P1 / 2 | Implement keyboard and gamepad remapping | [#172](https://github.com/elgansayer/Neptune-Bomberman/issues/172) |
| UX-003 | P1 / 2 | Implement controller hotplug and local seat assignment | [#173](https://github.com/elgansayer/Neptune-Bomberman/issues/173) |
| UX-004 | P1 / 2 | Implement touch controls and mobile-browser layout | [#174](https://github.com/elgansayer/Neptune-Bomberman/issues/174) |
| UX-005 | P1 / 2 | Implement focus-loss and stuck-input recovery | [#175](https://github.com/elgansayer/Neptune-Bomberman/issues/175) |
| UX-006 | P1 / 2 | Implement readable character outlines and player markers | [#176](https://github.com/elgansayer/Neptune-Bomberman/issues/176) |
| UX-007 | P1 / 2 | Implement colour-vision accessible palettes and symbols | [#177](https://github.com/elgansayer/Neptune-Bomberman/issues/177) |
| UX-008 | P1 / 2 | Implement scalable text, HUD and safe areas | [#178](https://github.com/elgansayer/Neptune-Bomberman/issues/178) |
| UX-009 | P1 / 2 | Implement reduced motion, flash and screen-shake settings | [#179](https://github.com/elgansayer/Neptune-Bomberman/issues/179) |
| UX-010 | P1 / 2 | Implement independent audio levels and visual sound cues | [#180](https://github.com/elgansayer/Neptune-Bomberman/issues/180) |
| UX-011 | P1 / 2 | Implement screen-reader-friendly menus and text alternatives | [#181](https://github.com/elgansayer/Neptune-Bomberman/issues/181) |
| UX-012 | P1 / 2 | Implement interactive movement and bomb tutorials | [#182](https://github.com/elgansayer/Neptune-Bomberman/issues/182) |
| UX-013 | P1 / 2 | Implement context-sensitive help and control prompts | [#256](https://github.com/elgansayer/Neptune-Bomberman/issues/256) |
| UX-014 | P1 / 2 | Implement searchable content selection and favourites | [#257](https://github.com/elgansayer/Neptune-Bomberman/issues/257) |
| UX-015 | P1 / 2 | Implement clear loading, validation and failure states | [#183](https://github.com/elgansayer/Neptune-Bomberman/issues/183) |
| UX-016 | P1 / 2 | Implement localisation, pluralisation and right-to-left layouts | [#184](https://github.com/elgansayer/Neptune-Bomberman/issues/184) |

## MEDIA: Rendering, animation, sound and original assets

| ID | Priority / wave | Feature | GitHub |
| --- | --- | --- | --- |
| MEDIA-001 | P2 / 3 | Define pixel-perfect and flexible rendering profiles | [#282](https://github.com/elgansayer/Neptune-Bomberman/issues/282) |
| MEDIA-002 | P2 / 3 | Implement sprite batching and large-roster memory budgets | [#283](https://github.com/elgansayer/Neptune-Bomberman/issues/283) |
| MEDIA-003 | P2 / 3 | Implement animation event and gameplay separation | [#284](https://github.com/elgansayer/Neptune-Bomberman/issues/284) |
| MEDIA-004 | P2 / 3 | Implement layered character, mount and equipment rendering | [#295](https://github.com/elgansayer/Neptune-Bomberman/issues/295) |
| MEDIA-005 | P2 / 3 | Implement palette swaps and colour remapping | [#285](https://github.com/elgansayer/Neptune-Bomberman/issues/285) |
| MEDIA-006 | P2 / 3 | Implement directional and spatial sound policies | [#286](https://github.com/elgansayer/Neptune-Bomberman/issues/286) |
| MEDIA-007 | P2 / 3 | Implement music transitions and campaign audio states | [#287](https://github.com/elgansayer/Neptune-Bomberman/issues/287) |
| MEDIA-008 | P2 / 3 | Implement captions and authored voice playback | [#288](https://github.com/elgansayer/Neptune-Bomberman/issues/288) |
| MEDIA-009 | P2 / 3 | Implement effect quality tiers and fallback assets | [#289](https://github.com/elgansayer/Neptune-Bomberman/issues/289) |
| MEDIA-010 | P2 / 3 | Implement camera effects and spectator framing | [#290](https://github.com/elgansayer/Neptune-Bomberman/issues/290) |
| MEDIA-011 | P2 / 3 | Implement thumbnail and preview generation | [#291](https://github.com/elgansayer/Neptune-Bomberman/issues/291) |
| MEDIA-012 | P2 / 3 | Build an original starter asset set with source credits | [#292](https://github.com/elgansayer/Neptune-Bomberman/issues/292) |

## REPLAY: Replays, spectating and broadcast

| ID | Priority / wave | Feature | GitHub |
| --- | --- | --- | --- |
| REPLAY-001 | P1 / 3 | Record authoritative replay headers and command streams | [#273](https://github.com/elgansayer/Neptune-Bomberman/issues/273) |
| REPLAY-002 | P1 / 3 | Implement deterministic replay verification | [#274](https://github.com/elgansayer/Neptune-Bomberman/issues/274) |
| REPLAY-003 | P1 / 3 | Implement replay seeking and checkpoint indexes | [#275](https://github.com/elgansayer/Neptune-Bomberman/issues/275) |
| REPLAY-004 | P1 / 3 | Implement replay speed, pause and camera controls | [#276](https://github.com/elgansayer/Neptune-Bomberman/issues/276) |
| REPLAY-005 | P1 / 3 | Implement replay sharing with privacy filters | [#277](https://github.com/elgansayer/Neptune-Bomberman/issues/277) |
| REPLAY-006 | P1 / 3 | Implement live spectating and broadcast delay | [#278](https://github.com/elgansayer/Neptune-Bomberman/issues/278) |
| REPLAY-007 | P1 / 3 | Implement tournament broadcast overlays | [#384](https://github.com/elgansayer/Neptune-Bomberman/issues/384) |
| REPLAY-008 | P1 / 3 | Implement replay-based bug reports | [#280](https://github.com/elgansayer/Neptune-Bomberman/issues/280) |
| REPLAY-009 | P1 / 3 | Implement ghost runs and asynchronous challenges | [#343](https://github.com/elgansayer/Neptune-Bomberman/issues/343) |
| REPLAY-010 | P1 / 3 | Implement replay retention and compatibility policy | [#281](https://github.com/elgansayer/Neptune-Bomberman/issues/281) |

## FACTORY: Continuous implementation and merge automation

| ID | Priority / wave | Feature | GitHub |
| --- | --- | --- | --- |
| FACTORY-001 | P0 / 1 | Validate issue readiness and bounded implementation scope | [#71](https://github.com/elgansayer/Neptune-Bomberman/issues/71) |
| FACTORY-002 | P0 / 1 | Implement durable task leases and worker ownership | [#72](https://github.com/elgansayer/Neptune-Bomberman/issues/72) |
| FACTORY-003 | P0 / 1 | Implement dependency-aware ready-task selection | [#73](https://github.com/elgansayer/Neptune-Bomberman/issues/73) |
| FACTORY-004 | P0 / 1 | Implement isolated worker branches and workspaces | [#74](https://github.com/elgansayer/Neptune-Bomberman/issues/74) |
| FACTORY-005 | P0 / 1 | Implement deterministic preflight and environment manifests | [#75](https://github.com/elgansayer/Neptune-Bomberman/issues/75) |
| FACTORY-006 | P0 / 1 | Implement feature-specific acceptance test selection | [#76](https://github.com/elgansayer/Neptune-Bomberman/issues/76) |
| FACTORY-007 | P0 / 1 | Implement native/browser/co-op integration lanes | [#345](https://github.com/elgansayer/Neptune-Bomberman/issues/345) |
| FACTORY-008 | P0 / 1 | Implement current-base PR revalidation and merge ordering | [#77](https://github.com/elgansayer/Neptune-Bomberman/issues/77) |
| FACTORY-009 | P0 / 1 | Implement automatic conflict repair within task boundaries | [#78](https://github.com/elgansayer/Neptune-Bomberman/issues/78) |
| FACTORY-010 | P0 / 1 | Implement post-merge regression detection and recovery | [#81](https://github.com/elgansayer/Neptune-Bomberman/issues/81) |
| FACTORY-011 | P0 / 1 | Implement failure classification and bounded retry budgets | [#79](https://github.com/elgansayer/Neptune-Bomberman/issues/79) |
| FACTORY-012 | P0 / 1 | Implement evidence storage and searchable run reports | [#80](https://github.com/elgansayer/Neptune-Bomberman/issues/80) |
| FACTORY-013 | P0 / 1 | Implement factory dashboard and operator controls | [#82](https://github.com/elgansayer/Neptune-Bomberman/issues/82) |
| FACTORY-014 | P0 / 1 | Implement provider cost and concurrency enforcement | [#83](https://github.com/elgansayer/Neptune-Bomberman/issues/83) |
| FACTORY-015 | P0 / 1 | Implement worker credential and tool isolation | [#84](https://github.com/elgansayer/Neptune-Bomberman/issues/84) |
| FACTORY-016 | P0 / 1 | Implement completion reconciliation and duplicate prevention | [#85](https://github.com/elgansayer/Neptune-Bomberman/issues/85) |
| FACTORY-017 | P0 / 1 | Automatically provision missing tools and resume factory jobs | [#518](https://github.com/elgansayer/Neptune-Bomberman/issues/518) |

## OPS: Packaging, hosting and operations

| ID | Priority / wave | Feature | GitHub |
| --- | --- | --- | --- |
| OPS-001 | P1 / 3 | Package dedicated authoritative game servers | [#227](https://github.com/elgansayer/Neptune-Bomberman/issues/227) |
| OPS-002 | P1 / 3 | Implement configuration validation and environment separation | [#228](https://github.com/elgansayer/Neptune-Bomberman/issues/228) |
| OPS-003 | P1 / 3 | Implement server health, readiness and graceful shutdown | [#229](https://github.com/elgansayer/Neptune-Bomberman/issues/229) |
| OPS-004 | P1 / 3 | Implement structured runtime metrics and bounded logs | [#230](https://github.com/elgansayer/Neptune-Bomberman/issues/230) |
| OPS-005 | P1 / 3 | Implement crash recovery and room reconciliation | [#379](https://github.com/elgansayer/Neptune-Bomberman/issues/379) |
| OPS-006 | P1 / 3 | Implement backup, restore and migration drills | [#231](https://github.com/elgansayer/Neptune-Bomberman/issues/231) |
| OPS-007 | P1 / 3 | Implement server capacity benchmarks and admission limits | [#232](https://github.com/elgansayer/Neptune-Bomberman/issues/232) |
| OPS-008 | P1 / 3 | Implement release channels and protocol rollout | [#233](https://github.com/elgansayer/Neptune-Bomberman/issues/233) |
| OPS-009 | P1 / 3 | Implement native packaging, signing and update workflows | [#234](https://github.com/elgansayer/Neptune-Bomberman/issues/234) |
| OPS-010 | P1 / 3 | Implement browser caching and offline installation policy | [#253](https://github.com/elgansayer/Neptune-Bomberman/issues/253) |
| OPS-011 | P1 / 3 | Implement service abuse controls and audit records | [#235](https://github.com/elgansayer/Neptune-Bomberman/issues/235) |
| OPS-012 | P1 / 3 | Publish self-hosting and local-development operations guides | [#236](https://github.com/elgansayer/Neptune-Bomberman/issues/236) |

## EXP: Optional original modes and experiments

| ID | Priority / wave | Feature | GitHub |
| --- | --- | --- | --- |
| EXP-001 | P3 / 6 | Prototype cooperative horde and survival expeditions | [#432](https://github.com/elgansayer/Neptune-Bomberman/issues/432) |
| EXP-002 | P3 / 6 | Prototype a roguelite campaign ruleset | [#433](https://github.com/elgansayer/Neptune-Bomberman/issues/433) |
| EXP-003 | P3 / 6 | Prototype puzzle and time-attack challenge packs | [#434](https://github.com/elgansayer/Neptune-Bomberman/issues/434) |
| EXP-004 | P3 / 6 | Prototype asymmetric heroes and authored classes | [#435](https://github.com/elgansayer/Neptune-Bomberman/issues/435) |
| EXP-005 | P3 / 6 | Prototype cooperative raid encounters | [#436](https://github.com/elgansayer/Neptune-Bomberman/issues/436) |
| EXP-006 | P3 / 6 | Prototype racing and obstacle-course modes | [#437](https://github.com/elgansayer/Neptune-Bomberman/issues/437) |
| EXP-007 | P3 / 6 | Prototype bomb sports and arena minigames | [#438](https://github.com/elgansayer/Neptune-Bomberman/issues/438) |
| EXP-008 | P3 / 6 | Prototype community challenge rotations | [#439](https://github.com/elgansayer/Neptune-Bomberman/issues/439) |
| EXP-009 | P3 / 6 | Prototype seasonal community events and collaborations | [#440](https://github.com/elgansayer/Neptune-Bomberman/issues/440) |
| EXP-010 | P3 / 6 | Evaluate larger-than-twelve-player modes | [#441](https://github.com/elgansayer/Neptune-Bomberman/issues/441) |
