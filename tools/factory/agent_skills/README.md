# Neptune agent skills and research development tools

Supports #508 / RLAB-001 and #518 / FACTORY-017. On 2 November 2026, 343 skill
entries in six public collections plus REA were screened against the current
Neptune contracts. The reviewed selection contains **59 upstream skills and one
project workflow**, with exact archive and per-skill tree hashes in
`skills-lock.json`. It covers the factory/Saturn priority and the retained Godot,
multiplayer, bots, browser, creator and community-content requirements.

The source collections are gamedev-skills/awesome-gamedev-agent-skills,
haxqer/godot-skill, openai/skills, wshobson/agents, obra/superpowers and
anthropics/skills. REA instructions come from the published rea-agents 6.8.0
package, rather than repository main. Sources are acquired without executing
their hooks. The cache retains upstream licences, references and helper scripts.

## Prepare once, verify offline

Run the recipe from a coordinator-trusted checkout as an unprivileged preparation
job with the existing network, disk and resource limits. It requires Python 3.12+.
Use the existing shared lease/budget boundary; this CLI is not an OS sandbox,
scheduler, provider session or substitute for the Elgl capability receipt flow.

```sh
python3 tools/factory/agent_skills/install.py --download
python3 tools/factory/agent_skills/install.py --verify
```

By default archives and verified generations live under
`.factory-tools/agent-skills`; `.agents/skills` contains local discovery symlinks.
Both are ignored. `--cache` and `--dest` support an explicit prepared mount.
Offline verification needs the same arguments when nondefault locations were used.
Installation does not modify global agent settings or register an MCP server.
Start a new agent turn/session to discover the skills; explicitly load
`neptune-project` to choose the relevant specialists.

The recipe checks pinned source identities, bounded archive sizes, safe paths,
selected skill entrypoints and every selected file. It refuses selected links,
foreign registrations, missing archives and modified bytes. It never follows
unrelated upstream convenience links. A failed preparation publishes no ready
generation. Existing conflicting registrations remain available for inspection;
do not overwrite them to refresh a pin. Stage an updated selection separately,
verify it and switch managed registrations under the existing ownership rules.

`tools/factory/tests/test_agent_skills.py`, included in the existing factory test
suite, exercises real install/reuse, read-only verification, wrong hashes,
tampering, missing input/resumption, path traversal, selected symlinks, duplicate
names, mutable revisions, foreign registrations and missing entrypoints.

## Selection and scope

| Work | Included specialists |
| --- | --- |
| Factory and research tools | Python testing, resilience, errors, observability, resource/performance management, async patterns, uv, defensive Bash, memory safety, MCP builder, skill creator/installer |
| Original artifacts | REA, binary analysis, recorded protocol analysis |
| Godot | GDScript, scenes/nodes, resources, signals, 2D movement, physics, animation, audio, shaders, tilemaps, UI, exports and headless tests; Godot scene/readback helpers |
| Bots and game systems | AI, behavior trees/utility, input, cameras, level design, saves, dialogue, performance, physics and explicitly selected game-feel additions |
| Browser and community | Playwright, webapp testing, screenshots, end-to-end testing, API/auth design, accessibility and threat/security analysis |
| Delivery | GitHub CI diagnosis and comment handling, Actions templates, dependency upgrades, systematic debugging and evidence before completion |

Do not enable the collections' broad orchestrators, hooks, automatic publication,
alternative engines, paid asset services or a replacement factory. Godogen/ECC/
Hermes-style application frameworks are not required for these skill folders.
Generated art/audio does not replace reference extraction. The installed generic
skills remain subordinate to the current project contracts and user request.

Preserve the unchanged Saturn baseline. Generic movement/fuse values, camera shake,
audio randomization, smoothing, loudness and animation examples do not establish
reference behavior. Enhanced profiles are explicit choices. Keep downloaded public
packs data-only and immutable, simulation authoritative and competitive bots fair.

## Supporting tool pins and observed checks

`tools-lock.json` records source URLs, hashes, compatibility limits and observed
reused tools. The local preparation added Node 26.13.0, Ghidra 12.2, Temurin JDK
25.0.5, REA 6.8.0 and a separate Ghidra 12.1.4 compatibility installation. Godot
4.7.2 uses the existing trusted recipe and unchanged addon/toolchain hashes.

Published REA 6.8.0 rejects Ghidra 12.2 despite newer repository-main documentation.
Its adapter therefore uses 12.1.4; direct PyGhidra uses 12.2. Track the compatibility
exception in #508 and recheck the next published REA release. REA 6.8.0 also
accepts output schema profiles `full`/`off`, not the newer `compact` profile.
The checked launcher uses compact input and output schemas off. Client launch and
connection are separate from a successful standalone MCP handshake.

The published REA dependency tree initially had five npm audit findings. Local
overrides to Zod 4.6.7, glob 14.0.3 and minimatch 11.0.3 removed all reported
findings at the check date. Reproduce with the adjacent package files:

```sh
mkdir -p .factory-tools/rea-cli
cp tools/factory/agent_skills/rea-package.json .factory-tools/rea-cli/package.json
cp tools/factory/agent_skills/rea-package-lock.json .factory-tools/rea-cli/package-lock.json
npm ci --prefix .factory-tools/rea-cli --ignore-scripts --omit=optional
```

For a read-only home, invoke `gdtoolkit_cli.py lint --cache /writable/cache`
or `gdtoolkit_cli.py format --cache /writable/cache` before the normal arguments.
The pinned gdtoolkit 4.5.0 ignores XDG_CACHE_HOME; this small launcher selects
a private grammar cache without changing HOME or the upstream package.

Use the pinned compatible Node runtime. Optional native instrumentation and PTY
dependencies are not claimed ready. The Python test/lint/analysis set is separately
hash-locked; provision it in a private environment rather than the system Python:

```sh
uv venv --python 3.12 .factory-tools/research-python
uv pip sync --python .factory-tools/research-python/bin/python --require-hashes tools/factory/agent_skills/python-requirements.lock
```

Retain the actual preparation and feature-smoke receipts in the job's evidence
directory. Validate a helper's real output, not only its exit code. Local synthetic
scene authoring/readback, browser interaction/capture, JavaScript analysis and
native decompilation establish those tools' operation only. Ghidra advertises SH-2
languages; actual Saturn loaders, overlays, addresses and recovered semantics
still require #481/#508's original-input and negative-control acceptance.

This rollout does not claim VPS installation, a new running provider/factory,
second-agent recovery, original-disc extraction, cross-play or exact game parity.
Keep #508/#518 open for their remaining operational and original-input evidence.
