# Research method, conflicts and remaining coverage

Research date: **3 November 2026**. This survey used internet sources extensively:
official Konami product/rules/update pages, developer announcements/changelogs,
manual-derived material, contemporary reviews, detailed GameFAQs guides,
specialist Bomberman archives and release databases. Chapter source lists retain
the individual URLs and access limitations. No reference binary was newly
executed for this documentation task.

## Evidence hierarchy

| Evidence | Useful for | Limits |
| --- | --- | --- |
| Current official product/rules/update page | Advertised features, platforms, patch/service dates and edition restrictions | Not a measured implementation specification; can change after access. |
| Developer release post, bundled manual or changelog | Version-specific feature claims, settings, fixes and regression leads | Displayed version can survive silent hotfixes; pin bytes before runtime experiments. |
| Original manual scan | Mode/control/option and hardware topology claims | Localization, OCR and edition differences need checking; numerical timing often absent. |
| Detailed guide or specialist play account | Individual items, puzzles, stages, abilities and hidden-option leads | Can contain mistakes, unused-content assumptions, translation issues or unsupported precision. |
| Contemporary review | Distinctive behavior and practical participation limits | Often rounds totals or omits modes; summary is not complete enumeration. |
| Database or master release index | Discovery of obscure titles, dates, platforms and aliases | Indexing establishes a lead; it does not establish all features or a playable release. |
| Search-only result | Candidate source/title worth investigating | No claim that the linked page was successfully read. |

Sources marked as blocked/unavailable are leads, not inspected authority. A page
returning an anti-bot screen, error or maintenance notice was not counted as a
successfully read gameplay guide. Some Fandom, Sega Retro and Hardcore Gaming 101
retrievals failed; accessible specialist pages, manuals and guides supplied the
substitute evidence. Historical project evidence remains separately identified.

## Cross-checks that changed the result

| Claim that needs care | Resolution retained in the dossier |
| --- | --- |
| “Bomberman II introduced multiplayer to the series” | Too broad: 1990 Bomber Boy and PC Engine releases predate it. Say NES sequel introduced its own Vs/Battle modes. Even official marketing can simplify chronology. |
| “The 2026 Collection contains seven games” | Correct at launch; the current official page lists eight after Panic Bomber W's 20 August update. |
| “The Collection physical release was in August” | The current US product page lists 25 September; distinguish the launch announcement's earlier plan and regional SKUs. |
| “R Online was released in 2017” | A stale specialist master-list row; R Online is the separate 2020 title. |
| “Bombergirl launched in 2017” | Announcement/showcase timing differs from the 2018 arcade release. |
| “Amazing Bomberman is currently active” | The official page records service ending 29 May 2025; retain historical features without implying current availability. |
| “R2 supports sixteen players locally” | Castle's total battle capacity is not the same as local controllers on one machine. Keep those capacities separate. |
| “R2 was the first official map editor” | Atomic Bomberman already documents a scheme editor, and other releases have puzzle-editor leads. Describe the actual editor and its scope without an unproved franchise-first claim. |
| “Power Bomberman has no mods” | Existing mod authors document graphics/sound replacements. Current supported authoring/sharing interfaces remain a version-specific research question. |
| “All old console online modes are shut down” | Verify each service independently. A console storefront closure, original matchmaking shutdown and community revival are different events. |

The survey also used an asynchronous, 66-source
[deep-research report](https://agent.tinyfish.ai/playground/research/share/01a19f5c-3ec4-7b74-9f3a-21793bc34957)
as a cross-check. Its generated narrative contains conflicting first-multiplayer
claims, unsupported availability assertions and other overbroad statements.
It was **not copied into the reference chapters or treated as an authority**.
The independently inspected sources and explicit caveats govern this dossier.

## Largest remaining gaps

1. **Carrier builds:** reconcile all i-mode, EZweb, Yahoo!/S! and Java ME releases,
   supported handsets, resolutions, revisions and localized/publisher aliases.
   Many names survive only in indexes or press coverage.
2. **Per-entity inventories:** enumerate every item, illness, combination, mount,
   companion, equipment part, enemy, boss phase, stage and variant against a
   pinned build. Broad feature families do not establish these totals.
3. **Timing and interactions:** measure fuses, movement, blast propagation,
   bounce/carry/throw behavior, invulnerability, simultaneous outcomes, RNG and
   reset/persistence. Guide values are not accepted exact clock contracts.
4. **Regional versions:** validate multiplayer caps, controller topology,
   Battle Pack compatibility, content changes, hidden options and service
   differences per release. Preserve distinct Bomberman/World/64/Online/GB identities.
5. **Network services:** inspect official closure notices and actual supported
   endpoints before claiming availability; identify fan revivals separately.
   Only owned test servers are suitable for protocol/load experiments.
6. **Power Bomberman:** pin developer-distributed client, server and manual hashes,
   any same-version hotfixes, roster/stage counts and actual modding workflows.
   Advertised totals are not an observed completeness denominator.
7. **Compilations and wrappers:** audit regional SKU lists, emulation options,
   save/controller features, translations, patches and storefront/retro-hardware
   reissues without counting each wrapper as a new original design.
8. **Prototypes, toys and adjacent games:** distinguish demonstrable builds from
   announced ideas; identify LCD model numbers and medal/slot revisions. Optional
   adjacent mechanics are not commitments to gambling or toy-service systems.

For each gap, retain the source lead, failed access if any, missing artifact,
next useful experiment and consequence for the claim. Unknown is neither absent
nor implemented. Do not erase a sparse game to make the catalogue look complete.

## Document verification versus game verification

Local documentation checks cover release/candidate ID uniqueness, TSV shape,
source/caveat fields, links to local files, agreement with extracted candidate
tables, existing backlog consistency and whitespace. The repository's existing
research-catalogue and metadata checks validate structure only. The six local
metadata selections passed: 350 input-tooling tests, 14 FILM tests, 14 catalogue
tests, catalogue validation, 211 factory tests and 20 merge-gate tests. The
existing 418-feature backlog also passed its consistency check. These results
apply to the supplied local baseline; protected CI validates the published head
against its current base before integration. No claim is made
that an HTTP URL will remain available, a guide is infallible, or a feature is
implemented because these checks pass.

Faithful Saturn verification still requires the original source and production
Godot state/events, native pixels and native-rate audio under
[SATURN_FIDELITY.md](../SATURN_FIDELITY.md). This documentation changes no game
code, source fixture, comparison tolerance, worker lease or runtime dependency.
