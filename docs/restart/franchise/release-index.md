# Bomberman release discovery index

Checked 3 November 2026. The machine-readable inventory is [games.tsv](games.tsv).
This register preserves **222 discovery records**: 187 indexed released entries,
three developer-documented releases (Power and two casino games), seven cancelled
projects, and twenty-five leads whose release/version status still needs confirmation. These are records of
families, editions, significant ports, updates and adjacent games; **222 is not
a claim that 222 distinct official Bomberman games exist**.

The title catalogue is broad enough to keep obscure games visible even when a
manual or playable copy cannot be located. A source identifying a title is not
evidence for an exhaustive feature list. Read each row's `evidence_limit` and the
linked detail document before treating it as an implementation reference.

## Reading and maintaining the register

`id` is a stable research-record identifier, not a task ID. `year` is the earliest
release year supported by the inspected index, or an explicit uncertainty; it is
not a complete regional release calendar. `platforms` may group related versions
that still require separate build identities. `kind` keeps game, port,
compilation, service, update, trial, cancelled project, fan game and cameo apart.
`status` describes evidence of release, never Neptune implementation progress.
`aliases` are searchable names and identity warnings. `detail_document` points to
the appropriate survey, which may contain fuller coverage only for the family.
`source_url` and `evidence_limit` distinguish inspected evidence from a search
lead. Empty aliases mean no alias recorded, not proof that none exists.

Append newly found identities without renumbering existing records. Merge an alias
only after establishing the shared family/build relationship, and retain the old
ID as a cross-reference. Split a family into regional/build rows when evidence
shows different mechanics, content, network services or controls. Reissues on
Virtual Console, Nintendo Switch Online, PlayStation Archives, retro hardware and
other storefronts still need a per-SKU audit; their existence must not inflate
the number of original game designs. Demo discs, competitive special editions,
promotional ROMs, LCD colour shells, arcade patches and carrier builds are not
fully enumerated by this pass.

## Name collisions that affect feature attribution

| Name | Distinct identities to preserve |
| --- | --- |
| Bomberman | 1983 computers; 1985 Famicom/NES; 1990 PC Engine; 1991 Irem arcade; 1998 PlayStation; 2004 N-Gage; 2005 DS; 2006 PSP; 2007 iPod; 2008 Wii retail; many mobile versions |
| Bomberman II / 2 | 1991 NES game; 2008 DS Custom Battler; neither is the unofficial MSX Bomberman 2 clone |
| Bomberman GB | Japanese 1994 game adapted into Wario Blast; the western title Bomberman GB instead identifies Japanese GB2 |
| Atomic Punk | Game Boy Bomber Boy localization and the separate Irem arcade game; neither is Interplay's Atomic Bomberman |
| Dyna Blaster / Dynablaster | Used by NES, Game Boy, Irem arcade and computer adaptations; platform and build must accompany the name |
| Bomberman World | 1992 Irem arcade game and separate 1998 PlayStation game |
| Bomberman 64 | 1997 Baku Bomberman 3D adventure and unrelated 2001 Japanese 2D game |
| Bomberman Online | Dreamcast 2001; regional Windows services from 2003; Online Japan 2008; Super Bomberman R Online 2020 |
| Bomberman Jetters | Console action game; GBA Densetsu no Bomberman; GBA Game Collection; mobile platformer Vol.1 |
| Bomberman Land | PS1, Wii, PSP and mobile Land Battles are separate identities; Land Touch DS is a separate sub-series |
| Super Bomberman | SNES original and separately developed mobile game; Living Mobile and Hudson Entertainment releases may be regional publishing identities of that mobile family |
| Taisen Bomberman | The feature-phone Taisen ☆ series, 2015/2016 smartphone Taisen! / VS!, and translated generic battle labels are not interchangeable |
| Bomberman Collection | 1996 Game Boy, Korean Selection, Windows Vol.1/2, GBA Hudson Best Collection, and 2026 Super Bomberman Collection |
| Panic Bomber | PC Engine, arcade/Neo Geo, PC-9821, Virtual Boy, Super Famicom W, PSP, mobile Taisen and broadcast trial have different content/features |
| Bombergirl | Arcade MOBA, Konaste PC edition, Rainbow revision and pachislot have separate rules and version histories |

Wario Blast has a separate title-visible adaptation record and a cross-reference
to Japanese Bomberman GB; it must not be counted twice when calculating unique
game families. The same principle applies to compilations and their included
games, the Panic Bomber W collection update and its 1995 original, and publisher
variants of the same mobile engine.

## Evidence and reconciliation notes

The inspected [Wikipedia series list](https://en.wikipedia.org/wiki/List_of_Bomberman_video_games)
is a useful conventional-console index but omits many mobile titles. The
[GameFAQs franchise register](https://gamefaqs.gamespot.com/games/franchise/135-bomberman)
contributes dozens of phone, toy-line, educational and medal-machine leads;
database indexing alone does not establish all mechanics. The
[specialist master list](https://randomhoohaas.net/bomb/game.html) says its
comprehensive scope reaches 2008, and includes cameo games. Its later entries
have visible date problems: it places R Online under 2017, while other sources
establish 2020, and lists Bombergirl's announcement year rather than its 2018
launch. The register uses the reconciled dates and leaves other conflicts open.

The [specialist mobile list](https://randomhoohaas.net/bomb/mob/) explicitly says
phone-game preservation and release dates are incomplete. Its text extraction
omits many linked title labels; linked game pages and the database provide the
additional identities here. Some rows depend only on indexed names, not surviving
manuals or binaries. In particular, early mobile Bomberman, mobile Special,
2004/2007/2008 generic editions, Deluxe/Reloaded/Reprint, and Taisen Wide need
build and alias reconciliation. Tsubame-fuu 2 and some Gachapin/Taisen games are
retained as franchise-adjacent leads, not established mainline releases.

The register also includes the inspected official [18 December 2025 casino premiere](https://www.konamigaming.com/home/2025/12/18/graton-resort---casino-hosts-world-premiere-of-new-bomberman-slot-games)
for Bomberman Boom and Bomberman Blast. The casino Blast shares a name with the
Wii game but is a separate product; current iGaming distribution is another
versioning question, not proof of a new mainline action game.

The current [official Super Bomberman Collection page](https://www.konami.com/games/bomberman/collection/us/en/)
lists eight titles. It launched with seven on 5 February 2026;
[Panic Bomber W was added on 20 August](https://www.konami.com/games/eu/en/topics/19238/).
The current US physical listing says 25 September, superseding the launch press
release's earlier August plan. Do not copy an older seven-title count into a
current coverage claim. Windows Collection Vol.1 is dated 19 December 2002 in Japan by the
[inspected specialist page](https://randomhoohaas.net/bomb/pc-col1/), while
Wikipedia lists 2003; international SKU chronology remains unresolved.
[Volume2](https://randomhoohaas.net/bomb/pc-col2/) is dated 15 April 2004 in Japan
and carries the Korean alias Bomberman Game Room.

[Bombergirl's PC launch report](https://www.siliconera.com/bombergirl-pc-version-launches-in-japan/)
describes a different content snapshot from contemporary arcade;
[Rainbow's 2022 launch report](https://www.arcadebelgium.be/ab.php?l=en&r=new&p=news&d=2022-07-13)
is an update identity, not a promise of the present roster. The
[Bandai LCD firsthand review](https://kimimithegameeatingshemonster.com/2025/07/29/bomberman-bandai-mame-game-lcd-small-but-mighty/)
infers 1997 from packaging copyright. The
[Satellaview preservation report](https://superfamicom.org/blog/2024/07/my-first-blogpost-attempt-with-some-demo-trial-versions/)
establishes a restricted Panic Bomber W trial and a May 1995 broadcast schedule;
it does not prove that every Super Bomberman broadcast is a distinct game.

## Remaining discovery work

- Reconcile every feature-phone carrier, language and publisher build, including
  release, shutdown, subscription and content-update dates.
- Establish the exact relationship between regional Windows Online services and
  the 2008 Japan relaunch. Preserve server and client versions separately.
- Pin every Saturn region/revision and network edition, Super Bomberman 5 special
  cartridge, Hi-Ten event revision and Mega Bomberman demonstration claim before
  attributing a special rule to the commercial game.
- Inspect the Satellaview Super Bomberman/2 broadcasts, trial versions,
  competition demos, compilations and modern reissues by hash. Broadcast year
  remains unknown where only a database/search lead survived.
- Verify the branded pachislot/medal/casino machine range, including simulator
  adaptations; the named pachislot leads below are not a complete machine census.
- Research all official crossovers/cameos separately if their complete mechanics
  are desired. This register samples direct Bomberman-linked games rather than
  claiming every later Smash Bros. item, music cameo, advertisement or licensed
  appearance is a new Bomberman game.
- A search for a Sharp Zaurus game did not establish a release; do not invent one
  from Zaurus Star, the unrelated world name in Bomberman games. Likewise, the
  inspected LCD source identifies Bandai, not a verified Tomy release.
- Power Bomberman is explicitly included because the owner requested it. Other
  clones and fan projects are not counted as official releases, and the open-ended
  fan scene is not claimed complete by adding a few familiar names.

## Discovery records

The full platforms, aliases, source URL and evidence limitations are in the TSV.
The compact table below is a navigation view of the same record set.

| ID | Title | Year / timing | Kind; status | Detail survey |
| --- | --- | --- | --- | --- |
| REL-001 | Bomber Man | 1983 | game; released-indexed | [classic.md](classic.md) |
| REL-002 | 3-D Bomberman | 1984 | game; released-indexed | [classic.md](classic.md) |
| REL-003 | Bomberman (Famicom/NES) | 1985 | game; released-indexed | [classic.md](classic.md) |
| REL-004 | Bomberman Special (MSX) | 1986 | game; released-indexed | [classic.md](classic.md) |
| REL-005 | Bomberman (PC Engine/TurboGrafx-16) | 1990 | game; released-indexed | [classic.md](classic.md) |
| REL-006 | Bomberman II (Famicom/NES) | 1991 | game; released-indexed | [classic.md](classic.md) |
| REL-007 | Bomberman '93 | 1992 | game; released-indexed | [classic.md](classic.md) |
| REL-008 | Hi-Ten Bomberman | 1993 | game; released-indexed | [classic.md](classic.md) |
| REL-009 | Bomberman '94 | 1993 | game; released-indexed | [classic.md](classic.md) |
| REL-010 | Mega Bomberman | 1994 | game; released-indexed | [classic.md](classic.md) |
| REL-011 | Hi-Ten Chara Bomb | 1994 | game; released-indexed | [classic.md](classic.md) |
| REL-012 | Super Bomberman | 1993 | game; released-indexed | [classic.md](classic.md) |
| REL-013 | Super Bomberman 2 | 1994 | game; released-indexed | [classic.md](classic.md) |
| REL-014 | Super Bomberman 3 | 1995 | game; released-indexed | [classic.md](classic.md) |
| REL-015 | Super Bomberman 4 | 1996 | game; released-indexed | [classic.md](classic.md) |
| REL-016 | Super Bomberman 5 | 1997 | game; released-indexed | [classic.md](classic.md) |
| REL-017 | Saturn Bomberman | 1996 | game; released-indexed | [classic.md](classic.md) |
| REL-018 | Saturn Bomberman Fight!! | 1997 | game; released-indexed | [classic.md](classic.md) |
| REL-019 | Atomic Bomberman | 1997 | game; released-indexed | [classic.md](classic.md) |
| REL-020 | Bomber Man (Irem arcade) | 1991 | game; released-indexed | [classic.md](classic.md) |
| REL-021 | Bomberman World (Irem arcade) | 1992 | game; released-indexed | [classic.md](classic.md) |
| REL-022 | Neo Bomberman | 1997 | game; released-indexed | [classic.md](classic.md) |
| REL-023 | Dyna Blaster (computer adaptations) | 1991-1993 adaptation era | port; released-indexed | [classic.md](classic.md) |
| REL-024 | Bomberman: Users Battle | 1990 | special-edition; released-indexed | [classic.md](classic.md) |
| REL-025 | Bomber Boy | 1990 | game; released-indexed | [handheld.md](handheld.md) |
| REL-026 | Bomberman GB (Japan) | 1994 | game; released-indexed | [handheld.md](handheld.md) |
| REL-027 | Bomberman GB 2 | 1995 | game; released-indexed | [handheld.md](handheld.md) |
| REL-028 | Bomberman GB 3 | 1996 | game; released-indexed | [handheld.md](handheld.md) |
| REL-029 | Pocket Bomberman | 1997 | game; released-indexed | [handheld.md](handheld.md) |
| REL-030 | Bomberman Quest | 1998 | game; released-indexed | [handheld.md](handheld.md) |
| REL-031 | Bomberman Max: Red Challenger | 1999 | game; released-indexed | [handheld.md](handheld.md) |
| REL-032 | Bomberman Max: Blue Champion | 1999 | game; released-indexed | [handheld.md](handheld.md) |
| REL-033 | Bomberman Tournament | 2001 | game; released-indexed | [handheld.md](handheld.md) |
| REL-034 | Bomberman Max 2: Red Advance | 2002 | game; released-indexed | [handheld.md](handheld.md) |
| REL-035 | Bomberman Max 2: Blue Advance | 2002 | game; released-indexed | [handheld.md](handheld.md) |
| REL-036 | Bomberman Jetters: Densetsu no Bomberman | 2002 | game; released-indexed | [handheld.md](handheld.md) |
| REL-037 | Bomberman Jetters: Game Collection | 2003 | game; released-indexed | [handheld.md](handheld.md) |
| REL-038 | Bomberman (N-Gage) | 2004 | game; released-indexed | [handheld.md](handheld.md) |
| REL-039 | Classic NES Series: Bomberman | 2004 | game; released-indexed | [handheld.md](handheld.md) |
| REL-040 | Bomberman (Nintendo DS) | 2005 | game; released-indexed | [handheld.md](handheld.md) |
| REL-041 | Bomberman (PSP) | 2006 | game; released-indexed | [handheld.md](handheld.md) |
| REL-042 | Bomberman: Bakufuu Sentai Bombermen | 2006 | game; released-indexed | [handheld.md](handheld.md) |
| REL-043 | Bomberman Story DS | 2007 | game; released-indexed | [handheld.md](handheld.md) |
| REL-044 | Bomberman 2 (Nintendo DS) | 2008 | game; released-indexed | [handheld.md](handheld.md) |
| REL-045 | Bomberman Blitz | 2009 | game; released-indexed | [handheld.md](handheld.md) |
| REL-046 | Bomberman Land Touch! | 2006 | game; released-indexed | [handheld.md](handheld.md) |
| REL-047 | Bomberman Land Touch! 2 | 2007 | game; released-indexed | [handheld.md](handheld.md) |
| REL-048 | Bomberman Land (PSP) | 2007 | game; released-indexed | [handheld.md](handheld.md) |
| REL-049 | Bomberman 64 (1997) | 1997 | game; released-indexed | [console-modern.md](console-modern.md) |
| REL-050 | Bomberman Hero | 1998 | game; released-indexed | [console-modern.md](console-modern.md) |
| REL-051 | Bomberman 64: The Second Attack! | 1999 | game; released-indexed | [console-modern.md](console-modern.md) |
| REL-052 | Bomberman 64 (2001) | 2001 | game; released-indexed | [console-modern.md](console-modern.md) |
| REL-053 | Bomberman World (PlayStation) | 1998 | game; released-indexed | [console-modern.md](console-modern.md) |
| REL-054 | Bomberman Party Edition | 1998 | game; released-indexed | [console-modern.md](console-modern.md) |
| REL-055 | Bomberman Wars | 1998 | game; released-indexed | [console-modern.md](console-modern.md) |
| REL-056 | Bomberman Fantasy Race | 1998 | game; released-indexed | [console-modern.md](console-modern.md) |
| REL-057 | Bomberman Land (PlayStation) | 2000 | game; released-indexed | [console-modern.md](console-modern.md) |
| REL-058 | Bomberman Online (Dreamcast) | 2001 | game; released-indexed | [console-modern.md](console-modern.md) |
| REL-059 | Bomberman Kart | 2001 | game; released-indexed | [console-modern.md](console-modern.md) |
| REL-060 | Bomberman Generation | 2002 | game; released-indexed | [console-modern.md](console-modern.md) |
| REL-061 | Bomberman Jetters (console) | 2002 | game; released-indexed | [console-modern.md](console-modern.md) |
| REL-062 | Bomberman Land 2 | 2003 | game; released-indexed | [console-modern.md](console-modern.md) |
| REL-063 | Net de Bomberman | 2004 | game; released-indexed | [console-modern.md](console-modern.md) |
| REL-064 | Bomberman Kart DX | 2004 | game; released-indexed | [console-modern.md](console-modern.md) |
| REL-065 | Bomberman Hardball | 2004 | game; released-indexed | [console-modern.md](console-modern.md) |
| REL-066 | Bomberman Land 3 | 2005 | game; released-indexed | [console-modern.md](console-modern.md) |
| REL-067 | Bomberman: Act Zero | 2006 | game; released-indexed | [console-modern.md](console-modern.md) |
| REL-068 | Bomberman Land (Wii) | 2007 | game; released-indexed | [console-modern.md](console-modern.md) |
| REL-069 | Bomberman Live | 2007 | game; released-indexed | [console-modern.md](console-modern.md) |
| REL-070 | Bomberman Blast (WiiWare) | 2008 | game; released-indexed | [console-modern.md](console-modern.md) |
| REL-071 | Bomberman (Wii retail) | 2008 | game; released-indexed | [console-modern.md](console-modern.md) |
| REL-072 | Bomberman Ultra | 2009 | game; released-indexed | [console-modern.md](console-modern.md) |
| REL-073 | Bomberman Live: Battlefest | 2010 | game; released-indexed | [console-modern.md](console-modern.md) |
| REL-074 | Super Bomberman R | 2017 | game; released-indexed | [console-modern.md](console-modern.md) |
| REL-075 | Super Bomberman R Online | 2020 | game; released-indexed | [console-modern.md](console-modern.md) |
| REL-076 | Super Bomberman R 2 | 2023 | game; released-indexed | [console-modern.md](console-modern.md) |
| REL-077 | Bomberman Collection (Game Boy) | 1996 | compilation; released-indexed | [handheld.md](handheld.md) |
| REL-078 | Bomberman Selection | 2003 | compilation; released-indexed | [handheld.md](handheld.md) |
| REL-079 | Bomberman Collection Vol. 1 (Windows) | 2002 Japan; 2003 also indexed | compilation; released-indexed | [classic.md](classic.md) |
| REL-080 | Bomberman Collection Vol. 2 (Windows) | 2004 | compilation; released-indexed | [classic.md](classic.md) |
| REL-081 | Hudson Best Collection Vol. 1: Bomberman Collection | 2005 | compilation; released-indexed | [handheld.md](handheld.md) |
| REL-082 | Super Bomberman Collection | 2026 | compilation; released-indexed | [console-modern.md](console-modern.md) |
| REL-083 | Super Bomberman Collection: Panic Bomber W update | 2026-08-20 | content-update; released-indexed | [console-modern.md](console-modern.md) |
| REL-084 | Bomber King | 1987 | spin-off; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-085 | Bomber King: Scenario 2 | 1991 | spin-off; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-086 | Bomberman: Panic Bomber (PC Engine) | 1994 | spin-off; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-087 | Bomberman: Panic Bomber (Neo Geo) | 1994/1995 disputed | spin-off; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-088 | Bomberman: Panic Bomber (PC-9821) | 1995 | spin-off; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-089 | Super Bomberman: Panic Bomber W | 1995 | spin-off; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-090 | Tobidase! Panibon | 1995 | spin-off; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-091 | Bomberman: Panic Bomber (PSP) | 2005 | spin-off; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-092 | Bomberman B-Daman | 1996 | spin-off; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-093 | Super B-Daman | 1997 | spin-off; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-094 | Bakukyuu Renpatsu!! Super B-Daman | 1997 | spin-off; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-095 | B.B-Daman Bakugaiden: Victory e no Michi | 1999 | spin-off; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-096 | B-Daman Bakugaiden V: Final Mega Tune | 2000 | spin-off; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-097 | Bomberman Misobon Roulette | 1997 | spin-off; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-098 | Bomberman Street | 2002 | spin-off; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-099 | Bomberman The Medal | 2018 | spin-off; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-100 | Bombergirl | 2018 | spin-off; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-101 | Bombergirl Konaste | 2021 | service-edition; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-102 | Bombergirl Rainbow | 2022 | major-revision; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-103 | Bomberman (Bandai Mame Game LCD) | circa 1997 | dedicated-handheld; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-104 | Bomberman (Palm OS) | 2001 | port; released-indexed | [handheld.md](handheld.md) |
| REL-105 | Bomberman (early mobile) | unknown | mobile-game; discovery-only | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-106 | Bomberman Special (mobile) | unknown | mobile-game; discovery-only | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-107 | Bomberman Kart (mobile) | 2002 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-108 | Bomberman Soccer | 2002 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-109 | Bomberman Baseball | 2002 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-110 | Bomberman Jetters Vol. 1 | 2003 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-111 | Super Bomberman (Japanese mobile) | 2003 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-112 | Super Bomberman (Living Mobile) | 2004 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-113 | Super Bomberman (Hudson Entertainment) | 2005 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-114 | Bomberman (mobile 2004) | 2004 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-115 | Bomberman GB 2 (Korean mobile port) | 2004 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-116 | Bomberman Puzzle | 2003 i-Mode; 2004 EZweb | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-117 | Bomberman 3D (2004) | 2004 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-118 | Tsubame-fuu 2 | 2004 | mobile-game; discovery-only | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-119 | Taisen ☆ Bomberman | 2004 | mobile-service; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-120 | Taisen ☆ Bomberman 8 | 2005 | mobile-service; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-121 | Bomberman Kart 3D | 2005 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-122 | Bomberman Kart Special | 2005 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-123 | Bomberman RPG | 2005 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-124 | Bomberman Pinball | 2005 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-125 | Taisen ☆ Daifugo | 2005 | mobile-service; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-126 | Bomberman Deluxe | 2006 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-127 | Bomberman Act: Zero MOBILE Type | 2006 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-128 | Taisen ☆ IQ | 2006 | mobile-service; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-129 | Taisen ☆ Mahjong | 2006 | mobile-service; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-130 | Taisen ☆ Panic Bomber | 2006 | mobile-service; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-131 | Taisen ☆ Bomberman 24 | 2007 | mobile-service; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-132 | Taisen ☆ Bomberman + | 2007 | mobile-service; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-133 | Taisen ☆ Bomberman 24+ | 2007 | mobile-service; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-134 | Taisen ☆ Golf | 2007 | mobile-service; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-135 | Gachapin Bomberman | 2007 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-136 | Bomberman (mobile 2007) | 2007 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-137 | Bomberman Reloaded | 2007 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-138 | Bomberman Reprint | 2007 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-139 | Bomberman Land Battles | 2007 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-140 | Gachapin & Mook Reversi | 2007 | mobile-game; discovery-only | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-141 | Bomberman (iPod) | 2007 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-142 | Bomberman Planet Vol. 1 | 2008 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-143 | Bomberman '08 | 2008 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-144 | Bomberman (mobile 2008) | 2008 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-145 | Bomberman Touch: The Legend of Mystic Bomb | 2008 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-146 | Gachapin & Mukku's Big Sports Day | 2008 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-147 | Yatterman x Bomberman | 2008 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-148 | R20 Moe Bomberman | 2008 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-149 | Bomberman Puzzle Special | 2008 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-150 | Bomberman Time Attack | 2008 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-151 | Taisen ☆ Bomberman Wide | 2008 | mobile-service; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-152 | Taisen ☆ Reversi Cross | 2008 | mobile-service; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-153 | 3D Bomberman Atomic | 2008 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-154 | Bomberman 3D Island | 2008 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-155 | Taisen ☆ Daifugo + | 2008 | mobile-service; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-156 | Taisen ☆ IQ + | unknown | mobile-service; discovery-only | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-157 | Taisen ☆ Panic Bomber + | unknown | mobile-service; discovery-only | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-158 | Super Gachapin Bomberman | 2009 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-159 | Rose O'Neill Kewpie Bomberman | 2009 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-160 | Taisen ☆ Bomberman GEEK | 2009 | mobile-service; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-161 | Taisen ☆ Bomberman Cross | 2009 | mobile-service; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-162 | Taisen ☆ Daifugo Cross | 2009 | mobile-service; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-163 | Bomberman Touch 2: Volcano Party | 2009 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-164 | Pac-Man x Bomberman | 2010 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-165 | Bomberman Next: Here in Kanto Edition | 2010 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-166 | Bomberman Next: Here in Kinki Edition | 2010 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-167 | Bomberman: Disney Stitch Edition | 2010 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-168 | Bomberman Dojo | 2009 Android; iOS by 2011 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-169 | Bomberman Chains | 2011 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-170 | Bomberman for GREE | 2011 | mobile-service; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-171 | 100 Man Battle Bomberman | 2012 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-172 | Bomberman (smartphones 2014) | 2014 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-173 | VS! Bomberman | 2016 (2015 also cited) | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-174 | Amazing Bomberman | 2022 | mobile-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-175 | Bomberman Online (Windows regional services) | 2003 | service-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-176 | Bomberman Online Japan | 2008 | service-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-177 | Super Bomberman (Satellaview broadcast) | unknown | broadcast-port; discovery-only | [classic.md](classic.md) |
| REL-178 | Super Bomberman 2 (Satellaview broadcast) | unknown | broadcast-port; discovery-only | [classic.md](classic.md) |
| REL-179 | Super Bomberman: Panic Bomber W (Satellaview trial) | 1995 | demo; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-180 | Dyna Blaster (cancelled computer ports) | 1991 planned | cancelled-game; cancelled | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-181 | Bomberman Legends | 1990s planned | cancelled-game; cancelled | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-182 | Virtual Bomberman | 1995/1996 planned | cancelled-game; cancelled | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-183 | Bomberman 2001 (PS2 project) | 2000 shown | cancelled-game; cancelled | [console-modern.md](console-modern.md) |
| REL-184 | Bomberman (Nintendo 3DS working title) | 2011 planned | cancelled-game; cancelled | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-185 | Bomberman Live: Battlefest (Wii planned edition) | 2010 planned | planned-port; discovery-only | [console-modern.md](console-modern.md) |
| REL-186 | Power Bomberman | 2013 public thread; 0.7.8c: 2026 | fan-game; released-documented | [power-bomberman.md](power-bomberman.md) |
| REL-187 | Lode Runner (Hudson Famicom) | 1984 | cameo-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-188 | Battle Lode Runner | 1993 | cameo-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-189 | Star Parodier | 1992 | crossover-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-190 | DreamMix TV World Fighters | 2003 | crossover-game; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-191 | Same Game (Hudson Super Famicom) | 1996 | cameo-game; discovery-only | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-192 | Bomberman Victory | 2006 | pachislot; discovery-only | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-193 | Bombergirl Pachislot | 2022 | pachislot; discovery-only | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-194 | Wario Blast: Featuring Bomberman! | 1994 | regional-adaptation; released-indexed | [handheld.md](handheld.md) |
| REL-195 | Bomberman Max: Ain Version | date unresolved (1999 game family) | special-edition; released-indexed | [handheld.md](handheld.md) |
| REL-196 | Super Bomberman 5: Gold Cartridge | 1997 game family | special-edition; released-indexed | [classic.md](classic.md) |
| REL-197 | Bomberman Boom (casino slot) | 2025-12-18 premiere | casino-slot; released-documented | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-198 | Bomberman Blast (casino slot) | 2025-12-18 premiere | casino-slot; released-documented | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-199 | Bomberman (Toshiba Rupo) | circa 1987 | port; released-indexed | [classic.md](classic.md) |
| REL-200 | Bomberman (Famicom Disk System) | date unresolved | port; released-indexed | [classic.md](classic.md) |
| REL-201 | Bomberman '94 Special Version | 1993 | promotional-game; released-indexed | [classic.md](classic.md) |
| REL-202 | Tengai Makyou: Deden no Den | 1994 | promotional-game; released-indexed | [classic.md](classic.md) |
| REL-203 | Saturn Bomberman XBAND | 1996-09-27 | service-edition; released-indexed | [classic.md](classic.md) |
| REL-204 | Flash Sega Saturn: Ochikazuki-hen Bomberman demo | 1996-03 | demo; released-indexed | [classic.md](classic.md) |
| REL-205 | Mega Bomberman (Factor 5 eight-player prototype) | before 1994 | cancelled-game; cancelled | [classic.md](classic.md) |
| REL-206 | Super Bomberman 2: Gold Version | 1994 event lead | special-edition; discovery-only | [classic.md](classic.md) |
| REL-207 | Bomberman Max: Complete Data Version | 1999 game family; edition date unresolved | promotional-data-edition; discovery-only | [handheld.md](handheld.md) |
| REL-208 | Panic Bomber (cancelled Neo Geo CD port) | 1995 planned | cancelled-port; cancelled | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-209 | Panic Bomber (FM Towns port) | date unresolved | port; discovery-only | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-210 | Panic Bomber (X68000 port) | date unresolved | port; discovery-only | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-211 | Panic Bomber (standalone mobile) | date unresolved | mobile-game; discovery-only | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-212 | Bomberman Panic! | date unresolved | mobile-game; discovery-only | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-213 | Bomberman (Nokia feature-phone variant) | date unresolved | device-edition; discovery-only | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-214 | Bomberman (Motorola feature-phone variant) | date unresolved | device-edition; discovery-only | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-215 | Bomberman Reborn 1.1 | date unresolved | mobile-game; discovery-only | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-216 | BomberPino | 2023 campaign lead | promotional-game; discovery-only | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-217 | Bomberman Pinball 3D | date unresolved | mobile-game; discovery-only | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-218 | Bomberman Puzzle Mini | date unresolved; original2003 family | demo; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-219 | Bomberman Kart Special Lite | date unresolved; 2005 game family | budget-edition; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-220 | Bomberman Planet Vol. 2 | advertised in 2008 family | mobile-game; discovery-only | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-221 | Bomberman Planet Vol. 3 | advertised in 2008 family | mobile-game; discovery-only | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
| REL-222 | Bomberman Chains (free-to-play relaunch) | 2014-09-09 international relaunch | major-revision; released-indexed | [mobile-arcade-spinoffs.md](mobile-arcade-spinoffs.md) |
