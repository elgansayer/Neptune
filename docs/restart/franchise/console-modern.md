# Bomberman console adventures, party games and modern releases

Research cut-off: **3 November 2026**. This chapter records publicly documented
features for future Neptune work. It does not claim that Neptune implements them,
that the originals were executed during this audit, or that every stage, item,
character ability and regional difference has been discovered.

The existing factory and Saturn code-recovery programme retains its current
priority. These are eventual additions through selectable profiles and public
content interfaces. Preserve the faithful Saturn defaults, existing feature IDs,
pack version locks, replay identity and clean-client sharing contracts.

## Reading the evidence

- **Primary** means an official page, update notice or instruction manual was
  read. Publisher marketing confirms the advertised feature, not its edge cases.
- **Guide** means a named walkthrough or specialist reference was read. Its
  measurements and completeness remain claims to reproduce in a pinned build.
- **Secondary** means an encyclopedia, database or review was read. Useful for
  catalogue identity and feature leads; insufficient for exact implementation.
- **Unknown** means unresolved here. An omitted feature is not evidence that a
  game lacks it. In particular, service availability needs its own dated evidence.
- Player counts distinguish local controllers, network sessions and mode-specific
  limits. They must not be copied across editions merely because names match.
- Reissues, platform editions and compilations are recorded with their source
  games. A title alias is not automatically an additional independent design.

Source identifiers resolve to the inspected URLs in the register at the end.
All sources were accessed on 3 November 2026 unless explicitly described as a
historical publication date. No ROMs, executable files or extracted game artwork
are included in this document.

## Nintendo 64 adventures and the separate 2001 game

### Bomberman 64 / Baku Bomberman — 1997, Nintendo 64

Identity: *Baku Bomberman* in Japan; *Bomberman 64* internationally. The separate
Japanese game named *Bomberman 64*, released in 2001, is listed below. Later Wii U
Virtual Console distribution is a reissue of the 1997 game. [M01], [M02]

- Fully three-dimensional movement, terrain, camera and adventure puzzles.
- Eight-direction movement; rotating camera with selectable zoom levels.
- Bombs produce a round/spherical blast region rather than the familiar grid cross.
- Kick, pickup and throw are available without first finding those item abilities.
- Holding a carried bomb pumps it into a larger, more powerful bomb.
- Pumped bombs have different handling restrictions; do not treat them as merely
  the small bomb with a larger radius.
- Bomberman cannot perform a conventional free jump. Bombs become stepping stones
  and bouncing surfaces for reaching otherwise inaccessible locations.
- Remote bombs support constructing stable routes and bomb-jumping puzzles.
- Shallow water traversal and dangerous deep water require distinct terrain rules.
- Contact and thrown objects can stun a character; stunned characters can be
  picked up and thrown, including off the arena.
- Heart protection can survive a hit and drop a recoverable heart in Normal play;
  the documented Hard-mode behavior differs.
- Adventure progression initially offers four worlds; puzzle stages alternate
  with rival-bomber and large guardian encounters.
- Gold Cards reward exploration, hidden objectives and boss performance.
- Collecting the initial set of Gold Cards unlocks Rainbow Palace and the true
  final route; further completion unlocks battle content and a Full Power option.
- Multiplayer supports four players in open arenas, including multiple heights.
- Multiplayer death scatters collected power-ups, creating contested recovery.
- Platform edges, falls, stun throws and bomb geometry matter to tactics in ways
  that a flat cross-blast profile cannot reproduce.

Future scope: optional spatial arena and adventure capabilities; authored bomb
bounce routes, pressure/switch puzzles, collectibles and alternate endings.
**Unknown:** exact collision volumes, pumping/fuse clocks, bounce equations, stun
priority, every card condition, costume set, complete arena variants and PAL
differences. The source card totals are discovery leads, not a measured inventory.

### Bomberman Hero: Rescue Princess Millian! — 1998, Nintendo 64

Identity: Japanese subtitle *Mirian-Ōjo o Sukue!*; international *Bomberman Hero*.
Wii Virtual Console release is a later reissue. [M03]

- Platform-oriented solo adventure, with a direct jump and a health meter.
- Moving, jumping and throwing bombs support continuous platform combat.
- Bomb impact behavior differs from simply leaving a classic timed bomb in a cell.
- Ice bombs freeze enemies into movable objects that can become platforms.
- Salt bombs address particular enemies that resist the ordinary arsenal.
- Remote bombs add a distinct detonation control.
- Bomber Marine changes the adventure into underwater travel and combat.
- Bomber Jet provides rail-shooting sections.
- Bomber Copter enables flight sections.
- Bomber Slider provides snowboarding-style sections.
- Stages award scores for collectibles and defeated enemies.
- End-of-stage evaluation compares performance against a target and awards points.
- Planet-level medals aggregate stage performance.
- High completion and hidden Adok bombs lead to additional content and a secret
  final challenge; retain the individual unlock conditions as separate rules.
- Boss-stage performance includes speed of victory in the scoring system.
- The documented game is single-player; this is a sourced mode distinction.

Future scope: platforming campaign profile, transformation-specific movement
controllers, enemy-to-platform effects, score medals and replayable challenges.
**Unknown:** full bomb inventory, every transformation-stage rule, exact medal
thresholds and secret-route requirements. Do not conflate this controller with
the no-free-jump controller in the 1997 adventure.

### Bomberman 64: The Second Attack! / Baku Bomberman 2 — 1999 JP / 2000 US, Nintendo 64

Identity: Japanese *Baku Bomberman 2*; US *Bomberman 64: The Second Attack!*.
Specialist release data lists 3 December 1999 in Japan and 28 May 2000 in the US.
The specialist identifies one or two campaign players and up to four battle
players. [M04], [M05]

- Three-dimensional adventure with bomb pumping and manipulation.
- Cross-shaped explosion behavior returns; the first N64 game's circular blast
  must not be inherited solely because this is its sequel.
- Element crystals provide different elemental bomb effects.
- Environmental and enemy interactions depend on the selected element.
- Pommy is a companion whose development depends on food supplied by the player.
- Pommy evolves into different forms rather than being a fixed cosmetic follower.
- A second human can control Pommy, establishing an asymmetric co-op role.
- A space shop sells heart capacity, battle stages and information about bosses.
- Hidden armor grants bomb-handling abilities without the usual temporary items.
- Armor-related permanent capability and current item inventory are distinct state.
- Astral Knight encounters and crystal collection drive progression.
- The final route and ending depend on earlier boss completion.
- Competitive multiplayer remains a separate four-player mode.

Future scope: data-driven elemental interactions, food-driven companion evolution,
human/AI companion interchange, permanent equipment and conditional final bosses.
**Unknown:** complete element-effect table, Pommy food thresholds and all forms,
shop economics, exact co-op restrictions, armor set, battle rules and every stage.

### Bomberman 64 — 2001, Nintendo 64, Japan

Identity: a distinct Racjin-developed, fully 2D game, not the 1997 *Baku Bomberman*.
Released 20 December 2001. It combines several forms of Bomberman play. [M06]

- Traditional grid-based Bomberman mode: blast obstructions, defeat enemies,
  collect items and find an exit.
- Stages offer two exits, creating branching routes through a run.
- A run leads through a sequence of stages to a boss selected by the route.
- Battle Royale supports up to four players.
- Solo Battle provides free-for-all competition.
- Team Battle divides the participants into paired teams.
- Tandem Battle splits control: one player moves while another places bombs.
- Panic Bomber supplies falling-block matching and bomb-based puzzle attacks.
- The puzzle mode includes solo score attack and a four-player battle option.
- SameGame supplies a separate adjacent-tile-clearing score puzzle.
- Bomberman Park provides a theme park, minigames and medal-gated access.
- Some minigames derive from the Land games; content reuse does not make the
  whole 2001 game a port of *Bomberman Land*.

Future scope: branching short campaigns, shared-controller roles and a hub able
to host distinct minigame/puzzle modules beside standard battles.
**Unknown:** every route node and terminal boss, Tandem timing arbitration,
complete puzzle rules and every Park minigame and medal threshold.

## PlayStation and Sega Saturn strategy/racing branches

### Bomberman World — 1998, PlayStation; later Windows compilation

Identity: this is the PlayStation game, not Irem's arcade *Bomber Man World*.
The specialist dates the Japanese release to 28 January 1998. A later Windows
*Bomberman Collection* includes this game; do not assume all PC behavior is
identical without checking the bundled build. [M07], [M08]

- Isometric presentation retains the traditional grid-and-block game underneath.
- Normal progression requires collecting crystals as well as handling enemies.
- Element-themed planets and Dark Force Bomber encounters frame the campaign.
- Defeated rival bombers and large monsters are separate encounter types.
- The specialist reports five-player battle support.
- Battle arenas can have separated upper and lower pieces of terrain.
- Springs, teleporters and trapdoors connect arena regions.
- Vertical separation requires explicit rules for bomb landing, explosions,
  player collision and visual overlap.
- Challenge Game supplies a separate stage judged on completion speed and score.
- The existence of animal armor is a primary-manual research lead, but the PDF
  extraction failed in this audit; its full ability table is not asserted here.
- Pre-rendered visuals and isometric coordinates require readable placement cues.

Future scope: selectable isometric renderer, crystal objectives, tiered arenas,
transition gimmicks and challenge rankings.
**Unknown:** exact armor inventory, all crystals, items, damage rules, bosses,
arena variants, Challenge scoring formula and the later PC edition's differences.

### Bomberman / Bomberman Party Edition — 1998 JP / 1999–2000 international, PlayStation

Identity: *Bomberman* in Japan/Europe and *Bomberman Party Edition* in North
America. Japanese specialist date: 10 December 1998. Later PSone Classics and
Windows *Bomberman Collection Volume 2* are distribution/port records. [M09], [M10]

- Solo play recreates the NES-style enemy-clear and hidden-door structure.
- A graphics selection offers the old pixel appearance and enhanced pre-rendered
  presentation for that solo design.
- Bomb count, blast range and movement upgrades alter the starting capabilities.
- Remote detonation, wall passage and bomb passage are documented solo upgrades.
- Temporary protection/invincibility is distinct from permanent upgrade capacity.
- Bonus stages allow safe enemy destruction for score and extra-life progression.
- A much-expanded Battle Game accompanies the retro solo mode.
- The specialist reports up to five players in battle.
- Characters and Louies borrow from *Super Bomberman 3* and *4*.
- The encyclopedia describes courses with multiple level variants.
- Character roster, mount behavior and map variants need their own inventories;
  the presence of familiar art does not establish identical movement or abilities.

Future scope: presentation variants over pinned rules; retro campaign packs,
bonus-room scoring and broader battle roster/map configuration.
**Unknown:** all battle options, character abilities, mount colors, regional
release-day differences, hidden stages and exact remake discrepancies.

### Bomberman Wars — 1998, PlayStation and Sega Saturn, Japan

Identity: turn-based strategy game released 16 April 1998; not a standard action
campaign under a different subtitle. [M11], [M12], [M13]

- Quest progression uses a world-conquest structure and a home castle.
- A party contains a required King and selected supporting units.
- Defeating the opposing King decides a battle even if other enemies survive.
- Units have different movement and bomb-placement ranges.
- Movement is constrained along a direction rather than allowing arbitrary turns
  through all squares in a movement allowance.
- Bomb fuses advance in turns; chain reactions still make long fuses dangerous.
- A late-battle rain of bombs prevents indefinite stalling.
- A cleric can delay bombs; an archer can hasten them; a samurai can force a
  nearby bomb toward imminent detonation.
- Witches trade slow movement for distant placement; thieves emphasize mobility.
- Recruitable classes change the available party after encounters.
- The castle supports changing the party and buying support items.
- Soft-block pickups retain familiar bomb-count and blast-range improvements.
- Remote bombs provide controlled activation within a turn-based context.
- Coins support an economy rather than only a high score.
- Items can grant another action, improve stats, extend movement, advance the
  stage timer or delay bombs across the board.
- Multiplayer applies the tactical style to another human opponent.
- The firsthand retrospective describes 15 classes and 25 conquest stages;
  those are source counts awaiting a reconciled per-unit/per-map ledger.

Future scope: optional turn-based scheduler, unit classes, turn-fuse modifiers,
king objectives, party recruitment and tactical content authoring.
**Unknown:** cross-platform differences, full class/action/item tables, AI policy,
simultaneous chain ordering, save migration and exact numeric turn semantics.

### Bomberman Fantasy Race — 1998 JP / 1999 US / 2000 EU, PlayStation

Identity: animal-racing spin-off, later reissued through PSone Classics. It is
distinct from the PS2 *Bomberman Kart* games. [M14], [M15], [M16]

- Riders select Louie or Tirra mounts with different speed, handling, stamina,
  dash and jump characteristics.
- Races pit the player against CPU rivals; a two-human versus mode is separate.
- Mounts accelerate, brake, dash, jump and wall-kick.
- Dash consumes stamina; recovery and stamina items affect sustained pace.
- Bombs can be dropped or thrown; charge duration affects throwing distance.
- Bomb dashing deliberately uses an explosion to gain forward speed.
- Being struck or falling produces recovery/stun rather than permanent elimination.
- Race results award money for buying items, mounts and courses.
- First-place finishes unlock a timed coin-collection bonus lap.
- Mirrored course progression and separate Time Trial records extend replay value.
- Time Trial supports ghost data and recorded best runs according to the secondary
  description; exchange details require direct verification.
- Versus selection depends on the players' save files and available unlocks.
- An optional wager transfers race currency between players; treat this as an
  archival rule, not a mandatory Neptune economic feature.
- Controls can be remapped; camera and HUD views can be selected.
- The HUD can show a course map, proximity radar or neither.
- Louie eggs give speed; Tirra eggs give protection, with stored eggs affecting
  the result. These share an item visual but have mount-dependent semantics.
- Bought items can be reserved separately from the currently collected track item.
- Items include homing/rocket attacks, remote and power bombs, multi-bomb throws,
  protection, high/floaty jumping, rolling attacks, stamina recovery and speed.
- Fake item panels punish opponents who mistake them for safe pickups.
- Item panels can inflict temporary curses instead of granting a benefit.
- Regional shop prices differ in the specialist's comparison; do not encode a
  single economy as universally faithful.

Future scope: racing profile, mount stats, stamina, recoverable combat, ghosts,
course variants, per-profile item panels and optional progression.
**Unknown:** exact physics, all courses/mirror unlocks, curse list, save compatibility,
regional prices and ghost format. Source timings are not measured Neptune targets.

## Dreamcast and GameCube/PS2 adventures

### Bomberman Online — 2001, Dreamcast

Identity: North American Dreamcast release, 30 October 2001. Distinct from the
PC services named *Online Bomberman* or *Bomberman Online*. The encyclopedia
reports the original service closed in 2003; this audit did not independently
test a restoration service. [M17]

- Traditional maze battles use blocks, pickups and timed stationary bombs.
- A Bomblympics campaign teaches modes through themed teams and rival bosses.
- Survival Rule uses last-survivor victory.
- Hyper Bomber Rule requires collecting target panels and reaching the central
  objective, triggering a decisive explosion while protecting the activator.
- Target-panel progress is lost on death, creating interception and comeback play.
- Submarine Rule divides the arena and sends bomb attacks toward the other side,
  creating a real-time battleship-like interaction.
- Panel Paint Rule colors floor cells through the owner's explosions.
- Death changes ownership state, so territory cannot be scored independently
  of the mode's death/reset rule.
- Ring Match Rule scores opponent eliminations and allows respawning.
- The same visual maze/bomb system therefore supports elimination, collection,
  territory and score-with-respawn objectives.
- Original network functionality and surviving offline modes are separate features.

Future scope: reusable objective modules, target-panel collection/activation,
cross-arena attacks, paint ownership and score-respawn rules.
**Unknown:** exact local/online seat limits and combinations in each mode, timer
values, complete items, roster, costumes, ranks, matchmaking and network protocol.

### Bomberman Generation — 2002, GameCube

Identity: GameCube adventure followed by *Bomberman Jetters*. June 2002 releases
in Japan/North America, later 2002 in Europe; sources differ on individual US
shipping days, so the year is the stable catalogue identity here. [M18], [M19]

- Cel-shaded three-dimensional adventure with puzzles and large bosses.
- Worlds combine traversal, environmental bomb puzzles and minigames.
- Befriended Charaboms provide abilities and participate in creature battles.
- Charabom merging combines companions into stronger forms.
- Bomb merging combines bombs with other ingredients to create new bomb types.
- Upgrades increase movement speed and bomb strength.
- Different boss encounters require different strategies.
- Battle play returns to constrained classic movement instead of reusing all
  adventure freedom.
- Four human or CPU players can participate in battle.
- Standard Battle uses last-survivor victory and late pressure-block shrinkage.
- Item-frequency options are documented for Standard Battle.
- Reversi Battle changes floor panels to the attacking player's color and permits
  opponents to overwrite those panels; count territory when time ends.
- Coin Battle reveals coins in barrels; death removes part of a player's hoard.
- Hige Hige Bandits can steal coins; defeating them returns coins and items.
- Dodge Battle removes normal bomb placement and rains bombs from above.
- Dodge participants retain manipulation/mobility tools such as kick and punch.
- Falling-bomb blast regions are telegraphed on the floor.
- Revenge Battle places players in the revenge position to score hits on moles,
  distinguishing stuns from explosive defeats.

Future scope: Charabom/bomb recipes, companion battles, coin economies inside a
match, NPC scavengers, telegraphed survival waves and perimeter minigames.
**Unknown:** complete Charabom growth/fusion recipes, every bomb and ability,
arena list, CPU settings, revenge targeting, item weights and exact mode scoring.

### Bomberman Jetters — 2002 JP / 2004 US, GameCube and PlayStation 2

Identity: console adventure derived from *Generation* and the anime. It is
distinct from GBA *Densetsu no Bomberman* and *Game Collection*. Only the GameCube
edition received the documented North American release. The GameCube and PS2
rendering styles differ; the US opening omits the Japanese theme song. [M20]–[M23]

- Adventure uses both Bomberman and Max in a mission to stop Dark Star.
- Bomb placement, pickup, charge and throw support environmental puzzles.
- Thrown bombs can stun enemies, while charged bombs handle larger obstacles.
- The inspected walkthrough includes swimming through Sharkun, companion-gated
  revisits, switch bridges, water spouts, teleporters and destructible spawn sites.
- Heart pieces and Jetters/Hige Hige cards encourage revisiting completed areas.
- Collectible retention can depend on finishing the level after retrieval.
- Charabom abilities open routes that are inaccessible on the initial visit.
- Four-player battle has Standard, Battle One-Two, Battle for Balloms and
  Knockout Battle variants.
- Battle One-Two requires stepping through numbered objectives in order; damage
  disrupts progress and allows rivals to take over the sequence.
- Battle for Balloms escorts followers to a gate; larger deliveries increase
  reward while slowing the escort, and a golden follower changes scoring.
- Damage can remove score/followers, and attacks on the following chain can break it.
- Knockout Battle uses explosion knockback and falling off rather than ordinary
  instant explosion death; defensive directional input affects displacement.
- Character-specific Killer Shots add temporary special abilities.
- Bomberman's special rapidly charges carried bombs; Max temporarily receives
  broad bomb, range, speed and manipulation power.
- Mermaid Bomber removes ordinary bombs from the arena.
- Thunder Bomber stuns with lightning; Flame Bomber and Mighty provide different
  protection effects; Grand Bomber disrupts bomb/player positions.
- Hige Hige Bandits temporarily freeze other participants; Mujoe rushes and
  dislodges a target's items. Team interaction must be tested separately.
- Bomb Up, Fire Up and Speed Up change capacity, reach and movement.
- Kick includes an explicit stop control; Punch moves bombs over intervening cells.
- Power Glove and Super Power Glove differ; the latter can create a Dangerous Bomb.
- Line Bomb, Remote Control, Power Bomb, Bouncing Bomb and Pierce Bomb provide
  different placement, activation, first-bomb, rebound and block-penetration rules.
- Heart, Safety Vest, Sandals and Poison supply survival, protection, speed loss
  and diseases. Some items cannot be assigned through item selection.
- The battle guide documents mutually exclusive item families; picking up an item
  may replace another capability instead of simply stacking indefinitely.
- Diseases include slow/fast movement, involuntary bombs, no bombs, fuse changes,
  forced running, reversed controls, weakened capacity and position swapping.
- Go Go Lorry supplies a ride that traverses routes, stuns rivals and breaks blocks.
- See Saw Park launches objects/players from opposite ends; raised terrain also
  affects bomb movement and blast obstruction.
- Changing Weather changes fuse/range/wind behavior over time.
- Rocket de Boom launches triggered rockets that return as explosive hazards.
- Mini Mini Light changes size and movement; Bouncing Ring rebounds characters
  and bombs at the boundary; Zoom-Up Stage changes available arena space.
- Stage A/B variants differ in layout and/or initial equipment.
- Optional Dig'em Bomber follows Standard Battle: the winner selects buried
  rewards, participants dig, and a successful winner can carry an item forward.
- Setup includes sudden-death variants, item selection and the between-match
  minigame; exact limits must be recovered from the selected edition.

Future scope: sequential objectives, escort-chain scoring, ring-out damage,
temporary character abilities, weather, launchers and configurable series rewards.
**Unknown:** complete campaign/battle inventories and interaction timing. The
2004 guide's second counts, distances, caps and damage fractions are hypotheses
for original-build experiments, not trusted exact constants for implementation.

## PlayStation 2 kart, online and theme-park games

### Bomberman Kart — 2001 JP / 2003 EU, PlayStation 2

Identity: kart-racing spin-off. The encyclopedia and contemporary-review lineage
place the European release in 2003; one specialist page instead prints 2004.
Preserve that discrepancy until product codes/release notices resolve it. [M24]–[M26]

- Character and vehicle selection are separate.
- Track items include bombs, homing/wall-rebounding rocket attacks and boosts.
- Drifting and corner speed are meaningful driving controls.
- A firsthand retrospective identifies use of PS2 pressure-sensitive face buttons.
- Local racing supports a Multitap and four players in the original version.
- Traditional non-kart Bomberman battle is an additional mode.
- Cup progression and track competition coexist with familiar bomb combat.

Future scope: optional kart rules, controller pressure calibration, separate
rider/vehicle definitions and shared battle access from a minigame hub.
**Unknown:** full track/vehicle roster, item inventory, battle settings, regional
button behavior and whether a digital-only input fallback matches the original.

### Bomberman Kart DX — 2004, PlayStation 2, Japan

Identity: enhanced redesign released 15 April 2004, rather than an international
alias for the first Kart. [M25], [M26]

- Revised graphics, camera/HUD, speed and handling.
- Additional tracks, modes and presentation/gallery material.
- GP racing supports two local racers here; do not copy the first Kart's four
  racing seats onto DX. The traditional battle mode has its own capacity.
- A separate mission-based racing story extends beyond ordinary cups.
- One cup can remove items for a driving-focused competition.
- Traditional customizable Bomberman battle remains available.
- A distinct two-player co-op dungeon adventure adds an action-RPG branch.
- Dungeon movement/combat uses health rather than ordinary one-hit elimination.
- The dungeon arsenal includes bombs, a sword, boomerang and shield.
- Bombs in this adventure have circular areas of effect.
- Temporary speed/power buffs coexist with lasting equipment upgrades.
- Chests, armor, bomb types, NPCs and regional bosses support progression.
- Important dialogue is visually highlighted, an interface detail worth preserving
  when studying navigation and localization.
- The secondary encyclopedia describes downloadable extra races using PS2 HDD
  and Network Adaptor; this audit has no retained original expansion package.

Future scope: race missions and optional equipment-based co-op campaigns, using
the same authoring platform without forcing those controllers into Saturn mode.
**Unknown:** complete DLC identity and availability, all missions/gear, co-op
join rules, per-mode capacities and differences between disc revisions.

### Net de Bomberman — 2004, PlayStation 2, Japan

Identity: network-focused PS2 release, commonly dated 19 February 2004. IGDB's
header and detailed release record differ by a day; the detailed record agrees
with the other database. It is not silently grouped with the Dreamcast title.
[M27], [M28]

- Public descriptions advertise up to eight network participants.
- Subscription-based online play was part of its original delivery model.
- The consulted database describes classic grid maps, item collection and enemy
  defeats to unlock further stages.
- Online chat is documented in that database description.
- It describes no offline play and a now-defunct original service.
- The same description calls it a Dreamcast port, but the listed developers and
  other service histories need reconciliation; lineage is **unresolved here**.
- Original access requirements, server dependency and preservation state must
  accompany any attempt to make an executable behavior specification.

Future scope: historical reference for network rooms/chat and service-dependent
progression; Neptune's player-hosted requirement remains its own product contract.
**Unknown:** actual mode list, complete maps/items, account/progression details,
precise shutdown date, PS2 hardware requirements and relationship to PC services.

### Bomberman Land — 2000, PlayStation, Japan

Identity: original theme-park game, released 21 December 2000. Separate from
the later PSP and Wii games also titled *Bomberman Land*. [M29]

- Story play explores a theme park with NPCs, quests and minigame attractions.
- Progression collects B-CARD pieces and opens further park content.
- Minigame scores contribute to exploration/progression rather than only a
  disconnected menu of score attacks.
- The secondary account gives a 125-piece objective, awaiting per-piece inventory.
- Multiplayer minigame play and classic Battle Pack coexist with story play.
- Park exploration and standard bomb-grid combat need distinct controllers.

Future scope: a creator-authored hub, quest items and minigames that unlock
story branches. **Unknown:** complete attractions, controllers, piece conditions,
capacity by mode, classic battle options, saves and secrets.

### Bomberman Land 2: The Biggest Theme Park in Game History — 2003, PS2/GameCube, Japan

Identity: PS2 release 17 July 2003; GameCube 31 July 2003 in the consulted
encyclopedia. The guide identifies multiple separately selectable games. [M30], [M31]

- Land Mode is a solo exploration/RPG hub with minigames and zone-piece progress.
- Classic Battle Mode supports up to four participants according to the guide.
- A racing mode supports up to four players, separate from the adventure.
- Additional puzzle modes extend the compilation beyond one ruleset.
- A Bompad tracks collected pieces and supports navigation/progression.
- Side quests involve talking to NPCs, buying contextual tools, locating missing
  characters and bringing followers back to destinations.
- Shops sell useful exploration objects instead of only battle statistics.
- Learned dash and power-glove interactions can expose hidden pieces.
- Quizzes, imitation challenges, rides and minigame performances supply pieces.
- Some events depend on revisiting earlier areas after later progress.
- Mail/event notifications and NPC state changes connect distant park regions.
- The guide includes inventory, name, text-speed and save/end controls.

Future scope: quest-state graph, explicit revisits, hub mail, contextual tools,
piece journal, minigame modules and readable save navigation.
**Unknown:** every piece, attraction and puzzle rule; complete Battle/Racing
options; PS2 versus GameCube differences and reward economy.

### Bomberman Land 3 — 2005, PlayStation 2, Japan

Identity: released 4 August 2005; a later Hudson The Best edition is a reissue.
The specialist's entry is explicitly unfinished and supplies little behavior
evidence. A separate database confirms the zone-piece/minigame progression.
[M32], [M33]

- Explore theme-park zones and collect pieces by beating minigames.
- Piece collection opens further zones and advances the park adventure.
- A classic Battle Mode is a research lead from the searched gameplay listing;
  its detailed rules were not recovered in this pass.
- Public guides/videos exist, but a guide index is not evidence that its entire
  walkthrough was inspected or that all attractions were enumerated.

Future scope: retain a distinct game record and research its actual additions
instead of copying Land 2's feature list into it.
**Unknown:** complete mode/minigame inventories, story flags, battle capacity,
phone games, character customization, save behavior and exact changes from Land 2.

### Bomberman Hardball / Bomberman Battles — 2004 JP / 2005 EU, PlayStation 2

Identity: *Bomberman Battles* in Japan and *Bomberman Hardball* in Europe. The
consulted encyclopedia dates the releases to 7 October 2004 and 1 July 2005.
[M34]

- A four-part package: classic battle, baseball, golf and tennis.
- Life Mode supplies a house, interactive objects, customization and naming.
- A television lets the player watch computer-controlled demonstrations.
- Coins earned by playing purchase randomized costume rewards from a machine.
- The customized character can be used in the documented battle play.
- Classic Battle uses last-survivor Bomberman competition.
- Star Battle collects stars, Crown Battle races toward a crown and Point Battle
  scores opponent defeats.
- Replay saves battle sessions to memory card for later viewing.
- Baseball offers exhibition and a pennant/league structure against CPU teams.
- Automated aiming/baserunning and optional automatic fielding change input load.
- Golf offers exhibition and tournament structures across an 18-hole course.
- Timed button presses control shot power and accuracy.
- Tennis supports singles/doubles, court surfaces, configurable sets/games,
  exhibition and tournaments.
- House controls expose options, calendar, naming, customization and the shop.

Future scope: match replay, persistent cosmetic identity, AI demonstrations,
accessible automation options and optional sports modules.
**Unknown:** complete sports controls, CPU difficulty, unlock tables, replay
format, cosmetic attributes and each mode's exact local capacity.

## Xbox 360, PlayStation 3 and Wii

### Bomberman: Act Zero — 2006, Xbox 360

Identity: intentionally different visual/style branch, released in 2006.
The encyclopedia dates the North American release to 29 August. [M35]

- A darker mechanical character style with body/gender customization.
- Overhead classic-style navigation around pillars and destructible obstacles.
- Standard mode uses single-hit death.
- First-Person Battle is the mode's name, but the documented camera follows
  behind the character; do not misdescribe it as a literal first-person view.
- FPB supplies camera manipulation and a health meter for multiple hits.
- Speed, bomb count, strength and duration upgrades are documented.
- A long survival structure reaches 99 floors.
- Death requires restarting the run; the source specifically criticizes the lack
  of checkpoint continuation, rather than merely omitting a save feature.
- World Battle is documented as online-only with up to eight players; its current
  reachability and exact original network requirements were not tested.

Future scope: optional survival runs, health-based battle profile, camera variants
and visibly distinct custom avatars. **Unknown:** complete settings/items, damage
scaling, online state, replay/rank features and every floor difference.

### Bomberman Live — 2007, Xbox 360 / Xbox Live Arcade

Identity: released 18 July 2007; later included in an Xbox Live Arcade retail
pack. *Ultra* is separately recorded because its platform/local capacity differs.
[M36], [M37]

- Competitive battles use destructible bricks, pickups and last-survivor rounds.
- Battle sets end when a configured win target is reached.
- Tournament play instead uses a configured number of rounds.
- The consulted sources describe eight online participants and four local ones.
- Character appearance is customizable.
- Downloadable content and release editions require their own content identities.
- CPU matches and online competition must be measured as separate populations.

Future scope: win-target sets versus fixed-length tournaments, cosmetics and
versioned expansion content. **Unknown:** every arena/gimmick, all bombs/items,
costume components, DLC roster, tournament tie rules and current service state.
No shutdown claim for Live is made in this document.

### Bomberman Ultra — 2009, PlayStation 3 / PlayStation Network

Identity: downloadable PS3 release dated June 2009, later in PAL regions.
One specialist page prints 2008 for the US entry; the other consulted identity
source dates the release to 2009. Preserve the distinction instead of using that
apparent typo to create an additional release. [M37], [M38]

- Related to the *Live* battle design, but packaged as a separate PS3 release.
- Source describes eight-player online battles and up to seven local controllers.
- Appearance customization uses combinations of outfit parts.
- The encyclopedia says the full outfit selection is available from the start;
  verify actual menus and edition before treating that as a progression contract.
- The widely advertised combination count reflects combinatorial cosmetics, not
  that many independently modeled playable mechanics.

Future scope: large local sessions, independent appearance slots and immediately
selectable compatible content. **Unknown:** complete stages/items/options,
relationship to Live DLC, online/current service status and all regional content.
No official Ultra shutdown notice was inspected here.

### Bomberman Live: Battlefest — 2010, Xbox 360 / Xbox Live Arcade

Identity: Pi Studios sequel to *Live*. The official Xbox store dates release to
8 December 2010; a specialist page instead prints 15 December. Prefer the
platform's release record pending a regional/revision reconciliation. [M39]–[M42]

- Traditional Battle plus free-for-all/team variations of additional objectives.
- Zombie and Paint Bomb turn the arena floor into contested colored territory.
- Capture the Flag carries an opposing team's flag back to base.
- Capture the Crown competes on time holding the crown.
- VIP makes protecting a designated participant central to team success.
- Bankroll gives money that can be exchanged for items during its ruleset.
- Xbox Live avatars can be used beside customizable Bomberman appearances.
- The inspected review reports four local and eight online participants.
- Arenas include Adventure Island, a pirate ship and a futuristic laser arena.
- Laser strikes are environmental hazards rather than just player bomb effects.
- Wind can affect bomb behavior in themed arenas.
- The boat's tilt can move crates/bombs, coupling the board state to physics.
- Offline CPU battles provide solo access to the competitive rules.
- Public product descriptions mention additional cluster/rocket/laser bombs;
  their names are leads until each mechanic is verified in a selected release.
- The official store lists Xbox One/Series backward compatibility; that is not
  evidence of a native remake or cross-play with unrelated Bomberman games.

Future scope: objective composition, team roles, match economy and moving boards.
**Unknown:** exact differences between Zombie and Paint Bomb, all item semantics,
content pack boundaries, score/reset rules, maps and contemporary server health.

### Bomberman Blast / Wi-Fi 8-Nin Battle Bomberman — 2008, Wii

Identity: distinguish the Japanese retail disc titled *Bomberman* from the
WiiWare battle release, *Wi-Fi 8-Nin Battle Bomberman* in Japan and *Bomberman
Blast* internationally. They share battle interoperability in the historical
description, but the retail game has additional modes/content. [M43]

- WiiWare supplies the traditional battle game.
- Japanese retail adds a story campaign and a beginners' tutorial mode.
- Story progression covers themed worlds, enemy families and boss rescues.
- Retail shops exchange collected gems for hearts and bomb/range/speed upgrades.
- Miis are usable in the documented game.
- Rocket flight and shield items add active defensive/traversal actions.
- Some item actions use shaking the Wii Remote.
- Wii Remote held sideways and GameCube controller input are documented options.
- Eight local participants use four Wii Remotes and four GameCube controllers.
- Historical online play supports eight participants and rankings.
- Retail and WiiWare users can historically play each other.
- WiiWare and retail arena counts differ; the source gives ten versus twelve.
- Appeal motions/emotes are selectable, with different edition inventories.
- The source describes widescreen and progressive display options.

Future scope: controller mixtures, tutorial pack, emotes, flight/protection items,
edition-aware content locks and a beginner-to-online path.
**Unknown:** exact item activation windows, complete maps, story content, online
shutdown/restoration state and edition/console hardware differences. Wii Family
Edition/mini hardware cannot be assumed to expose GameCube controller ports.

### Bomberman Land / Bomberman Land Wii — 2007 JP / 2008 international, Wii

Identity: a separate Wii entry from both the PS1 original and PSP game. Japanese
release 8 March 2007; North American release 29 January 2008. Consulted sources
differ on the PAL March day, so this document uses the year. [M44], [M45]

- Theme-park exploration spans zones with minigame-driven progression.
- Collecting pieces restores the fractured park and advances the adventure.
- An attraction menu allows replaying completed minigames.
- Promotional copy advertises 50 minigames, including skateboarding and Laser Ball.
- Multiplayer attractions support up to four players in the consulted description.
- Classic Bomberman Battle remains a separate included game.
- Character customization supports a persistent personalized appearance.
- Wii motion/input demands differ from the PSP entry even when themes overlap.

Future scope: minigame replay, accessible motion alternatives, hub progression and
shared cosmetics. **Unknown:** every attraction and control scheme, exact Battle
settings, character parts, per-attraction capacities and score thresholds.

## Super Bomberman R family and the 2026 collection

### Super Bomberman R — 2017 Switch; 2018 PS4/Xbox One/Windows

Identity: the first R game. Updates materially expand it, so launch, 2.0, 2.1
and 2.2 must be distinguished when creating a feature specification. [M46]–[M50]

- Story Mode supports one player or two-player co-op.
- The official page advertises more than 50 levels with themed worlds and bosses.
- Battle Mode supports up to eight participants; the Switch page describes local
  multi-system play using up to four Switch consoles.
- Arenas include standard layouts plus height, gaps, movement and terrain gimmicks.
- Named stages on the official page include Pitfall Zone, Old-school, The Great
  Wall, Magnetic Sphere, Medieval, Slippery Garden, Junkyard and Labyrinth.
- Additional named stages include White Cross, Lagoon, Max Speed, Power Zone,
  Plain Floor, Desert Fort, Classic Conveyor Belt, Panic Factory, Nine Areas and
  Critical Path. The names establish an inventory lead, not their collision maps.
- Online leagues give progression distinct from story completion.
- Purchasable/unlockable characters and cosmetic accessories extend the roster.
- Crossover characters can have special abilities, so appearance and gameplay
  capability must not be conflated in pack compatibility.
- Platform-exclusive characters differ: MAX on Switch, Ratchet on PS4, Master
  Chief on Xbox One and P-Body on Windows are documented examples.
- Grand Prix, added after launch, supports 1v1, 2v2 and 3v3 team competition.
- Grand Prix totals two rounds; the team with the highest resulting score wins.
- Basic Bomber scores defeated opponents and provides limited-life respawns.
- Eliminating the whole other team can end Basic Bomber as a perfect result.
- Crystal gathers team resources; mistakes lose crystals/points, and collecting
  the entire supply can immediately end the game.
- Grand Prix ties use a mistakes/deaths criterion in the official description.
- Checkpoints adds occupation gauges, recapture and score for held territory.
- Holding all checkpoints for the required duration can produce a perfect victory.
- Civilians escorts Balloms from the other team's base; followers slow movement.
- Castlevania/Bloody Tears maps and Mother Base/Frontline accompany the added rules.
- Official character pages name abilities including portals, mediation, Ninja Run,
  Speed Up, Arcane Slash, Zero Shift and Dark Curse; each needs a versioned contract.
- Patch notes distinguish control/online fixes from newly added modes/content.

Future scope: multiple cooperative stories, respawn/team objective plugins,
character capabilities, ranked records and explicit platform content selection.
**Unknown:** full version-specific item/character ability table, all arena variants,
story collectibles, networking behavior and local/network seat combinations on
each platform. Cross-platform ports do not establish cross-play for the first R.

### Super Bomberman R Online — 2020 Stadia / 2021 other platforms; closed 2022

Identity: separate online-only game. Stadia launch 1 September 2020; PS4,
Xbox One, Switch and Windows launch 27 May 2021. Konami explicitly ended all
platform services on **1 December 2022**. [M51]–[M56]

- Battle 64 accommodates up to 64 participants across interconnected maps.
- The manual identifies sixteen maps shown in a minimap.
- Battle and Movement phases alternate.
- Gates open during movement, letting participants migrate to adjacent maps.
- Maps seal at the end of a movement phase; remaining there is fatal.
- HUD signals the current map, closed maps, phase time and life hearts.
- A sole remaining player on a map receives a falling bonus block to break for items.
- Character starting/capped statistics and special abilities change selection tactics.
- The roster includes Bomberman siblings and Konami/non-Konami crossovers.
- Quick Match chooses opponents for Battle 64.
- Private rooms historically support Battle 64, Standard and Grand Prix.
- Hosting requires a paid entitlement in the inspected official pages; one manual
  calls it Platinum Pass while the product page calls it Premium Pack. Preserve
  this wording/version discrepancy rather than inventing two compatible products.
- Standard supports up to sixteen solo/team participants in its manual.
- Standard uses sets and revenge carts for eliminated players.
- Revenge carts attack from outside the board and have a boost input.
- Sudden Death drops pressure blocks from outside toward the center.
- Simultaneous survival until crushing can yield a tied set.
- Grand Prix has Basic Bomber and Crystal, supporting 1v1, 2v2 and 3v3.
- Grand Prix uses two rounds, team scores, life exhaustion and respawn rules.
- Private-rule customization and room invitations are advertised.
- Orion Town is restricted to Quick Match in the official product page.
- Stadia Crowd Play lets a viewer follow a stream link into the streamer's game;
  this is platform-specific historical functionality, not a current Stadia service.
- Outfits, accessories, bomb skins, blast visuals, taunts, speech bubbles and icons
  extend presentation and social expression.
- Player levels, stars, rank gauges, challenges and Bomber Pass rewards coexist.
- Free and paid reward tracks, shop currency and season changes are documented.
- Seasonal Event Battles can temporarily alter the normal conditions; Mighty Fest
  begins with maximum firepower and bomb count.
- Soma Cruz's announced ability temporarily copies/seals abilities via bats,
  demonstrating interaction beyond ordinary damage/stun.
- The official shutdown notice also ends sales of Bomber Coins/Premium Packs;
  archival economic details must not be presented as products to buy now.

Future scope: multi-arena survival, area evacuation, public/private rooms, spectator
entry hooks and entirely optional cosmetic progression. Player-hosted preservation
is a Neptune requirement, not a feature inferred for this closed service.
**Unknown:** exact network protocol, full character caps/cooldowns, every season,
matchmaking populations, all event variants and service-independent replayability.

### Super Bomberman R 2 — 2023, Switch/PS4/PS5/Xbox One/Series/Windows

Identity: a separate paid sequel, released in September 2023. The official US
page distinguishes 12 September physical from 13 September digital; regional
dates differ. A fully fetched official Konami launch announcement explicitly
confirms crossplay. [M57]–[M64], [M70]

- Standard supports up to sixteen participants in its mode specification.
- That is an **online/mode capacity** statement, not proof of sixteen local controllers.
- Standard supports multiple sets and surviving solo/team victory.
- Battle 64 returns from R Online, using migration between shrinking areas.
- Grand Prix supports teams of up to three under Basic Bomber and Crystal rules.
- Castle introduces asymmetric attackers versus defenders, maximum sixteen total.
- Attackers collect keys and touch treasure chests while carrying a key.
- Defenders win by keeping at least one chest safe until time expires.
- The defender uses authored terrain/gimmicks, Ellons and a selected weapon.
- Three defender weapon types have gauges charged by conditions during play.
- Stage Editor specifically authors Castle stages; do not advertise a general
  campaign or arbitrary Standard-stage editor from that evidence.
- Templates and random setup assist stage construction.
- Creators place walls, obstructions and surprise gimmicks.
- The creator must clear/test a stage before uploading it.
- Tags help discover uploaded stages.
- Players search for and download stages created by others.
- Story play explores planets, destroys obstacles and solves puzzles with bombs.
- Ellons support progression and defense; their story role differs from a
  freely programmable creator companion system.
- Grade Match supplies ranked competition; Room Match supplies private settings.
- Update 1.2.2 allows selecting battle rules in Grade Match; launch rotation
  behavior must not be documented as immutable current behavior.
- Update 1.3.0 adds Room Lobby and entry while a battle is already running.
- That update extends selectable Standard round count to 99 in private/offline play.
- Results can continue with the same settings.
- A setting skips waiting after all players finish selecting characters.
- Update 1.3.1 adds lobby Refresh and Friends sorting.
- It also merges Basic Bomber/Crystal grades under Grand Prix.
- Patch notes change continuous stun and some character/gimmick traversal; those
  are version-dependent interaction leads, not proof bugs persist today.
- Bean Bomber and Luca Blight Bomber are documented additions; the latter's
  initial in-game Bright/Blight spelling error is explicitly noted by Konami.
- Achievements, Challenges, earned gems and unlocks need separate persistent records.

Future scope: asymmetric objective API, bounded stage editor, mandatory playtest,
tag/search/download flow, cross-play and usable room lobbies.
**Unknown:** exact offline capacities/controller mixtures, full editor object
limits, upload moderation/revisions, character balance, all story progression,
weapon charge thresholds and current service health. No original game was run.

### Super Bomberman Collection — 2026, Switch/Switch 2/PS5/Series/Windows

Identity: official 2026 compilation. Digital release **5 February 2026**. The
current US page lists physical release **25 September 2026**, superseding an
earlier launch announcement that promised August. [M65]–[M67]

- Launch compilation contains NES *Bomberman*, *Bomberman II*, and *Super
  Bomberman* 1–5: seven source games before the later addition.
- *Panic Bomber W* arrives through a free update announced as available on
  **20 August 2026**, bringing the current advertised total to eight titles.
- Source games retain their separate catalogue identities; the collection is
  also a product record for its new wrapper and support functions.
- Multiple regional versions of the Super games are selectable according to the
  official launch listing, rather than being automatically equivalent data.
- *Super Bomberman 4* and *5* gain official English-localized versions.
- Save/Load Anytime supports resuming difficult content.
- Rewind allows undoing mistakes, including self-destruction.
- Boss Rush supplies consecutive boss fights and Time Attack.
- The launch announcement gives Boss Rush three difficulty settings.
- Save/Load Anytime and Rewind are unavailable in Boss Rush.
- *Panic Bomber W* does not receive a Boss Rush mode.
- Gallery collects roughly 200 character illustrations in the official description.
- BOMB Radio plays archived music, including W tracks added with its update.
- The current page exposes a separate sound playback function.
- Nintendo Switch 2 Edition supports GameShare locally and through GameChat.
- Other players can participate through the advertised sharing feature without
  each owning a copy, subject to Nintendo's actual GameShare conditions.
- Switch 2 TV output supports up to 4K on compatible equipment.
- An upgrade pack allows existing Switch owners to acquire Switch 2 Edition.
- The page explicitly excludes Camera Mode compatibility.
- Collector/Deluxe/standard physical packaging is a product-edition distinction,
  not evidence of extra combat rules.

Future scope: reference-specific rewind/practice states, boss challenge playlists,
sound/gallery browser, language variants and single-copy session sharing where
supported by the chosen runtime/distribution model.
**Unknown:** exact emulation fidelity, every version difference, save compatibility,
all practice restrictions, network/local capacities by source game and regional
store entitlement. Earlier seven-game advertisements remain accurate for launch;
they do not contradict the later eight-game update.

## Unreleased title that must remain separate

### Bomberman 2001 — PlayStation 2 development lead, unreleased/unresolved

The specialist traces a title name in third-party PS2 lists and a fan's E3-era
account, but calls the evidence anecdotal and the relationship to any released
game speculative. [M68]

- Preserve the name as a development/cancellation lead, not a released game.
- No verified public feature inventory is established by this research.
- Claims it became *Jetters* or *D.N.A.: Dark Native Apostle* are hypotheses,
  explicitly labeled speculation in the inspected specialist article.
- Do not turn a plausible development relationship into committed gameplay scope.

## Eventual capability candidates

These IDs are **research-note references**, not a replacement task scheduler or
new implementation status database. Reconcile them against the existing backlog
before creating bounded issues. All are proposed/unverified in Neptune here.

| Note ID | Candidate capability and source designs | Concrete later acceptance slice |
| --- | --- | --- |
| MODERN-001 | Spatial bomb geometry: N64/Generation/Kart DX | An authored obstacle scenario distinguishes spherical from cross blasts and replays identically. |
| MODERN-002 | Bomb pumping and handling restrictions: N64/Jetters | Small/pumped bombs have measured carry/kick eligibility and blast geometry. |
| MODERN-003 | Bomb stepping and bouncing traversal: N64 | A player completes an authored multi-height route using bombs; forbidden jumps remain unavailable. |
| MODERN-004 | Stun, carry and throw actors: N64 | Human/bot interactions resolve simultaneous pickup, recovery and edge falls deterministically. |
| MODERN-005 | Dropped recoverable protection: N64 | Damage consumes/drops a heart under the selected difficulty without duplicating it. |
| MODERN-006 | Gold-card challenge predicates: N64 | Hidden-object, time and boss conditions unlock only the correct route. |
| MODERN-007 | Platforming controller: Hero | Jump/land/fall and bomb combat pass an authored platform scenario in an explicit profile. |
| MODERN-008 | Enemy freezing into platforms: Hero | Frozen targets become valid geometry and recover under measured rules. |
| MODERN-009 | Enemy-specific bomb vulnerability: Hero | Salt/ordinary attacks discriminate a target without changing unrelated enemies. |
| MODERN-010 | Transforming movement sections: Hero | Marine/jet/copter/slider content switches controller and saves its correct state. |
| MODERN-011 | Stage scores and medal aggregation: Hero | A deterministic run awards the expected stage and planet reward. |
| MODERN-012 | Elemental environmental interactions: Second Attack | One element changes a named obstacle while incompatible elements fail. |
| MODERN-013 | Food-driven companion evolution: Second Attack | Saved food history produces the intended form across reloads and co-op joins. |
| MODERN-014 | Asymmetric companion co-op: Second Attack | A second human takes a companion role without altering the main player's control. |
| MODERN-015 | Permanent equipment capabilities: Second Attack | Armor grants only declared actions and survives the specified transitions. |
| MODERN-016 | Branching exit graph: 2001 N64/Super5 | Two valid exits lead to distinct route/boss states and preserve replay identity. |
| MODERN-017 | Tandem split controls: 2001 N64 | Separate players own move/place inputs with explicit disconnect and conflict rules. |
| MODERN-018 | Puzzle/minigame hub: 2001 N64/Land | A data-authored hub hosts two different rule modules and tracks independent scores. |
| MODERN-019 | Isometric presentation: World | Cell highlights, landing markers and sprite layers agree with authoritative collision. |
| MODERN-020 | Tiered arenas: World/N64/R | Bomb/player movement across a spring, teleporter and trapdoor has explicit layer transitions. |
| MODERN-021 | Crystal-clear objectives: World | Exit eligibility depends on the selected item/enemy objectives, with correct timeout behavior. |
| MODERN-022 | Challenge ranking: World | Time and score records remain tied to ruleset/content versions. |
| MODERN-023 | Retro/enhanced rendering variants: Party Edition | Presentation switches retain identical declared simulation/replay semantics. |
| MODERN-024 | Turn-based bomb scheduler: Wars | Turn fuses and chain reactions resolve in a reproducible tactical encounter. |
| MODERN-025 | Class-specific placement/movement: Wars | At least three authored classes obey distinct legal ranges and actions. |
| MODERN-026 | King/leader objective: Wars | Eliminating the designated leader ends the match regardless of surviving support units. |
| MODERN-027 | Turn manipulation items: Wars | Delay/advance/extra-action effects do not skip or repeat unrelated scheduled events. |
| MODERN-028 | Party recruitment and roster: Wars | A saved unlock changes available party composition without overwriting other campaigns. |
| MODERN-029 | Racing with mount stats: Fantasy Race | Two data-authored mounts differ in documented speed/stamina/handling parameters. |
| MODERN-030 | Stamina dash and bomb dash: Fantasy Race | Boost windows and recovery are reproducible and cannot bypass course collision. |
| MODERN-031 | Ghost trials: Fantasy Race | A ghost replays its input/build/content identity and detects incompatible versions. |
| MODERN-032 | Course mirrors and bonus laps: Fantasy Race | Mirror transforms preserve valid checkpoints and bonus scoring. |
| MODERN-033 | Fake pickups/curses: Fantasy Race | Fake panels and temporary negative effects remain readable and restore state correctly. |
| MODERN-034 | Cross-arena attacks: Dreamcast Online | Placed attacks transfer to the paired board with deterministic timing. |
| MODERN-035 | Target collection and activation: Hyper Bomber | Death/reset and central activation have tested simultaneous-win precedence. |
| MODERN-036 | Territory paint: Online/Generation/Battlefest | Ownership, overwrite, death reset and tie scoring are explicit per profile. |
| MODERN-037 | Respawn score battles: Ring Match/GP | Kills, self-defeat, team hits, lives and timeout use declared scoring. |
| MODERN-038 | Companion/bomb recipes: Generation | One recipe resolves from permitted ingredients; invalid inputs cannot consume/save partial results. |
| MODERN-039 | Coin battles and scavenger NPCs: Generation | Coins drop/steal/return correctly without duplication and bots pursue objectives. |
| MODERN-040 | Telegraphed bomb survival: Dodge Battle | A falling-bomb wave warns participants and resolves declared blast timing. |
| MODERN-041 | Perimeter scoring minigame: Revenge Battle | Cursor-limited targeting distinguishes stun and defeat scores. |
| MODERN-042 | Number-sequence race: Jetters | Ordered progress, regression and damage takeover are deterministic. |
| MODERN-043 | Escort-chain objectives: Jetters/R | Followers slow the player; chain break and delivery scoring preserve ownership. |
| MODERN-044 | Ring-out battles: Jetters | Blast knockback, resistance input and edge recovery have a measured contract. |
| MODERN-045 | Character special abilities: Jetters/R | Two authored abilities declare timing/cost/capability and synchronize across clean clients. |
| MODERN-046 | Item incompatibility families: Jetters | Replacement/stacking/removal follows the selected profile with replay tests. |
| MODERN-047 | Disease system: Jetters/classic lineage | Duration, transfer/cure and simultaneous pickup interactions are explicit. |
| MODERN-048 | Rideable arena transport: Go Go Lorry | Route choice, temporary protection, collection and collision resolve authoritatively. |
| MODERN-049 | Seesaw launchers: Jetters | Mass/position/landing and raised-obstacle interactions are deterministic. |
| MODERN-050 | Weather modifies bombs: Jetters | One weather transition affects declared fuses/motion without shifting unrelated clocks. |
| MODERN-051 | Triggered rocket hazards: Jetters | Launch, warning, return and blast states are replayable and do not double-trigger. |
| MODERN-052 | Temporary size change: Jetters | Size, speed, hitbox and restoration rules remain consistent across renderers. |
| MODERN-053 | Rebounding boundaries: Jetters | Actors and bombs obey profile-specific rebound/stop rules. |
| MODERN-054 | Between-round reward games: Jetters | Earned carryover items apply once to the next round and remain optional. |
| MODERN-055 | Separate kart/driver data: Kart | Vehicle/character composition uses declared stats without conflating cosmetics. |
| MODERN-056 | Mission-based racing: Kart DX | A non-position objective can end a race with correct saved progression. |
| MODERN-057 | Equipment-based co-op adventure: Kart DX | Two players complete a short authored dungeon with gear, health and saved checkpoints. |
| MODERN-058 | Theme-park quest graph: Land series | NPC state, purchases, revisits and piece collection unlock only declared areas. |
| MODERN-059 | Minigame replay and records: Land | Replaying a completed attraction updates the correct score without resetting story state. |
| MODERN-060 | Persistent cosmetic identity: Hardball/Live/R | Compatible cosmetics transfer through server/character sharing without mandatory grind. |
| MODERN-061 | Match replay: Hardball | A saved match restores exact rules/content and rejects missing dependencies. |
| MODERN-062 | AI demonstration mode: Hardball | Watchable bots complete a bounded match with pause/replay controls. |
| MODERN-063 | Optional input automation: Hardball | Accessible assist settings preserve declared scoring/category identity. |
| MODERN-064 | Health-based survival run: Act Zero | Multiple-hit rules, floor progression and restart conditions are independently selectable. |
| MODERN-065 | Fixed-round tournament versus win target: Live | Ties and series winner selection differ correctly between the two structures. |
| MODERN-066 | Capture the Flag/Crown/VIP: Battlefest | One objective fixture per rule includes carrying, dropping, scoring, death and timeout. |
| MODERN-067 | Match economy: Bankroll | Currency and purchases are authoritative and reset at the declared boundary. |
| MODERN-068 | Moving/tilting arena: Battlefest | Arena motion moves declared objects and remains deterministic across clients. |
| MODERN-069 | Mixed local controllers: Blast | Supported controller types can join the same room with explicit platform capacity. |
| MODERN-070 | Beginner tutorial: Blast | A new player can complete movement, placement, escape and item lessons with feedback. |
| MODERN-071 | Emotes and speech bubbles: Blast/SBRO | Cosmetic messages are rate-limited and cannot change collision or hidden information. |
| MODERN-072 | Two-round team competition: R GP | Aggregate score, perfect wins, lives and tie criteria reproduce the chosen profile. |
| MODERN-073 | Checkpoint occupation: R GP | Capture, recapture, sustained scoring and all-point victory have explicit timers. |
| MODERN-074 | Interconnected battle royale: SBRO/R2 | Battle/movement phases, gates, area closure and stranded death replay deterministically. |
| MODERN-075 | Character stat ceilings: SBRO | Pickups respect each selected character's declared caps and item eligibility. |
| MODERN-076 | Private-room browser/lobby: SBRO/R2 | A clean client discovers/joins a room, waits during a running battle and enters the next round. |
| MODERN-077 | Stream/spectator join integration: SBRO | A supported invitation resolves session identity, seat availability and content lock. |
| MODERN-078 | Optional challenges/progression: SBRO | Rewards do not gate compatible installed custom content or overwrite match rules. |
| MODERN-079 | Seasonal rule presets: SBRO | Event rules pin their version and never silently modify existing replay/save profiles. |
| MODERN-080 | Asymmetric castle defense: R2 | Attack keys/chests, defensive survival, weapons and timeout produce correct results. |
| MODERN-081 | Data-only stage construction: R2 inspiration | A creator builds a validated Castle-like arena through the documented public pack API. |
| MODERN-082 | Publish after successful playtest: R2 | Upload is blocked until the required local validator/playtest receipt matches current content. |
| MODERN-083 | Tagged stage discovery/download: R2 | Another clean client searches, downloads exact versions and plays without preinstalled assets. |
| MODERN-084 | Practice save/rewind: Collection | Restore preserves complete declared state; competitive profiles explicitly disable incompatible assistance. |
| MODERN-085 | Boss Rush playlists: Collection | A versioned boss sequence produces accurate times/difficulty and honors assistance restrictions. |
| MODERN-086 | Gallery and sound browser: Collection | Only permitted assets appear with attribution and version identity. |
| MODERN-087 | Regional/localized content variants: Collection | Saves/replays identify the selected release and text variant rather than silently converting. |
| MODERN-088 | Session content sharing: Collection/Neptune | Guests receive only permitted exact-version content through supported runtime channels. |

## Coverage gaps and next research passes

1. Obtain permitted manuals/menu captures for each exact regional release. Catalogue
   every option, controller layout, item, disease, character skill, enemy, boss,
   map, gimmick and unlock by stable identifier; do not use this prose as a complete
   inventory denominator.
2. Resolve the unfinished Land 3 specialist entry, Net de Bomberman's lineage and
   service history, Kart DX expansion packages and the disc/download variants of
   Blast. A search snippet or unfinished page cannot close those gaps.
3. Measure overlapping names separately: circular/elemental bombs, Charaboms,
   paint modes, Crown rules, Revenge and Grand Prix differ between games.
4. Pin update versions for R, R Online, R2 and Collection. Keep launch marketing
   separate from later added content and fixed defects.
5. Check local/network capacities per mode and hardware. R2 Standard's sixteen
   participants, N64's four battle seats, Ultra's seven local controllers and
   Blast's mixed Wii/GameCube controllers are different contracts.
6. Retain original-service closure evidence only where actually inspected. This
   chapter confirms Konami's R Online closure; it does not establish the present
   network availability of Live, Ultra, Battlefest or restored Dreamcast services.
7. Compare original and candidate behavior only after the factory/Saturn critical
   path permits the bounded job. Documentation presence and metadata validation
   do not certify behavior, fidelity or completeness.

## Inspected source register

Primary pages and guides are prioritized where they were available. Wikipedia
and community database entries remain secondary even when their own references
point to primary documents not inspected here.

| ID | Inspected source | Evidence type / useful scope |
| --- | --- | --- |
| M01 | <https://en.wikipedia.org/wiki/Bomberman_64_(1997_video_game)> | Secondary: identities, controller, progression and multiplayer. |
| M02 | <https://randomhoohaas.net/bomb/n64-1/> | Specialist: puzzle/battle differentiation and platform identity. |
| M03 | <https://en.wikipedia.org/wiki/Bomberman_Hero> | Secondary: movement, gears, bombs, scoring and solo mode. |
| M04 | <https://en.wikipedia.org/wiki/Bomberman_64:_The_Second_Attack> | Secondary: elements, shop, armor and Pommy. Redirects to title with exclamation mark. |
| M05 | <https://randomhoohaas.net/bomb/n64-2/> | Specialist: dates and separate co-op/battle capacities; gameplay section unfinished. |
| M06 | <https://en.wikipedia.org/wiki/Bomberman_64_(2001_video_game)> | Secondary: distinct 2D game, branching exits, Tandem and puzzle modes. |
| M07 | <https://en.wikipedia.org/wiki/Bomberman_World> | Secondary: PS1 identity and later PC compilation. |
| M08 | <https://randomhoohaas.net/bomb/psx-wo/> | Specialist: crystal objective, five-player battle, tiered arenas and Challenge. |
| M09 | <https://en.wikipedia.org/wiki/Bomberman_Party_Edition> | Secondary: retro/enhanced solo and upgrades. |
| M10 | <https://randomhoohaas.net/bomb/psx-1/> | Specialist: aliases, five-player battle, roster/mount lineage and PC compilation. |
| M11 | <https://en.wikipedia.org/wiki/Bomberman_Wars> | Secondary: platforms, genre and release identity. |
| M12 | <https://www.randomhoohaas.net/bomb/psx-war/> | Specialist: turn-based identity and two-player battle; behavioral section unfinished. |
| M13 | <https://retroxp.substack.com/p/40-years-of-bomberman-bomberman-wars> | Firsthand retrospective: turn rules, classes, support items and conquest. |
| M14 | <https://en.wikipedia.org/wiki/Bomberman_Fantasy_Race> | Secondary: identities, modes, ghost/race progression leads. |
| M15 | <https://randomhoohaas.net/bomb/psx-race/> | Specialist: animal-racing identity and release. |
| M16 | <https://randomhoohaas.net/bomb/psx-race/game.html> | Detailed guide: controls, mounts, items, races, region-price differences and bomb dash. |
| M17 | <https://en.wikipedia.org/wiki/Bomberman_Online> | Secondary: Dreamcast identity, five rules and reported 2003 closure. |
| M18 | <https://en.wikipedia.org/wiki/Bomberman_Generation> | Secondary: Charaboms, merging and five battle modes. |
| M19 | <https://randomhoohaas.net/bomb/gcn-gen/> | Specialist: release/platform data; game guide unfinished. |
| M20 | <https://en.wikipedia.org/wiki/Bomberman_Jetters_(video_game)> | Secondary: console editions, localization/rendering differences. |
| M21 | <https://randomhoohaas.net/bomb/gcn-jet/> | Specialist: console identity and transcribed US manual story. |
| M22 | <https://gamefaqs.gamespot.com/gamecube/583039-bomberman-jetters/faqs/28039> | Walkthrough: adventure bomb actions, companions, collectibles and revisit puzzles. |
| M23 | <https://gamefaqs.gamespot.com/gamecube/583039-bomberman-jetters/faqs/30180> | Michael Benzing/brappy, version 3.00, 17 May 2004: battle items, diseases, specials, stages and modes. |
| M24 | <https://randomhoohaas.net/bomb/ps2-kart/> | Specialist: platform, four-player lead and conflicting European year. |
| M25 | <https://en.wikipedia.org/wiki/Bomberman_Kart> | Secondary: original/DX identity, capacities, modes and expansion lead. |
| M26 | <https://retroxp.beehiiv.com/p/40-years-of-bomberman-bomberman-kart> | Firsthand retrospective, 31 July 2023: controls, DX racing missions and co-op dungeon. |
| M27 | <https://www.igdb.com/games/net-de-bomberman> | Database: PS2 identity, Japanese title, network capacity and release record; pending validation noted. |
| M28 | <https://gamesdb.launchbox-app.com/games/details/99981-net-de-bomberman> | Database: service-dependent play, chat and map/progression description; lineage unverified. |
| M29 | <https://en.wikipedia.org/wiki/Bomberman_Land> | Secondary: PS1 identity, B-CARD progression and Battle Pack. |
| M30 | <https://en.wikipedia.org/wiki/Bomberman_Land_2> | Secondary: PS2/GameCube release identities. |
| M31 | <https://gamefaqs.gamespot.com/gamecube/917383-bomberman-land-2/faqs/27074> | Walkthrough: modes, hub menus, Bompad and quest/piece conditions. |
| M32 | <https://randomhoohaas.net/bomb/ps2-lan3/> | Specialist: release/reissue identity; explicitly unfinished behavior coverage. |
| M33 | <https://gamesdb.launchbox-app.com/games/details/99855-bomberman-land-3> | Database: piece/minigame/zone progression. |
| M34 | <https://en.wikipedia.org/wiki/Bomberman_Hardball> | Secondary: Battle variants, sports, Life, replay and cosmetic economy. |
| M35 | <https://en.wikipedia.org/wiki/Bomberman:_Act_Zero> | Secondary: survival, FPB health/camera, upgrades and online lead. |
| M36 | <https://en.wikipedia.org/wiki/Bomberman_Live> | Secondary: release, battle-versus-tournament structure. |
| M37 | <https://randomhoohaas.net/bomb/x360-1/> | Specialist: Live/Ultra relationship and different local capacities; Ultra US year conflicts. |
| M38 | <https://en.wikipedia.org/wiki/Bomberman_Ultra> | Secondary: 2009 identity and customization. |
| M39 | <https://en.wikipedia.org/wiki/Bomberman_Live:_Battlefest> | Secondary: sequel identity and network/team play. |
| M40 | <https://www.xbox.com/en-US/games/store/bomberman-battlefest/bq8s2hk3zsd7> | Primary platform store: 8 December 2010, named modes, arenas and compatible platforms. |
| M41 | <https://www.gamingnexus.com/article/bomberman-live-battlefest/item2939.aspx> | Review, 26 January 2011: modes, avatars, capacities and moving/hazardous arenas. |
| M42 | <https://randomhoohaas.net/bomb/x360-2/> | Specialist: identity/local capacity; release day conflicts with official store. |
| M43 | <https://en.wikipedia.org/wiki/Bomberman_Blast> | Secondary: retail/WiiWare differences, controls, tutorial, campaign, items and battle interoperability. |
| M44 | <https://en.wikipedia.org/wiki/Bomberman_Land_(Wii_video_game)> | Secondary: Wii identity, dates and relation to PSP. |
| M45 | <https://www.wiisworld.com/wii-games/Bomberman-Land.html> | Historical promotional description: zones, minigames, customization and battle. Comments excluded from evidence. |
| M46 | <https://en.wikipedia.org/wiki/Super_Bomberman_R> | Secondary: platforms/releases, original story and platform-specific characters. |
| M47 | <https://www.konami.com/games/bomberman/r/us/en/> | Primary: update chronology and added Grand Prix rules. |
| M48 | <https://www.konami.com/games/bomberman/r/us/en/about/> | Primary: Story co-op, battle capacity and named arenas. |
| M49 | <https://www.konami.com/games/bomberman/r/us/en/gp/> | Primary: Basic, Crystal, Checkpoint and Civilians rules. |
| M50 | <https://www.konami.com/games/bomberman/r/us/en/character/> | Primary: character identities, platform exclusivity and named specials. |
| M51 | <https://en.wikipedia.org/wiki/Super_Bomberman_R_Online> | Secondary: release/platform identities and selection/stat structure. |
| M52 | <https://www.konami.com/games/bomberman/online/us/en/> | Primary: Battle 64 phases/gates, Stadia Crowd Play and cosmetics. |
| M53 | <https://www.konami.com/games/bomberman/online/us/en/about/> | Primary: Premium Pack, private modes, map restriction, Standard/GP. |
| M54 | <https://www.konami.com/games/bomberman/online/us/en/news/> | Primary: shutdown, seasons, passes, events and Soma ability. |
| M55 | <https://dds.konami.com/games/manual/sbro/multi/en/pc/> | Primary online manual: controls; platform/language selector resolves here. |
| M56 | <https://dds.konami.com/games/manual/sbro/multi/en/pc/page01.html>, <https://dds.konami.com/games/manual/sbro/multi/en/pc/page02.html>, <https://dds.konami.com/games/manual/sbro/multi/en/pc/page03.html>, <https://dds.konami.com/games/manual/sbro/multi/en/pc/page04.html> | Primary manual: matchmaking/rewards, Battle 64, GP and Standard/revenge/sudden-death rules. |
| M57 | <https://en.wikipedia.org/wiki/Super_Bomberman_R_2> | Secondary: platform identity and general overview. |
| M58 | <https://www.konami.com/games/bomberman/r2/us/en/> | Primary: physical/digital US release and platforms. |
| M59 | <https://www.konami.com/games/bomberman/r2/us/en/battle/> | Primary: mode capacities and objectives. |
| M60 | <https://www.konami.com/games/bomberman/r2/us/en/castle/> | Primary: attack/defense, weapons, editor, playtest, tags and sharing. |
| M61 | <https://www.konami.com/games/bomberman/r2/us/en/pickup_solo/> | Primary: planetary exploration and bomb puzzles. |
| M62 | <https://www.konami.com/games/bomberman/r2/us/en/pickup_build/> | Primary: custom stages and Castle scope. |
| M63 | <https://www.konami.com/games/bomberman/r2/us/en/character/> | Primary: Ellons, Lugions, Lugibons and story roles. |
| M64 | <https://www.konami.com/games/bomberman/r2/us/en/news/> | Primary: 1.2.2–1.3.1 rule selection, lobbies, joining, rematch and fixes. |
| M65 | <https://www.konami.com/games/bomberman/collection/us/en/> | Primary current product page: eight games, wrapper features, current physical date and Switch 2 conditions. |
| M66 | <https://www.konami.com/games/eu/en/topics/18971/> | Primary launch announcement, 6 February 2026: seven launch games, regional versions, gallery, Boss Rush and GameShare. |
| M67 | <https://www.konami.com/games/eu/en/topics/19238/> | Primary update, 20 August 2026: Panic Bomber W and BOMB Radio addition. |
| M68 | <https://randomhoohaas.net/bomb/ps2-2001/> | Specialist: unreleased title evidence and explicitly speculative development relationships. |
| M69 | <https://randomhoohaas.net/bomb/game.html> | Discovery index only: broad release leads. Its modern dates/groupings require correction from primary pages. |
| M70 | <https://www.konami.com/games/ca/en/topics/2264/> | Primary official launch announcement fully fetched during final cross-check: R2 cross-play, platform list, Castle editor and battle modes. |

Fetch limitations: Fandom requests for Net de, Kart/DX, Wars and Land entries were
blocked by the site. They were not treated as read articles. The US *Bomberman
World* PDF manual at <https://www.video-games-museum.com/en/manual/Playstation/16711_us-Bomberman-World.pdf>
returned no extracted text; it remains a primary-source lead. An attempted direct
download did not complete, so no facts above claim successful PDF inspection.
The Land 3 guide index was read, but its full walkthrough was not successfully
retained. These are research gaps, not conclusions that the games lack features.

[M01]: https://en.wikipedia.org/wiki/Bomberman_64_(1997_video_game)
[M02]: https://randomhoohaas.net/bomb/n64-1/
[M03]: https://en.wikipedia.org/wiki/Bomberman_Hero
[M04]: https://en.wikipedia.org/wiki/Bomberman_64:_The_Second_Attack
[M05]: https://randomhoohaas.net/bomb/n64-2/
[M06]: https://en.wikipedia.org/wiki/Bomberman_64_(2001_video_game)
[M07]: https://en.wikipedia.org/wiki/Bomberman_World
[M08]: https://randomhoohaas.net/bomb/psx-wo/
[M09]: https://en.wikipedia.org/wiki/Bomberman_Party_Edition
[M10]: https://randomhoohaas.net/bomb/psx-1/
[M11]: https://en.wikipedia.org/wiki/Bomberman_Wars
[M12]: https://www.randomhoohaas.net/bomb/psx-war/
[M13]: https://retroxp.substack.com/p/40-years-of-bomberman-bomberman-wars
[M14]: https://en.wikipedia.org/wiki/Bomberman_Fantasy_Race
[M15]: https://randomhoohaas.net/bomb/psx-race/
[M16]: https://randomhoohaas.net/bomb/psx-race/game.html
[M17]: https://en.wikipedia.org/wiki/Bomberman_Online
[M18]: https://en.wikipedia.org/wiki/Bomberman_Generation
[M19]: https://randomhoohaas.net/bomb/gcn-gen/
[M20]: https://en.wikipedia.org/wiki/Bomberman_Jetters_(video_game)
[M21]: https://randomhoohaas.net/bomb/gcn-jet/
[M22]: https://gamefaqs.gamespot.com/gamecube/583039-bomberman-jetters/faqs/28039
[M23]: https://gamefaqs.gamespot.com/gamecube/583039-bomberman-jetters/faqs/30180
[M24]: https://randomhoohaas.net/bomb/ps2-kart/
[M25]: https://en.wikipedia.org/wiki/Bomberman_Kart
[M26]: https://retroxp.beehiiv.com/p/40-years-of-bomberman-bomberman-kart
[M27]: https://www.igdb.com/games/net-de-bomberman
[M28]: https://gamesdb.launchbox-app.com/games/details/99981-net-de-bomberman
[M29]: https://en.wikipedia.org/wiki/Bomberman_Land
[M30]: https://en.wikipedia.org/wiki/Bomberman_Land_2
[M31]: https://gamefaqs.gamespot.com/gamecube/917383-bomberman-land-2/faqs/27074
[M32]: https://randomhoohaas.net/bomb/ps2-lan3/
[M33]: https://gamesdb.launchbox-app.com/games/details/99855-bomberman-land-3
[M34]: https://en.wikipedia.org/wiki/Bomberman_Hardball
[M35]: https://en.wikipedia.org/wiki/Bomberman:_Act_Zero
[M36]: https://en.wikipedia.org/wiki/Bomberman_Live
[M37]: https://randomhoohaas.net/bomb/x360-1/
[M38]: https://en.wikipedia.org/wiki/Bomberman_Ultra
[M39]: https://en.wikipedia.org/wiki/Bomberman_Live:_Battlefest
[M40]: https://www.xbox.com/en-US/games/store/bomberman-battlefest/bq8s2hk3zsd7
[M41]: https://www.gamingnexus.com/article/bomberman-live-battlefest/item2939.aspx
[M42]: https://randomhoohaas.net/bomb/x360-2/
[M43]: https://en.wikipedia.org/wiki/Bomberman_Blast
[M44]: https://en.wikipedia.org/wiki/Bomberman_Land_(Wii_video_game)
[M45]: https://www.wiisworld.com/wii-games/Bomberman-Land.html
[M46]: https://en.wikipedia.org/wiki/Super_Bomberman_R
[M47]: https://www.konami.com/games/bomberman/r/us/en/
[M48]: https://www.konami.com/games/bomberman/r/us/en/about/
[M49]: https://www.konami.com/games/bomberman/r/us/en/gp/
[M50]: https://www.konami.com/games/bomberman/r/us/en/character/
[M51]: https://en.wikipedia.org/wiki/Super_Bomberman_R_Online
[M52]: https://www.konami.com/games/bomberman/online/us/en/
[M53]: https://www.konami.com/games/bomberman/online/us/en/about/
[M54]: https://www.konami.com/games/bomberman/online/us/en/news/
[M55]: https://dds.konami.com/games/manual/sbro/multi/en/pc/
[M56]: https://dds.konami.com/games/manual/sbro/multi/en/pc/page01.html
[M57]: https://en.wikipedia.org/wiki/Super_Bomberman_R_2
[M58]: https://www.konami.com/games/bomberman/r2/us/en/
[M59]: https://www.konami.com/games/bomberman/r2/us/en/battle/
[M60]: https://www.konami.com/games/bomberman/r2/us/en/castle/
[M61]: https://www.konami.com/games/bomberman/r2/us/en/pickup_solo/
[M62]: https://www.konami.com/games/bomberman/r2/us/en/pickup_build/
[M63]: https://www.konami.com/games/bomberman/r2/us/en/character/
[M64]: https://www.konami.com/games/bomberman/r2/us/en/news/
[M65]: https://www.konami.com/games/bomberman/collection/us/en/
[M66]: https://www.konami.com/games/eu/en/topics/18971/
[M67]: https://www.konami.com/games/eu/en/topics/19238/
[M68]: https://randomhoohaas.net/bomb/ps2-2001/
[M69]: https://randomhoohaas.net/bomb/game.html
[M70]: https://www.konami.com/games/ca/en/topics/2264/
