# Open source and content delivery

The root `LICENSE` at foundation head `59aef5d2d228a8a2fd597e933ce01b009a48039b`
contains Apache License 2.0. Preserve it and applicable upstream notices. Do not
change the whole repository's licence as part of the restart. An inventory of
third-party code/assets and actual release outputs remains necessary in #46.

The product goal is a buildable, modifiable, self-hostable source release with
documented APIs, dependencies and contribution instructions. Repository visibility
has not been changed. Public release is a separate operation after build/content
checks; a private repository's licence file does not make it publicly available.

## Separate deliverables

| Deliverable | Contents and release treatment |
| --- | --- |
| Source | Our implementation, tests, tools, schemas, docs and permitted dependencies |
| Default pack | Art/audio/fonts with established distribution terms and credits |
| Reference lab | Original binaries, BIOS, save states, extracted bytes and private captures kept outside public releases |
| Community packs | Per-author provenance/licence, version, compatibility and moderation records |

Recovering original graphics and independently implementing gameplay are different
deliverables. Do not automatically put recovered Saturn or Power Bomberman artwork
into an Apache-labelled distribution. Record reuse permission separately, including
fan artists' contributions. Technical import support is not a distribution licence.

Keep the game buildable with permitted placeholders/default content while research
continues. Release packaging should use an explicit file/content allowlist with
tests against accidental inclusion. Examine generated PCKs, export caches, demo
content and Git history when planning public release, not only current source files.
Do not rewrite/delete history automatically during that inventory.

## Creator contract

Anyone can use the documented format to create maps, cosmetics and compatible
character packs. Provide templates, validation, preview and local testing. No
mandatory character unlock or payment gate should obstruct installed custom packs.
Store author credit, source, permission/licence, dependency and API version with
each immutable publication. Support self-hosted registries as a later compatible
distribution option; avoid hard-coding one company's workshop into the game core.

Cosmetics must not secretly alter collision or abilities. Gameplay-changing packs
declare capabilities and use compatible custom rooms. Default online packs are
data-only; future scripting requires a separately tested restricted runtime.
Provide compatibility errors that tell creators what to fix, rather than silently
substituting missing gameplay. Moderation of public distribution is distinct from
the engine's ability to load a technically valid local pack.
