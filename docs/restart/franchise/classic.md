# Classic Bomberman: computers, 8/16-bit consoles, Saturn and arcade

Research date: **3 November 2026**. This is a public-source feature inventory and
an eventual Neptune design reference. Every feature below is **documented**, not
newly measured in an original game and not a claim of Neptune implementation.
The [Saturn fidelity contract](../SATURN_FIDELITY.md), additions-only pack contract
and [factory/Saturn-first priority](../FACTORY_FIRST_GOAL.md) remain in force.

Read each release independently. The title `Bomberman`, the alias `Dyna Blaster`,
and the phrase `Atomic Punk` identify several substantially different games.
An arcade credit is not a saved campaign; a human seat is not a computer seat;
an unused animation is not an accessible feature. Numerical timings quoted in
guides are experiment leads until pinned-release measurements establish them.

## Release identity register

Years are first release/showcase, with distinct conversions identified separately.
This register covers 27 classic game/edition groups; it does not assert that every
hardware revision, demo disc, cartridge pressing or digital emulation wrapper has
been discovered. The wider franchise inventory lives in the surrounding dossier.

| ID | Release / aliases | Year and hardware | Identity boundary |
| --- | --- | --- | --- |
| C-01 | Bomber Man / Bakudan Otoko / Eric and the Floaters | 1983 Japanese computers; European MSX/ZX Spectrum 1984 | Original pre-NES game; multiple computer implementations need separate inspection. |
| C-02 | 3-D Bomberman / Sanjigen Bomberman | 1984, MSX; shrine also lists Sharp X1 | First-person interpretation; not a polygonal console game. |
| C-03 | Bomberman | 1985 Famicom; NES North America 1989; Famicom Disk System 1990 | Expanded robot-protagonist game; single-player. |
| C-04 | Bomberman Special | 1986 MSX | Conversion of NES formula with real mechanical and presentation differences. |
| C-05 | Bomberman, Toshiba Rupo edition | Approximately 1987, Rupo word processor | Rare monochrome conversion; date and full behaviour remain uncertain. |
| C-06 | Bomberman / Dyna Blaster | 1990 PC Engine; TurboGrafx-16 1991 | Home-console five-player battle introduction. |
| C-07 | Dyna Blaster computer conversions | 1991–1993 era: X68000, Amiga, MS-DOS, Atari ST | Related to C-06, not NES Bomberman II; platform-specific differences below. |
| C-08 | Bomber Man / Atomic Punk / Dyna Blaster, arcade | 1991 Irem arcade | Japanese and overseas mode/player-count differences matter. |
| C-09 | Bomberman II / Dynablaster | 1991 Famicom, Europe 1992, North America 1993 | NES sequel; separate two-player Vs and three-player Battle. |
| C-10 | Bomber Man World / New Dyna Blaster: Global Quest / New Atomic Punk: Global Quest / Atomic Punk 2 | 1992 Irem arcade | Not 1998 PlayStation Bomberman World. |
| C-11 | Bomberman '93 | December 1992 PC Engine; 1993 North America | Title year differs from Japanese release year. |
| C-12 | Super Bomberman | 1993 SNES/Super Famicom | Not the later similarly named mobile game. |
| C-13 | Hi-Ten Bomberman | 1993 event-only custom hardware | Publicly demonstrated game; no ordinary retail release. |
| C-14 | Bomberman '94 | December 1993 PC Engine | Not a game first released in 1994. |
| C-15 | Bomberman '94 Special Version | 1993 PC Engine Super CD-ROM² promotional release | Battle-only limited distribution; not full retail '94. |
| C-16 | Super Bomberman 2 | 1994 SNES/Super Famicom | Solo scrolling adventure; battle and items expanded. |
| C-17 | Mega Bomberman | 1994 Mega Drive/Genesis | Westone conversion of '94; four players and campaign changes. |
| C-18 | Tengai Makyō: Deden no Den | 1994 PC Engine Super CD-ROM² promotional release | '94-derived Kabuki Denjūrō character replacement and battle subset. |
| C-19 | Hi-Ten Chara Bomb / Hi-Ten Kyara-BOM | 1994 event-only custom hardware | Expanded arena and Hudson guest characters. |
| C-20 | Super Bomberman 3 | 1995 Super Famicom/SNES, Japan and PAL regions | Two-player co-op; five-player battle. |
| C-21 | Super Bomberman 4 | 1996 Super Famicom, Japan | Organic/mechanical mounts and character abilities. |
| C-22 | Saturn Bomberman | 1996 Japan; 1997 Europe/North America, Sega Saturn | Normal, Master, standard Battle and Wide Battle are different rulesets. |
| C-23 | Saturn Bomberman XBAND | September 1996 Japanese Saturn | Separate network-focused release; not full retail Normal mode. |
| C-24 | Super Bomberman 5 | 1997 Super Famicom, Japan | Normal/gold cartridges; branching progression and custom battle characters. |
| C-25 | Neo Bomberman | 1997 Neo Geo MVS arcade | Not Atomic Bomberman; AES-mode behaviour does not establish an official home release. |
| C-26 | Atomic Bomberman | 1997 Windows, Interplay | Licensed original PC battle game with scheme editor and IPX networking. |
| C-27 | Saturn Bomberman Fight!! | 1997 Sega Saturn, Japan | Separate isometric 3D battle game with health, jumping and character stats. |

Reissues, compilations, demos and the unreleased Mega Drive proof of concept have
their own edition notes rather than inflating the count of original games.

## C-01 — Bomber Man / Bakudan Otoko / Eric and the Floaters

Sources: [original computer release overview][C01], [MSX specialist gameplay][C02].

- The original is a single-player maze game with a human protagonist, balloons,
  destructible blocks and fixed obstacles. The familiar robot design came later.
- The MSX guide describes randomly generated starting positions, walls and enemy
  placements. A new layout can be generated after death.
- Balloons change expression/colour; the guide interprets this as changing their
  pursuit behaviour. Treat the colour-to-policy mapping as an unmeasured claim.
- Bomb supply is effectively unlimited in the documented MSX version. This is
  different from the later bomb-capacity upgrade loop.
- Bombs have a documented two-tile reach and can be placed off tile centres.
  Partial blasts can leave half-destroyed soft blocks, a mechanic worth preserving
  as an optional historical profile rather than imposing on modern grid rules.
- Characters and balloons can pass through bombs, so bombs do not create the same
  corner traps as in later games.
- Hidden exits can advance immediately even while enemies remain. Treasure-chest
  pickups add score. Defeating balloons is the main score/combat activity.
- The release overview lists PC-6001, PC-8801, MSX, FM-7, Sharp X1, MZ machines and
  further Japanese computers. The feature bullets above describe the MSX guide,
  **not verified common behaviour across that entire platform list**.
- European MSX/ZX Spectrum branding is Eric and the Floaters. Preserve platform,
  publisher, language and build as identity fields; do not infer mechanical parity.
- Open work: per-platform controls, enemy policies, timers, scoring, level/end
  behaviour and the complete computer release denominator.

## C-02 — 3-D Bomberman

Sources: [Generation MSX record][C03], [first-person play account][C04].

- A 1984 MSX title, distinct from the later games branded Bomberman 3D by fans.
- Uses a first-person maze view with timed bombs and hostile green balloons.
- The contemporary-style play account describes forward/backward movement,
  right-angle turning and half-block steps.
- A small radar supplies player/enemy/outer-wall information. Destructible interior
  walls can look like the indestructible boundary from the main perspective.
- A ladder provides escape/progression; the account reports no score for using it.
- This suggests a reusable alternative camera and limited-information ruleset,
  plus radar-based navigation and escape objectives.
- Open work: confirm Sharp X1 and any other conversions, exact radar semantics,
  fuse behaviour, scoring, number of stages and ending conditions. The play account
  itself does not establish whether a final ending exists.

## C-03 — Bomberman, Famicom/NES/Famicom Disk System

Sources: [release/gameplay overview][C05], [version-aware detailed guide][C06],
[edition comparison][C07].

- Fifty main stages use the destroy-enemies-and-find-the-hidden-door objective.
  Stages scroll horizontally and include fixed hard-block geometry with variable
  soft blocks and enemies.
- Bombs block movement after placement; cross-shaped blasts trigger chain
  reactions, destroy blocks and kill vulnerable enemies and the player.
- One power-up is normally hidden in a stage. Bomb capacity, flame reach and the
  speed upgrade can survive death; ability items have separate persistence rules.
- Documented abilities: Bomb Up, Fire Up, Skate, remote detonation, soft-block
  passage, bomb passage, fire protection and temporary invincibility.
- Remote bombs remain until the player detonates them or another explosion
  reaches them. A single global fuse rule cannot model both timed and remote bombs.
- Eight legacy enemy families have different speeds, turning/pursuit patterns,
  soft-block traversal and score values: Ballom, Onil, Dall, Minvo, Kondoria, Ovapi,
  Pass/Parse and Pontan. Name transliterations vary by source/localisation.
- Bombing an exposed exit or an item can spawn enemies, making the exit a gameplay
  object rather than merely a scene-transition trigger.
- Timeout can replace existing enemies with Pontans instead of immediately ending
  the stage. This differs from the direct life-loss timeout of several sequels.
- Bonus stages after groups of levels allow reckless bombing under invincibility.
  Simultaneous/multi-enemy kills increase score awards.
- Hidden bonus collectibles require conditions such as visiting the exit before
  killing enemies or walking around the perimeter after clearing a stage.
- Passwords retain stage, abilities and score. The permissive password system can
  expose unusual item combinations and out-of-range stages; distinguish these
  from the intended campaign route.
- Completing the campaign shows an ending and loops to the first stage with
  retained equipment in the specialist account.
- Pause and game-over/password screens are part of the full experience. There is
  no local competitive Battle mode in this original release.
- Famicom Disk System is documented as a substantially identical rewrite-service
  edition without a new disc-swapping gameplay loop.
- Open work: reconcile differences in how sources count starting lives; pin the
  exact timing units, RNG, collision/corner rules, score tables and password parser.

## C-04 — Bomberman Special, MSX

Sources: [version-aware detailed guide][C06], [edition comparison][C07].

- A conversion of the 1985 formula, not the 1983 MSX original.
- Retains enemies, power-ups, hidden exits, bonus stages and passwords while
  changing level layouts, item requirements and some enemy scoring/behaviour.
- Uses flip-screen camera movement in place of smooth horizontal scrolling.
- Uses a smaller resolution, reduced palette and reduced enemy animation.
- Different timer pacing, temporary-invincibility duration, movement rates and
  maximum item stocks are documented. Preserve these as version parameters.
- Some bonus icons change to Hudson's bee, BeeCard and office clock tower.
- The guide's prose and comparison table disagree on maximum MSX bomb stock;
  **do not choose a value until the original build is tested**.
- An unlicensed SG-1000 conversion is reported in the release account; its
  provenance and mechanics remain a separate investigation, not an official port.

## C-05 — Bomberman, Toshiba Rupo

Source: [updated edition inventory][C08].

- A rarely documented word-processor conversion with an approximately 1987 date.
- The cited record describes a monochrome widescreen presentation showing the
  entire 29×11 stage with a HUD at the side, avoiding camera scrolling.
- Open work is nearly the entire game: compatible Rupo models, release identity,
  controls, original software availability, rule differences, sound and saves.
- Keep the entry visible with unknown mechanics; rarity is not evidence of absence.

## C-06 — Bomberman, PC Engine/TurboGrafx-16

Sources: [release overview][C09], [campaign and battle guide][C10].

- Normal mode has eight worlds of eight stages in the guide, ending each world
  with a multi-hit boss. Some stages scroll vertically.
- Standard objective: destroy enemies, reveal and enter the exit. The soft block
  containing an uncollected item flashes after enemies are cleared.
- Bombing the door or an item spawns enemies. Normal timeout replaces enemies
  with Pontans; boss handling requires its own scenario.
- Items include bomb/flame/speed increases, remote detonation, bomb pass, block
  pass, timed fire protection and extra lives.
- Bonus collectibles have conditional triggers rather than simply occupying
  predetermined blocks; some guide conditions are explicitly unverified.
- Up to five **human** players compete using a multitap. This release does not
  provide CPU-controlled Bomberman seats in the documented battle mode.
- The normal battle item pool is deliberately small: Bomb Ups and Fire Ups.
  Skull mode adds contagious temporary ailments.
- With fewer than five players, ordinary enemies populate the battle arena as an
  additional threat. Enemy population and timer depend on player count.
- Wins-to-match is configurable; the timer is tied to participation count.
- There is no falling-wall sudden death in this documented battle profile.
  Timeout kills survivors and yields a draw.
- A sound test and hidden stage/loadout configuration screen provide useful
  research hooks. Save/load and portable-system link options vary by conversion.
- Open work: distinguish PC Engine and TurboGrafx-16 editions, TurboExpress/GT
  link behaviour, backup-memory requirements, enemy mixtures and all boss states.

## C-07 — Dyna Blaster computer conversions

Sources: [platform release overview][C09], [conversion-by-conversion comparison][C11].

- X68000, Amiga, MS-DOS and Atari ST conversions belong to the 1990 game family.
  Do not transfer three-player NES Bomberman II behaviour to them by alias alone.
- X68000: documented taller view, four-player limit and selectable keyboard/pad
  inputs; portable-console link options are removed.
- MS-DOS: setup menu, keyboard/gamepad configuration and VGA scrolling test;
  four-player battle is documented by the specialist comparison.
- Amiga: floppy loading, removed save/load and GT-link options; several bosses
  lose attacks or have altered enemy populations and transition sequences.
- Atari ST: side HUD for its screen geometry, altered music, shortened scenes,
  absent end credits and removed boss hit-flashing in the cited comparison.
- These examples justify separate presentation, controller, loading, boss and
  progression contracts for each conversion rather than one generic Dyna profile.
- An announced Commodore 64 conversion did not release; manuals advertising it
  do not prove a playable retail game. A Lynx cancellation is tracked elsewhere
  in the franchise research; neither is silently counted as released here.
- Open work: original manuals/builds, exact release dates and playable player
  counts/input topology for every conversion; published dates are inconsistent.

## C-08 — Bomber Man / Atomic Punk / Dyna Blaster, Irem arcade

Sources: [campaign/battle guide][C12], [regional comparison][C13].

- Six worlds with six rounds each are documented; every sixth is a multi-hit boss.
  Levels are single-screen.
- Destroying all enemies automatically advances. There is no hidden-door hunt.
- Death normally respawns the player while the stage continues. Remote Control
  is lost on death while basic stat upgrades persist until the round ends.
- All upgrades reset at the next round, creating a short-cycle arcade economy.
- A joining player's Start input and a death can reset the stage timer. Timeout
  restarts the round; reported two-/three-minute variants need dip-switch checks.
- Items include bomb/flame/speed upgrades, remote bombs, temporary protection,
  extra lives and score objects.
- The Japanese edition supports two humans and exposes a Vs Game against CPUs.
- Overseas editions can support four players through dip switches, but remove
  the mode-selection menu, making that Japanese Vs Game inaccessible normally.
- Japanese Vs is a four-seat arena with one/two humans and CPU-filled seats,
  progressively harder repeated matches and a special three-victory screen.
- The cocktail version restarts a solo stage after death, unlike other variants.
- Overseas versions rearrange and replace some stages and enemy populations.
- Open work: dip switches, credit/continue limits, cabinet input variants, region
  revisions and stage-by-stage deltas. Four-human co-op must not imply four-human
  access to the Japanese competitive menu.

## C-09 — Bomberman II / Dynablaster, NES

Sources: [release and modes][C14], [detailed guide][C15].

- Solo campaign uses six areas with eight stages each, some single-screen and
  some scrolling across two screens.
- Destroy all enemies and uncover the exit; bombing exits/items spawns foes.
- A bonus token in each area's sixth stage enables a bonus round; running
  Bomberman clones in that round award extra lives.
- Basic capacity/flame upgrades persist, with remote bombs, speed, bomb passage,
  block passage and two differently acting fire-protection items also documented.
- One fire-protection variant lets blasts push the player harmlessly; another
  prevents that displacement. Damage immunity and knockback are separate axes.
- A Mystery item can replace an already-owned remote item. Its selection rules
  remain a guide hypothesis, not verified RNG semantics.
- Vs Mode is two-human competition; Battle Mode is three-human competition.
  Computer opponents are not offered in this release's competitive modes.
- Skull ailments can transfer by touch. Exact available ailments and expiration
  rules need inspection in both modes, rather than inheritance from later games.
- Password alphabets differ between Japanese and English releases. A special
  password enables persistent remote control, and another opens the sound room.
- Open work: per-mode starting stats, win limits, board geometry, simultaneous
  death resolution, three-controller adapters and the regional password mapping.

## C-10 — Bomber Man World / New Atomic Punk: Global Quest

Sources: [release overview][C16], [detailed arcade guide][C17], [play account][C18].

- Irem's 1992 follow-up, distinct from PlayStation Bomberman World.
- Up to four humans can co-operate through single-screen enemy-clear stages.
  Six worlds contain six main rounds each, with bosses and optional bonus rounds.
- Immediate post-death respawn, round-end equipment reset and timer-reset events
  are part of the documented arcade lifecycle.
- BONUS letter collection in the first five rounds buys time in a block-smashing
  score bonus stage; collecting the whole word grants additional time.
- Basic and maximum stat pickups coexist. Source item labels are unofficial and
  occasionally swapped; verify the actual effect instead of relying on the name.
- Special remote/fission bomb ammunition can be limited in quantity according
  to the play account. Exact remaining-ammunition and replacement rules are open.
- Fission/splinter bombs redirect remaining blast reach around an encountered
  block, allowing fire to turn corners. This is different from soft-block piercing.
- Protection, contact-kill protection, clock freeze, extra lives and score pickups
  provide distinct effects; skulls occur in Vs/bonus contexts.
- Vs supports human/CPU seats with repeated escalating matches and credit/life
  handling. Preserve cabinet revision and region before fixing a seat topology.
- Open work: fission propagation at junctions, chain priority, ammunition limits,
  bonus timing and credit-specific continuation semantics.

## C-11 — Bomberman '93

Sources: [release overview][C19], [campaign/items/battle guide][C20].

- Seven worlds with eight stages each are documented; world finales are bosses.
  Horizontal, vertical and single-screen stages coexist.
- Adds interactive campaign terrain and differentiated battle arenas, moving
  beyond the one-board competitive presentation of the 1990 game.
- Items: Bomb Up, Fire Up, Speed Up, speed down/Geta, Remote Control, Bomb Kick,
  Line Bomb, block/bomb passage, timed fire suit, Heart, clock, extra life and
  points objects. Item pools differ between Normal and Battle.
- Bomb Kick includes an explicit stop action. Double-tapping the bomb button
  lays available bombs in a forward line.
- Bosses and normal stages use different timer/timeout contracts in the guide.
- Battle supports two to five human/CPU participants, one-to-five win targets,
  fixed round time and clockwise falling hard blocks late in the round.
- Eight documented arenas use conveyors, deterministic warp destinations,
  turnstiles/spinning gates, no-bomb-placement tiles and regenerating soft blocks.
- No-bomb tiles restrict placement while allowing movement and flame traversal;
  they are not equivalent to solid collision.
- Revive blocks regenerate after destruction, requiring the simulation to resolve
  occupancy, items, bombs and actors at reappearance time.
- Skulls transfer ailments by contact; the battle item pool includes kick and
  line-bomb abilities but does not simply include every campaign item.
- Japanese hidden configuration and sound-test access differ from the US edition.
- Wii Virtual Console has a five-player input-activation caveat in its release
  account; a port's controller wrapper is a feature boundary worth documenting.
- Open work: actual CPU policy, revive collision, gate/flame interactions and
  every campaign terrain hazard; the item guide itself has some uncertain counts.

## C-12 — Super Bomberman

Sources: [release/mode overview][C21], [detailed guide][C22],
[power-up guide][C23].

- Six themed worlds with eight stages each; single-screen campaign, multi-hit
  bosses and two-human co-op. Friendly bombs remain dangerous to the partner.
- Soft-block and enemy positions are randomised, while the enemy/item roster is
  stage-specific. World five uses successive robot-Bomberman combat waves.
- Campaign passwords resume stages. The timer is represented visually by blocks.
- Bomb Up, Fire Up, speed, remote control, kick/stop, bomb punch, block pass, bomb
  pass, piercing/super bomb, maximum flame, temporary armour, Heart, extra life,
  clock, mystery and score collectibles appear across the documented item lists.
- Important terminology: this game's translated Power Glove/Boxing Glove sends
  a placed bomb flying. It is not automatically the carry-and-throw glove of SB2.
- Kicking a bomb into an ordinary enemy can deal damage without waiting for its
  blast. Airborne bosses can require a projectile/punched-bomb interaction.
- Competitive Battle supports four human/CPU seats and configurable win target.
  The guide lists ten CPU difficulty levels.
- Twelve arena gimmick sets include random bomb rain, directional jump pads,
  conveyors, concealment tunnels, items concentrated around the border, moving
  lawnmowers that remove bombs, darkened play with moving spotlights, high-power
  starting loadouts, random warps and maximum-speed play.
- Sudden-death walls spiral inward; simultaneous elimination and surviving to
  timeout can draw. Sources disagree on the exact start time: measure the edition.
- Contagious skull effects include speed changes, involuntary bombs, inability to
  place bombs, invisibility and weak-bomb restrictions in the power-up guide.
- A tiny-character password changes presentation in both modes; sound-test access
  uses a controller in the multitap's extra port.
- Open work: the precise item stock and score tables differ between secondary
  sources; do not copy their numerical caps or timing directly into Saturn defaults.

## C-13 — Hi-Ten Bomberman

Sources: [history/mode overview][C24], [specialist event account][C25].

- Event-demonstrated multiplayer game using custom circuitry with PC Engine
  controller hardware and a large 16:9 HDTV field, rather than an ordinary PC-FX
  retail title.
- Supports ten participants, colour-assigned through controller topology.
- Modes documented: Battle Royale, two teams of five, three teams of three,
  five teams of two and one-versus-nine.
- Multi-team, asymmetric and odd-seat-capacity rules should be explicit mode
  data, including what happens to an unused tenth seat in the three-team mode.
- Block destruction reveals extra bombs and flame reach. Detailed item pools,
  scoring, timeouts and arena variants are not fully established here.
- Distinguish public play at events/exhibits from retail availability and from
  modern preservation of a usable complete original build.
- Open work: playable input/build identity, exact maps and rule menu, elimination
  and tie handling, special items and team-friendly-fire behaviour.

## C-14 — Bomberman '94

Sources: [release overview][C26], [normal/items/Louies][C27], [battle guide][C28].

- Campaign changes its objective to destroying core mechanisms and recovering
  Spirit Picture fragments, rather than requiring every enemy to die.
- Some mechanisms are carried by enemies and must fall before being destroyed.
  The guide notes falling mechanisms can crush the player.
- Multiple rooms and stage selection/revisits coexist. Cleared stages reopen
  without mechanisms and with the exit already active.
- On stage clear, remaining soft blocks become coins during a short timed bonus.
- Six areas use jungle, volcano, sea, castle, snow and final-fortress themes.
- Items include capacity/flame increases, speed up/down, kick/stop, line bombs,
  remote control, block/bomb passage, Heart, extra life, freeze and fire protection.
- Louie eggs introduce rideable companions that absorb one hit and supply a
  colour-specific ability: dash, airborne bomb kick, soft-block kick, jump or dance.
- Block kicking can propagate through a row and move the last block. Jumping
  changes collision/explosion exposure, so it needs more than an animation flag.
- Louie death grace differs between campaign and battle in the specialist guide.
- Up to five humans/CPUs compete; team grouping and one-to-five wins are available.
- Nine character archetypes are cosmetic for humans but have described CPU
  tendencies: balanced, defensive, reckless, item-seeking, ambush, strategic,
  aggressive and block-clearing preferences.
- Ten battle settings cover plain boards, underwater visual distortion,
  counter-running conveyors, tight forest corridors, igloos, bomb-redirection
  arrows, linked trapdoors, high-power no-soft-block starts, high speed and canopy
  concealment. These are rules plus presentation, not merely background skins.
- Falling walls begin late in a fixed three-minute round in the guide.
- Sound Room access is documented for the PC Engine version.
- Open work: every enemy/boss/terrain inventory, exact Louie colours/abilities,
  CPU policy and per-edition mechanical differences.

## C-15 — Bomberman '94 Special Version

Source: [promotional edition comparison][C29].

- Limited-distribution PC Engine Super CD-ROM² battle game related to '94.
- One character type, one default arena with arrows redirecting kicked bombs.
- Up to five **humans**; the guide reports no CPU toggle.
- The '94 item set, including Louies, is reported available in this battle subset.
- Preliminary resources differ from the later Deden no Den release.
- Distribution quantities/dates in the guide are qualified estimates. Do not
  promote them to verified production totals or a precise release day.

## C-16 — Super Bomberman 2

Sources: [release/modes][C30], [specialist guide][C31], [item list][C32].

- Solo Normal mode drops co-op and uses larger scrolling layouts with monsters,
  switches, traps and gates. Destroying required enemies/switches opens the route.
- Five worlds culminate in an enemy-Bomber battle and then a war-machine boss.
- Predetermined block/enemy layouts coexist with randomised item locations.
- Death restarts the stage; bombing the exit can spawn enemies.
- Adds carry-and-throw Power Glove; its fuse handling differs from SB1's punch.
- Items include capacity/flame/speed, remote, Heart, bomb/block passage, kick,
  full fire, first-slot Power Bomb, piercing/super bombs and bouncing slime bombs.
- Battle supports four players, free-for-all and teams, with ten arenas in the
  release overview. Detailed per-arena hazard inventory remains open here.
- G-Bomber/golden winner option awards a roulette-selected starting power-up for
  the next match/round context. Verify precisely how long it remains active.
- Skull disease transfers by contact; the item guide describes picking up another
  item to eject the skull. Available ailments and immunity interactions need tests.
- Normal and full-power stage passwords are documented separately.
- Open work: full terrain inventory, all ten battle arenas, golden reward duration,
  carry fuse suspension/reset and region-specific option differences.

## C-17 — Mega Bomberman

Sources: [release identity][C26], [detailed conversion comparison][C33].

- Westone's 1994 Mega Drive/Genesis adaptation of '94 retains core-mechanism
  objectives, Spirit Pictures, Louies and the normal/battle split.
- Battle supports four players, not the PC Engine original's five.
- Campaign stage ordering is constrained: '94 lets the player choose unfinished
  stages within an area; Mega requires order, while allowing completed revisits.
- Spirit Picture progress display changes, as do intro/ending details and names.
- Palette, audio instrumentation, two stage music tracks and environmental
  effects differ. Water ripples/foreground fish and snow are among removed effects.
- The South Pole battle board adds fireworks and an igloo-centre bomb effect
  with very large flame reach, absent from the PC Engine counterpart in the guide.
- Three-button controls separate actions differently from the two-button PC
  Engine layout. A control binding is part of edition identity.
- A separate Factor 5 proof of concept supported eight participants in reports;
  it is **not** the four-player Westone retail release. Never advertise eight
  players as a feature of the shipping Mega Bomberman cartridge.
- Open work: all boss/stage deltas, actual Sega multitap compatibility and
  unmodified release checks for any retained debug menus.

## C-18 — Tengai Makyō: Deden no Den

Source: [promotional edition comparison][C29].

- A 1994 '94-derived promotional battle game featuring Kabuki Denjūrō with
  differently coloured accessories rather than the ordinary Bomberman roster.
- Like Special Version, its default presentation exposes one arena and human
  competition; all Louie/power-up claims require this exact edition.
- A boot/title code unlocks four additional stages according to the guide.
- Character replacement, default-content restriction and hidden stage expansion
  are the specific differentiators. Do not infer a new campaign.
- Open work: exact distribution identity, stage inventory, hidden-language mode,
  music and full behaviour comparison with Special Version/retail '94.

## C-19 — Hi-Ten Chara Bomb

Sources: [Hi-Ten history][C24], [event account][C25].

- Summer 1994 update on custom Hi-Ten hardware, with a larger battlefield.
- Selectable Hudson guest characters include representatives from Bonk, Milon's
  Secret Castle, Momotarō Densetsu and Tengai Makyō.
- Ten-player event battle and character selection are documented; do not assume
  every original Hi-Ten mode or item survived without a menu/build comparison.
- Distinguish guest appearance from a mechanical special ability. The cited
  sources do not provide a complete per-character rules inventory.
- Open work: build preservation/playability, complete roster, team mode menu,
  map geometry and whether any character has a gameplay advantage.

## C-20 — Super Bomberman 3

Sources: [release/co-op identity][C34], [campaign/items/Louies][C35],
[mode overview][C36].

- Returns to co-op and mostly single-screen-style play after SB2's solo scrolling
  emphasis. Some stages still contain multiple screens.
- Destroy core mechanisms, including enemy-carried mechanisms, to open a computer
  chip capsule. Campaign goal progress is separate from enemy population.
- Completed stages are revisitable with mechanisms removed and exit open.
- Bomb/flame/speed up, Geta, full fire, kick, carry/throw, bouncing bombs,
  first-slot Power Bomb, piercing, remote, bomb/block passage, freeze, armour,
  Heart, extra life, points objects, eggs and skulls are documented.
- The carry/throw guide specifies a three-tile throw and destruction of an item
  under a landing bomb; this is a useful interaction probe, not a universal rule.
- Louies return with dash, jump, airborne bomb kick, block kick and line bomb.
  Unlike '94's dance Louie, this roster contains a useful line-bomb specialist.
- Battle expands the SNES series to five participants and introduces country-
  themed selectable character designs, including Pretty Bomber.
- Hidden battle-group passwords expose alternate layouts. A battle-group
  identifier should be captured separately from a board's visual theme.
- Campaign full-power passwords provide stage access/loadouts for research.
- Open work: full battle settings, revenge availability/semantics, all battle
  groups, every CPU character and stage hazard; do not infer these from SB4.

## C-21 — Super Bomberman 4

Sources: [release and modes][C37], [campaign/items/mounts][C38],
[detailed battle options][C39].

- Two-human co-op returns to enemy-clear objectives across historical eras.
  World routes include enemy-Bomber fights and larger bosses.
- Specific defeated enemies become eggs. Organic and mechanical mounts have
  different abilities, and the player can tow two spare eggs of the same category.
- Spare eggs can be destroyed by flame while surviving ordinary enemy contact.
  On mount death, the next spare becomes the ride automatically.
- Mount effects include piercing, wall pass, dash, global block destruction,
  bomb pass, full fire, kick, punch, max speed, stun projectile, slowing projectile,
  explosive sacrifice and line bombs.
- Caged allied Bombers can be freed and operate as helpers against blocks/enemies.
- Co-op bonus routes require throwing the other player over hard-block barriers.
  The carried object API must support players as well as bombs.
- Items add Punch, Push and character-changing Cosplay alongside the familiar
  bomb/range/speed, remote/piercing, glove, passage, Heart, clock and egg effects.
- The rotating/selectable item pickup is different from a random result chosen
  after collection; preserve its time-dependent selection behaviour.
- Battle Royale supports five human/CPU seats, free-for-all or two teams, three
  CPU levels, selectable win count/time, endless time and sudden-death depth.
- Gutter Bomb lets eliminated participants move along the boundary and throw
  inward, with a cutoff near timeout.
- Dash Bomber is a winner's driving/stop-on-an-item mini-game that determines
  next-match equipment; team matches have different availability.
- Champion mode is a sequence of Bomber King encounters, with solo and co-op
  variants and fixed enhanced starting equipment.
- Maniac mode selects available item quantities and per-player hit handicaps,
  while constraining the board, time, round count and other settings.
- Battle maps include speed-changing lights, blast-pushable balls, cliff-edge
  falls, all-power starts, slowing/sliding/control-reversal floor states, arrows,
  foliage, item-depositing slots and seesaws.
- Playable Bomber Kings/Great Bomber have special abilities; costs/cooldowns and
  temporary stat reductions must be documented individually.
- Open work: every character skill, complete mount roster, detailed co-op warp
  graph, secret battle groups and the constraints of each mode.

## C-22 — Saturn Bomberman

Sources: [release/mode overview][C40], [normal/items/Tirras][C41],
[battle options/hazards][C42], [Master guide][C43], [regional editions][C44].

### Normal, co-op and progression

- Destroy Core Mechanisms/Zarfs to open exits. A two-human cooperative campaign
  shares the world route, with enemies, stage hazards, set-piece transitions,
  multi-phase bosses, cinematics and ending sequences.
- Cleared stages can be revisited with their mechanisms removed; boss revisit
  restrictions are separate. Exact room/stage/boss counts need the pinned-release
  inventory already required by Neptune's Saturn research programme.
- World themes include Hige Hige Land, Mage Mage World, Gunman World, Tyranno World
  and Mujoe World. Do not substitute the names/themes for recovered level data.
- Variable stage timeouts, life loss, scores, extra lives and equipment carryover
  need separate Normal/co-op contracts.

### Bombs, items and mounts

- Bomb/range/speed increases; full flame and Geta; kick/stop; carry/throw; remote;
  first-slot Power Bomb; charged projectile bomb; piercing; line bomb; jelly/rubber
  bounce; invisible mine; protection; Heart; clock; extra life and score objects.
- **Availability differs by mode.** Remote and Power Bomb appear in the guide's
  Normal/Master lists; eggs in Normal/Battle; mine/full fire in Battle. A shared
  item registry still needs distinct pools, restrictions and parameter values.
- The charged shot launches a bomb that detonates on impact. Mine arming, reveal,
  countdown and blast extent differ from a normal timed bomb.
- Merger absorbs other participants temporarily and boosts the carrier; releases
  occur on expiry or carrier death. The guide excludes two-seat games.
- A special Bomura reward from Bomber Catcher can introduce a roaming creature
  in the following Wide Battle, crushing blocks/players and breathing fire.
- Skull and Devil are separate: one curses the collector, while the other can
  inflict ailments on every player. Exact disease interaction/order remains open.
- Tirras/dinosaurs absorb a hit, have three growth stages and five ability families:
  bomb-detecting/detonating screech, airborne kick, controllable dash evolution,
  stun roar and jump. Each growth level changes range/control.
- Campaign growth depends on a meter earned through play; battle growth uses
  extra eggs. Dismounting leaves a reclaimable Tirra that another player can ride.
- Do not copy the guide's numerical durations/ranges into the faithful profile
  without the existing measured-reference gates.

### Battle, maps and options

- Up to ten local human/CPU participants; up to eight in ordinary arenas, with
  nine/ten requiring Wide Battle and its reduced mechanics/item pool.
- A six-port multitap topology gives two native ports, six participants with one
  tap and ten with two taps. Physical topology is distinct from room capacity.
- Match win target, time, spawn Shuffle, No Draw, Devil, Mad Bomber and Bomber
  Catcher are named configuration switches.
- No Draw changes falling-wall completion rather than simply prohibiting a result
  string. Simultaneous deaths still require explicit resolution.
- Mad Bomber lets eliminated participants travel on the sidelines and throw
  bombs into the field; throw distance, speed-up input and late-round cutoff vary.
- Bomber Catcher is a crane mini-game whose captured item affects the next round.
- Stage sky/time variants alter mechanics/layouts, not only colour palettes.
  Japanese Night Sky unlock steps differ from the English editions.
- Arena mechanisms documented: bomb-redirection arrows, reversible conveyors,
  looping top/bottom paths that pass actors/bombs/flames, trampolines, seesaws,
  warps and periodic rain that restricts flame range.
- Hidden Yuna and Manto selection includes gameplay differences in the guide;
  visible roster/cosmetic choice cannot imply equal simulation.
- Control remapping, pause overlay hiding, stage access and soundtrack/voice
  regional changes belong in the full interface/presentation inventory.

### Master and networking

- Master is a separate twenty-floor enemy-clear gauntlet with regular bosses,
  score/rank goals, time bonuses and no ordinary life stock.
- Some basic upgrades/Hearts persist between floors, while special ability items
  are floor-limited. Normal-mode item persistence cannot be reused unchanged.
- Boss techniques include projectile bombs, bomb kicks, shields, flying immunity,
  minion generation, shockwaves, stun and form changes. Each is a separate state
  machine and interaction contract.
- North American NetLink provides a distinct network battle path with two linked
  consoles and up to four participants; Japanese XBAND is the separate C-23 build.
- Open work: all original code, per-room/enemy/boss content, every timing and
  RNG decision, exact native presentation/audio, saves, menus, modem negotiation
  and region-specific behaviours remain under the existing Saturn programme.

## C-23 — Saturn Bomberman XBAND

Source: [separate XBAND edition account][C44].

- Japanese network-focused release dated 27 September 1996 in the source.
- Omits the retail Normal campaign. Its network rules are not a free-form clone
  of every local Battle option.
- Up to four participants on two Saturns; team assignment, character assignment,
  three-minute time, first-to-three target and sudden death are fixed in the guide.
- A missing fourth participant can be filled by a low-level CPU in the reported
  three-human configuration.
- Without a modem, the software exposes a one-stage score challenge named
  NikoBon Pick '96 with graded performance, then returns to title.
- North American retail integrates a related network path, but that does not
  make the Japanese standalone disc the same executable/content set.
- Open work: original disc/regional menu traces, server/protocol assumptions,
  modem presence/error states and every offline challenge rule.

## C-24 — Super Bomberman 5

Sources: [release/edition overview][C45], [detailed walkthrough][C46].

- Nonlinear campaign with multiple exits, visited/completed stage indicators,
  world-map replay and stage-specific routes. Four worlds remix previous games;
  a fifth provides new content.
- Two endings depend on where the final boss is encountered. Completing the
  inventory to 100% resets progression for a second pass with additional items,
  enabling the advertised 200% goal.
- Two-player co-op shares life stock and supports midgame joining. Some item
  placements differ in two-player and second-pass configurations.
- Boss battles emphasise enemy Bombers with ordinary bomb/item interactions
  rather than only large bespoke monsters.
- Bomb capacity/range/speed up and down; full fire; kick/stop; punch; carry/throw;
  mine; piercing; remote; seeker; bomb/block pass; Heart; eggs; extra life;
  freeze clock; invincibility and contagious skull conditions are documented.
- Mines disappear, arm on contact and delay their explosion. Seeker bombs detect
  and pursue a target; they do not follow every terrain rule of ordinary bombs.
- Mutually exclusive effect families are documented: piercing/mine/remote/seeker,
  and kick/bomb passage. Replacement/ejection is a gameplay policy per profile.
- Airborne bomb impacts can stun and dislodge items; bombs/players thrown beyond
  board boundaries can wrap. Check carried-fuse differences against SB2/Saturn.
- Six Louies provide bomb kick, block kick, jump, line bombs, roll/dash and stun
  punch. Enemy Warooeys can instead serve simply as an extra hit.
- Battle supports character colour/loadout customisation through a points budget;
  predefined enemies and a secret character coexist with ordinary Bomberman.
- Normal and gold cartridges have different additional battle-map access.
  Do not infer an identical unlocked map set from the title alone.
- Sound mono/stereo, sound test, passwords and save files form part of the UI.
- Open work: complete battle variants/options, loadout economy, every secret
  map/code, all route gates and exact mutually exclusive/stacking interactions.

## C-25 — Neo Bomberman

Sources: [release overview][C47], [detailed campaign/battle guide][C48].

- Neo Geo MVS arcade game with up to two-human co-op and a separate competitive
  tournament. No official AES/CD retail release is established by these sources.
- Enemy-clear campaign, hidden exits, bosses, stage timer, continuation pickups,
  time bonuses and a helper-survival score bonus.
- Difficulty dip switches alter starting equipment and enemy hit points; menu
  settings must be part of reference identity.
- Basic stats, kick/stop, carry/throw, protection, piercing, remote, block/bomb
  passage, added time, eggs, helper cages and skull disease are documented.
- Throw trajectory runs until collision rather than simply inheriting SB3's
  three-tile distance. Landing on a rival stuns and knocks out item panels.
- Organic/mechanical mounts and spare-egg towing resemble SB4 but have a distinct
  roster: max speed, airborne bomb toss, slow mount, destructive sacrifice, bomb
  disguise, kamikaze, disease contact, random charge and block passage effects.
- Freed helper Bombers use remote bombs and grant a clear bonus if retained;
  the guide describes unusual helper invulnerability requiring verification.
- Solo Battle is an arcade sequence against one-to-three CPUs across boards and
  variants; a second human joining switches to one-on-one competitive play.
- Losing the human challenge loses a credit while the winner continues; this is
  not an unrestricted four-human local battle room.
- Arena effects include wall-rebound movement/bombs, warp holes, burnable
  concealing foliage and bomb-redirection arrows.
- Character abilities include rubber-form wall passage, block disguise, random
  stun dash, moving heart bombs, decoy bombs, random teleport, controllable dash
  and stationary timed invulnerability with cooldown.
- Sources disagree on selectable roster size (ten versus twelve). The specialist
  guide enumerates twelve including four coloured Bombers; retain the conflict
  and verify original roster/unlock flags before using a completion denominator.
- Open work: all character/mount names and availability, arcade region revisions,
  one-player/two-player scaling, credit transitions and complete stage inventory.

## C-26 — Atomic Bomberman

Sources: [release/editor overview][C49], [manual-derived items and editor guide][C50],
[network/customisation play account][C51].

- Licensed Windows game developed by Interplay, with prerendered graphics,
  extensive voice lines, death/trapped animations and a different visual identity.
- Traditional free-for-all/two-team battle supports ten participants through
  combinations of local input, CPUs and IPX network play.
- Keyboard has a two-local-player constraint; gamepad remapping support conflicts
  between play accounts, so verify the exact build/driver before claiming it.
- Classic/enhanced presentation/rules choices are reported in the release account.
- Time choices, configurable enclosure depth and gold-winner roulette reward
  let the host create short, long, no-sudden-death or fully enclosing matches.
- Items include extra bombs, flame reach/full fire, skates, boxing glove, carry
  glove, kick/stop, line bombs, Skullz, multi-disease item named Ebola, remote
  trigger bombs, bouncing jelly, slow-down and random item.
- Multiple diseases can coexist. Remote/glove/jelly/line conflicts can eject an
  item rather than silently combine effects; the manual-derived account names
  specific conflicting pairs.
- Carry-glove text describes a suspended fuse while held, with activation after
  landing. This differs from Fight!!, where bombs can explode in the hands.
- The hidden scheme editor is accessed through Ctrl+E inputs. Scheme files define
  layout, hard/soft/floor cells, player starts, team assignment and item density.
- Editor item fields include starting equipment (`BORNWITH`), exclusion from
  random-item results (`FORBID`) and exact/probabilistic quantities (`OVERRIDE`).
- Graphic/theme selection and logical schemes are separate: the same scheme can
  combine with different arena graphics. This is directly relevant to public pack
  APIs that separate stage mechanics from permitted visual skins.
- Density editing, fill-grid tools, renaming, default scheme selection and saving
  are real creator affordances, beyond a claim that the game has custom maps.
- There is a hidden **unfinished** campaign experiment. It is not a complete
  shipped story mode or evidence of campaign parity with console games.
- IPX is a LAN-era protocol. Community IPX wrappers/launchers are later support
  tools, not native TCP matchmaking features of the 1997 executable.
- Open work: actual shipped manual/build, all scheme fields, network limits,
  every arena hazard, AI levels and exact gold-reward scope.

## C-27 — Saturn Bomberman Fight!!

Sources: [release overview][C52], [complete specialist gameplay account][C53].

- Japan-only 1997 Saturn game; a separate 3D isometric battle design.
- Multi-level arenas include slopes, pits, high surfaces and airborne interaction.
  Characters run, jump and backflip/double-jump with constrained airborne steering.
- Health bars replace universal one-hit death. Character stats change health,
  speed, kick/throw distance, jump and special-bomb meter gain.
- Bombs can be placed, carried, kicked, thrown and **caught in flight**. Movement
  state changes throw distance; fuse continues while held.
- Flying-bomb impacts stun and dislodge items. Pickups themselves bounce when
  bombed instead of being destroyed.
- Laying bombs fills a Deca-Bomb gauge. Deca-Bombs produce large circular blasts;
  Super Deca-Bomb is stronger. Both can be caught/thrown, unlike a static grid-only
  explosion architecture.
- Mystery panels yield good/bad effects: super bomb, line bombs, vertically stacked
  Tower Bombs, max flame, speed boost, short fuse, no jump, slow movement, weak
  flame and reversed controls.
- A White Horse mount raises movement/throw ability and erases touched bombs,
  clears status effects, cannot double-jump and disappears at sudden death.
- Story mode follows character-specific voiced battle routes; Battle supports
  up to four players. The guide distinguishes fourteen starters plus unlockable
  Deral, explaining a roster total of fifteen versus shorter release summaries.
- Minibon gives eliminated players tiny limited avatars inside the battlefield,
  a different revenge mechanic from sideline carts.
- Survival is a long CPU gauntlet with retained health/meter and partial recovery.
  High-score/password details are explicitly uncertain in the cited account.
- Handicap changes stats and starting bomb/range equipment. Round target, timer,
  shuffled starts and rain-of-bombs sudden death are configurable aspects.
- Player Info registers eight IDs with name/default character and win/loss/draw
  records. Isometric pad orientation, mono/stereo and CD sound test are options.
- Unlocks include character/arena rewards, bonus arenas and alternate costumes;
  their conditions are documented leads rather than a tested unlock inventory.
- Open work: exact 3D collision/height/blast model, all maps/stats, catch windows,
  damage formulas, status durations, training mode and save persistence.

## Reissues, compilations, demos and prototype boundaries

Sources: [NES editions][C07], [PC Engine conversions][C11], [Saturn editions][C44],
[PC collection one][C54], [PC collection two][C55].

| Edition | Distinct feature or research task |
| --- | --- |
| Bomberman: Users Battle, PC Engine | Fetched [LaunchBox account](https://gamesdb.launchbox-app.com/games/details/34237-bomberman-users-battle) describes battle-only 2–5-player play, a different title screen and no Skull Mode. The 1990 copyright is not a confirmed release date; distribution and build remain open. |
| Bomberman as Bomber Boy's Mode B / Atomic Punk Game Boy bonus | Legacy campaign with smaller/changing field geometry and version-specific timings; catalogue under the handheld game as well. |
| Classic NES Series / Famicom Mini: Bomberman, GBA 2004 | Display scaling/palette/sprite adjustments, wrapper reset/sleep/save menu and saved password handling; not a newly added battle mode. |
| Hudson Best Collection Vol. 1: Bomberman Collection, GBA 2005 | Packages Famicom Bomberman and Bomberman II; preserve each embedded game's controls and multiplayer requirements. |
| Bomberman Collection Vol. 1, Windows | Japan 19 December 2002, later international releases often dated 2003; packages PCE Bomberman/'93 and PlayStation World with PC control configuration. |
| Bomberman Collection Vol. 2 / Bomberman Game Room, Windows | Japan 15 April 2004; packages Super Bomberman 1–3 and PlayStation Bomberman/Party Edition. This is the substantiated 2004 PC release found here. |
| Gate of Thunder/Bonk pack-in disc's hidden Bomberman | Boot code exposes PC Engine Bomberman; portable-link option removed. Do not invent a standalone official title from common fan compilation names. |
| PC Engine '94 Virtual Console / PSN; '93 Virtual Console | Emulator/controller wrappers, regional availability and player-input topology need separate checks; no inferred new campaign mechanics. |
| Flash Sega Saturn Ochikazuki-hen, March 1996 | One-round five-seat Fire Goal demonstration with one human/four CPUs, then reset to disc menu; preview Bomberman SS title differs from final. |
| Super Bomberman 2 gold/promotional and Super Bomberman 5 gold cartridges | Explicit revision/unlock/map inventory needed; a gold shell alone is not a measured rules specification. |
| Factor 5 Mega Bomberman proof of concept | Reported eight-player demonstration; not Westone's shipping four-player adaptation. |
| Super Bomberman Collection, 2026 | Modern compilation is covered in the later-games chapter; wrapper functionality must not be silently attributed to 1990s ROMs. |

No distinct original game named simply **Bomberman for PC (2004)** was established
in these sources. Keep that query as an unresolved alias lead, not an extra row
with invented mechanics. Net de Bomberman and online PC games belong to separate
release families in the wider dossier.

## Reusable eventual feature candidates

These are **planning IDs within this research document**, not a second factory
intake schema and not new implementation-completion records. Deduplicate against
the existing backlog before creating bounded issues. The acceptance column names
an observable slice to specify after original research; it does not claim a test
exists. Every extension must preserve unmodified Saturn defaults, use namespaced
additive content and demonstrate the relevant clean-client sharing journey.

| Candidate | Capability | Documented reference(s) | Eventual acceptance slice |
| --- | --- | --- | --- |
| CLASSIC-001 | Per-release rule profiles | All | Same input fixture uses distinct pinned caps/persistence without cross-profile mutation. |
| CLASSIC-002 | Variable arena dimensions and camera | C-03/05/22 | Non-wide, wide and scrolling fields frame HUD/spawns correctly. |
| CLASSIC-003 | Off-grid bombs and partial block damage | C-01 | Offset blast leaves documented half-block geometry. |
| CLASSIC-004 | Passable versus blocking bombs | C-01/03 | Movement and trap fixture changes only with declared profile. |
| CLASSIC-005 | Four-ray chain-reaction ordering | C-03 onward | Simultaneous chains match independently captured event order. |
| CLASSIC-006 | Remote trigger sequencing | C-03/24/26 | Manual detonation and chain ignition respect ownership/order. |
| CLASSIC-007 | First-slot maximum-power bomb | C-16/20/22 | Only the eligible placed bomb receives the special range. |
| CLASSIC-008 | Soft-block piercing | C-12/21/22 | Flame crosses eligible cells without adopting corner-turning rules. |
| CLASSIC-009 | Splinter/corner-turning flame | C-10 | Junction blast preserves captured remaining reach and branch order. |
| CLASSIC-010 | Invisible contact mines | C-22/24 | Arm, trigger, reveal and delayed blast reproduce separately. |
| CLASSIC-011 | Target-seeking bombs | C-24 | Acquisition, pursuit, target retention and friendly collision are explicit. |
| CLASSIC-012 | Charged impact bombs | C-22 | Charge threshold and impact detonation have captured boundary cases. |
| CLASSIC-013 | Rubber/jelly bounce bombs | C-16/20/22/26 | Kick and aerial bounce follow distinct reproducible trajectories. |
| CLASSIC-014 | Kick with manual stop | C-11 onward | Correct owner/input stops moving bomb before/after hazard entry. |
| CLASSIC-015 | Kick-contact damage | C-12 | Enemy receives non-flame impact damage in this profile only. |
| CLASSIC-016 | Bomb punch | C-12/21/24/26 | Aerial arc, wrap, collision and landing are deterministic. |
| CLASSIC-017 | Carry and throw with profile fuse policies | C-16/22/27 | Suspend/reset/continue variants each reject wrong timer behaviour. |
| CLASSIC-018 | Catch an airborne bomb | C-27 | Catch-window boundaries and rethrow of giant bombs are measured. |
| CLASSIC-019 | Throw another player | C-21/24 | Co-op partner reaches otherwise inaccessible legal route. |
| CLASSIC-020 | Line placement | C-11 onward | Capacity, blocked cells and placement order are explicit. |
| CLASSIC-021 | Vertical stacked bombs | C-27 | Stack interacts correctly with kick/height/catch. |
| CLASSIC-022 | Giant circular blasts and charge meter | C-27 | Meter threshold, impact and radial damage reproduce. |
| CLASSIC-023 | Item exclusion/replacement/ejection | C-24/26 | Conflicting pickup ejects the right prior effect/item. |
| CLASSIC-024 | Multiple concurrent ailments | C-26 | Independent duration/clear/transfer rules remain replayable. |
| CLASSIC-025 | Contagious skull ailments | C-06 onward | Contact, re-contact, timeout and healthy-item cures are explicit. |
| CLASSIC-026 | Global Devil ailment | C-22 | One pickup targets the documented participant set. |
| CLASSIC-027 | Bomb pass and block pass | C-03 onward | Actor movement permission leaves flame/hazard rules independent. |
| CLASSIC-028 | Fire protection versus invincibility | C-03/09/11 | Enemy collision, flame knockback and timeout remain distinct. |
| CLASSIC-029 | Health/Heart/mount damage precedence | C-21/22/27 | One hit consumes the intended layer with correct grace. |
| CLASSIC-030 | Freeze clock | C-11 onward | Enemy/time freeze and contact damage follow profile. |
| CLASSIC-031 | Timed cyclic/random item panels | C-21/26/27 | Capture pickup instant and RNG state; replay selects same effect. |
| CLASSIC-032 | Item scatter from aerial stun | C-24/25/27 | Drops follow captured priority and position rules. |
| CLASSIC-033 | Bombing item/exit spawns enemies | C-03/06/09/11/16 | Spawn type/count/cap match selected release. |
| CLASSIC-034 | Multiple campaign objective types | C-01/03/14/20/22 | Enemy clear, exit, mechanisms and capsule pickup are composable. |
| CLASSIC-035 | Mechanisms carried by enemies | C-14/20 | Enemy death drops mechanism with captured collision behaviour. |
| CLASSIC-036 | Automatic arcade advancement | C-08/10 | Last enemy triggers transition without an exit hunt. |
| CLASSIC-037 | Campaign route graph and revisits | C-14/20/24 | Revisit suppresses cleared objectives while preserving topology. |
| CLASSIC-038 | Multiple endings and second campaign pass | C-24 | Route ending and 100%/200% state persist correctly. |
| CLASSIC-039 | Password and ordinary save variants | C-03/09/24 | Identity/version encoding restores only permitted state. |
| CLASSIC-040 | Co-op shared lives and midgame join | C-24 | Join/death/restart cannot duplicate lives or progress. |
| CLASSIC-041 | Arcade credits and challenge takeover | C-08/10/25 | Join/win/loss/continue reproduces credit accounting. |
| CLASSIC-042 | Per-stage equipment persistence | C-08/22 | Death, stage-clear and continue each apply their own retention table. |
| CLASSIC-043 | Score chains and conditional collectibles | C-03/06/12 | Multi-kill and secret condition track actual event sequence. |
| CLASSIC-044 | Timed stage-clear coin sweep | C-14 | Remaining blocks transform and expire under the correct clock. |
| CLASSIC-045 | Boss forms, shielding and airborne immunity | C-12/16/22 | Captured state boundary rejects damage from an invalid direction/state. |
| CLASSIC-046 | Caged AI companions | C-21/25 | Rescue, autonomous action, survival and reward are explicit. |
| CLASSIC-047 | Organic/mechanical mounts with spare eggs | C-21/25 | Type checks, egg destruction and automatic replacement reproduce. |
| CLASSIC-048 | Louie skill families | C-14/20/24 | Each skill has its own cooldown/movement/damage contract. |
| CLASSIC-049 | Three-stage growing Tirras | C-22 | Campaign meter and battle egg growth remain separate. |
| CLASSIC-050 | Dismount and another rider's adoption | C-22 | Unridden mount persists and transfers without duplicating ownership. |
| CLASSIC-051 | Sacrificial/kamikaze mounts | C-21/25 | Rider survives/detaches while mount attack resolves once. |
| CLASSIC-052 | Stateful mount bomb erasure | C-27 | Horse removes eligible bombs and expires at proper boundary. |
| CLASSIC-053 | CPU archetypes versus character appearance | C-14 | Cosmetic skin and AI preference are independently selectable. |
| CLASSIC-054 | Character-specific competitive abilities | C-21/25 | Capability negotiation and costs apply only in compatible rooms. |
| CLASSIC-055 | Multi-team and asymmetric battle | C-13 | Five pairs, three trios and 1v9 have valid seat/team outcomes. |
| CLASSIC-056 | Wide-battle-specific item and option pools | C-22 | Nine/ten seats reject incompatible items/settings explicitly. |
| CLASSIC-057 | Standard revenge cart | C-21/22 | Eliminated participant moves/throws until cutoff, never scores twice. |
| CLASSIC-058 | Tiny in-arena revenge avatar | C-27 | Limited avatar cannot collect/kick as a living full-size participant. |
| CLASSIC-059 | Temporary absorption/merger | C-22 | Death/expiry releases every captured actor exactly once. |
| CLASSIC-060 | Bonus-introduced roaming hazard | C-22 | Prior reward deterministically adds Bomura to next round. |
| CLASSIC-061 | Winner reward mini-games | C-16/21/22/26 | Roulette, driving and crane outcomes have correct reward scope. |
| CLASSIC-062 | Falling-wall patterns and No Draw | C-11/12/22/26 | Pattern, crush, bomb impact and exhaustion produce captured outcome. |
| CLASSIC-063 | Rain-of-bombs sudden death | C-27 | RNG/time-bound spawn sequence is pinned in replay. |
| CLASSIC-064 | Reversible conveyors and redirect arrows | C-11/14/22 | Actor/bomb motion and reversal inputs resolve consistently. |
| CLASSIC-065 | Warps and looping arena edges | C-11/22/24 | Actor, bomb and flame traversal declare distinct permissions. |
| CLASSIC-066 | Trampolines and seesaws | C-12/21/22 | Weight/order/destination determine measured launch. |
| CLASSIC-067 | No-bomb floor and regenerating blocks | C-11 | Placement restriction and regeneration occupancy are explicit. |
| CLASSIC-068 | Sliding/slow/reverse-control terrain | C-21 | Terrain state changes with bomb input and expires/persists correctly. |
| CLASSIC-069 | Concealment and limited lighting | C-12/14/25 | Visibility differs without deleting authoritative actor/bomb state. |
| CLASSIC-070 | Periodic rain flame suppression | C-22 | Blast reach changes at captured weather phase boundaries. |
| CLASSIC-071 | 3D heights, jumps, pits and slopes | C-27 | Height alters collision/explosion exposure; pit death is deterministic. |
| CLASSIC-072 | Configurable logical arena schemes | C-26 | Layout/spawn/item schema loads independently of visual theme. |
| CLASSIC-073 | Player ID and battle statistics | C-27 | Named profile's win/loss/draw record survives declared save cycle. |
| CLASSIC-074 | Distinct Master/survival gauntlets | C-22/27 | Floor/round progress preserves the right health/items/meter. |
| CLASSIC-075 | Reference-grade menus/audio/controls | All | Native input, text, cue, animation and sound traces match pinned edition. |

## Evidence limits and next research

The sources were fetched on **2026-11-03**. Rich specialist pages are useful
secondary evidence and often reproduce manual text, but many explicitly contain
unfinished sections, guesses or estimated timings. Their original-URL successor
`randomhoohaas.net` was accessible; the older flyingomelette host was not usable.
Fandom fetches were blocked, Sega Retro returned a challenge, and HG101 returned
a maintenance page. Those responses were **not** treated as game evidence.

Attempted SNES manual PDFs were discoverable but produced no extracted text in
the web tool, and the local proxy was unavailable for downloading them. They are
next-source leads, not manuals newly read during this investigation. No private
disc, save, binary, copyrighted art or decompiled implementation is added here.

The immediate useful continuation is a release/region checklist, first for the
existing supplied Saturn references, then per-game manuals and controlled probes
for the interaction candidates above. Unknown denominators include every enemy,
boss phase, room, secret and regional revision, even where this chapter gives a
published headline stage count. A complete list of documented games cannot by
itself establish complete discovery of their features.

## Sources

All links below were fetched for this chapter. Access date: 3 November 2026.

- [C01: Wikipedia, original computer game][C01]
- [C02: Shrine, original MSX gameplay][C02]
- [C03: Generation MSX, 3-D release identity][C03]
- [C04: Lunatic Obscurity, 3-D gameplay account][C04]
- [C05: Wikipedia, 1985 game][C05]
- [C06: Shrine, NES/MSX/Game Boy/PS1 version-aware gameplay][C06]
- [C07: Shrine, NES edition differences][C07]
- [C08: Shrine, NES/MSX/Rupo release inventory][C08]
- [C09: Wikipedia, 1990 game and computer ports][C09]
- [C10: Shrine, PC Engine gameplay][C10]
- [C11: Shrine, PC Engine conversion differences][C11]
- [C12: Shrine, 1991 arcade gameplay][C12]
- [C13: Shrine, 1991 arcade regional changes][C13]
- [C14: Wikipedia, Bomberman II][C14]
- [C15: Shrine, Bomberman II gameplay][C15]
- [C16: Wikipedia, 1992 arcade release][C16]
- [C17: Shrine, 1992 arcade gameplay][C17]
- [C18: Asphodel Gaming, Irem arcade play account][C18]
- [C19: Wikipedia, Bomberman '93][C19]
- [C20: Shrine, Bomberman '93 gameplay][C20]
- [C21: Wikipedia, Super Bomberman][C21]
- [C22: Shrine, Super Bomberman gameplay][C22]
- [C23: StrategyWiki, Super Bomberman power-ups][C23]
- [C24: Wikipedia, Hi-Ten Bomberman][C24]
- [C25: Shrine, Hi-Ten games][C25]
- [C26: Wikipedia, Bomberman '94/Mega Bomberman][C26]
- [C27: Shrine, Bomberman '94 normal/items/Louies][C27]
- [C28: Shrine, Bomberman '94 battle][C28]
- [C29: Shrine, Special Version/Deden no Den][C29]
- [C30: Wikipedia, Super Bomberman 2][C30]
- [C31: Shrine, Super Bomberman 2 gameplay][C31]
- [C32: StrategyWiki, Super Bomberman 2 power-ups][C32]
- [C33: Shrine, Mega Bomberman conversion differences][C33]
- [C34: Shrine, Super Bomberman 3 release][C34]
- [C35: Shrine, Super Bomberman 3 gameplay][C35]
- [C36: StrategyWiki, Super Bomberman 3 modes][C36]
- [C37: Wikipedia, Super Bomberman 4][C37]
- [C38: Shrine, Super Bomberman 4 gameplay][C38]
- [C39: Shrine, Super Bomberman 4 battle][C39]
- [C40: Wikipedia, Saturn Bomberman][C40]
- [C41: Shrine, Saturn normal/items/Tirras][C41]
- [C42: Shrine, Saturn battle][C42]
- [C43: Shrine, Saturn Master][C43]
- [C44: Shrine, Saturn demos/XBAND/regions][C44]
- [C45: Wikipedia, Super Bomberman 5][C45]
- [C46: GameFAQs, detailed Super Bomberman 5 walkthrough][C46]
- [C47: Wikipedia, Neo Bomberman][C47]
- [C48: Shrine, Neo Bomberman gameplay][C48]
- [C49: Wikipedia, Atomic Bomberman][C49]
- [C50: Shrine, Atomic gameplay and editor][C50]
- [C51: Arcadex Machina, Atomic retrospective][C51]
- [C52: Wikipedia, Saturn Bomberman Fight!!][C52]
- [C53: Shrine, Saturn Bomberman Fight!! gameplay][C53]
- [C54: Shrine, PC Collection Vol. 1][C54]
- [C55: Shrine, PC Collection Vol. 2][C55]

[C01]: https://en.wikipedia.org/wiki/Bomberman_(1983_video_game)
[C02]: https://randomhoohaas.net/bomb/msx-1/game.html
[C03]: https://generation-msx.nl/software/hudson-soft/3-d-bomberman/media/169
[C04]: https://lunaticobscurity.blogspot.com/2019/11/3-d-bomberman-msx.html
[C05]: https://en.wikipedia.org/wiki/Bomberman_(1985_video_game)
[C06]: https://randomhoohaas.net/bomb/nes-1/game.html
[C07]: https://randomhoohaas.net/bomb/nes-1/misc.html
[C08]: https://randomhoohaas.net/bomb/nes-1/
[C09]: https://en.wikipedia.org/wiki/Bomberman_(1990_video_game)
[C10]: https://randomhoohaas.net/bomb/pce-1/game.html
[C11]: https://randomhoohaas.net/bomb/pce-1/misc.html
[C12]: https://randomhoohaas.net/bomb/arc-1/game.html
[C13]: https://randomhoohaas.net/bomb/arc-1/misc.html
[C14]: https://en.wikipedia.org/wiki/Bomberman_II
[C15]: https://randomhoohaas.net/bomb/nes-2/game.html
[C16]: https://en.wikipedia.org/wiki/Bomber_Man_World
[C17]: https://randomhoohaas.net/bomb/arc-2/game.html
[C18]: https://asphodelgaming.com/bomber-man-arcade
[C19]: https://en.wikipedia.org/wiki/Bomberman_%2793
[C20]: https://randomhoohaas.net/bomb/pce-93/game.html
[C21]: https://en.wikipedia.org/wiki/Super_Bomberman
[C22]: https://randomhoohaas.net/bomb/snes-1/game.html
[C23]: https://strategywiki.org/wiki/Super_Bomberman/Power-ups
[C24]: https://en.wikipedia.org/wiki/Hi-Ten_Bomberman
[C25]: https://randomhoohaas.net/bomb/arc-hiten/
[C26]: https://en.wikipedia.org/wiki/Bomberman_%2794
[C27]: https://randomhoohaas.net/bomb/pce-94/game.html
[C28]: https://randomhoohaas.net/bomb/pce-94/battle.html
[C29]: https://randomhoohaas.net/bomb/pce-94/sp.html
[C30]: https://en.wikipedia.org/wiki/Super_Bomberman_2
[C31]: https://randomhoohaas.net/bomb/snes-2/game.html
[C32]: https://strategywiki.org/wiki/Super_Bomberman_2/Power-ups
[C33]: https://randomhoohaas.net/bomb/pce-94/misc.html
[C34]: https://randomhoohaas.net/bomb/snes-3/
[C35]: https://randomhoohaas.net/bomb/snes-3/game.html
[C36]: https://strategywiki.org/wiki/Super_Bomberman_3
[C37]: https://en.wikipedia.org/wiki/Super_Bomberman_4
[C38]: https://randomhoohaas.net/bomb/snes-4/game.html
[C39]: https://randomhoohaas.net/bomb/snes-4/battle.html
[C40]: https://en.wikipedia.org/wiki/Saturn_Bomberman
[C41]: https://randomhoohaas.net/bomb/sat-1/game.html
[C42]: https://randomhoohaas.net/bomb/sat-1/battle.html
[C43]: https://randomhoohaas.net/bomb/sat-1/master.html
[C44]: https://randomhoohaas.net/bomb/sat-1/misc.html
[C45]: https://en.wikipedia.org/wiki/Super_Bomberman_5
[C46]: https://gamefaqs.gamespot.com/snes/562899-super-bomberman-5/faqs/79457
[C47]: https://en.wikipedia.org/wiki/Neo_Bomberman
[C48]: https://randomhoohaas.net/bomb/arc-neo/game.html
[C49]: https://en.wikipedia.org/wiki/Atomic_Bomberman
[C50]: https://randomhoohaas.net/bomb/pc-atom/game.html
[C51]: https://arcadestrikerblog.wordpress.com/2017/12/26/strikers-retrospective-atomic-bomberman/
[C52]: https://en.wikipedia.org/wiki/Saturn_Bomberman_Fight!!
[C53]: https://randomhoohaas.net/bomb/sat-sbf/game.html
[C54]: https://randomhoohaas.net/bomb/pc-col1/
[C55]: https://randomhoohaas.net/bomb/pc-col2/
