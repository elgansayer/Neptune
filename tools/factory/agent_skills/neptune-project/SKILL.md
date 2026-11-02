---
name: neptune-project
description: Route Neptune Bomberman factory, Saturn/Power research, Godot implementation, multiplayer, bots, content-pack and verification work to the installed specialist skills and existing project tools. Use when selecting a Neptune task, preparing research tools, diagnosing a pipeline failure or making a project change.
---

# Neptune project workflow

Read the current repository `AGENTS.md` and `docs/restart/FACTORY_FIRST_GOAL.md`.
Use their current priorities and the user's current request. Read live issue/PR
ownership before overlapping work. Preserve active sessions and existing limits.

## Choose a workflow

Load only the specialist skills needed for the current question.

| Task | Skills |
| --- | --- |
| Factory/process recovery | python-resilience, python-resource-management, python-observability, async-python-patterns |
| Original binaries and recorded protocols | binary-analysis-patterns, protocol-reverse-engineering, reverse-engineer-anything |
| Local analysis adapters | skill-creator, skill-installer, mcp-builder, python-error-handling, python-testing-patterns |
| Godot changes | godot, godot-gdscript, godot-nodes-scenes, godot-signals-groups, godot-resources |
| Movement and collisions | godot-2d-movement, godot-physics, physics-tuning |
| Bots | game-ai, ai-behavior-trees-utility-ai, performance-optimization |
| Multiplayer and online content | godot-multiplayer, api-design-principles, auth-implementation-patterns |
| Native pixels, presentation and PCM | godot-animation, godot-audio, godot-shaders, godot-tilemap, audio-design |
| Campaign/creator interfaces | godot-ui-control, game-ui-ux, input-systems, level-design, save-systems, dialogue-systems |
| Browser export and clean-client journeys | godot-export, playwright, webapp-testing, screenshot, e2e-testing-patterns |
| Security and accessibility | security-threat-model, security-best-practices, security-ownership-map, accessibility-compliance |
| CI/dependencies/debugging | gh-fix-ci, gh-address-comments, github-actions-templates, dependency-upgrade, systematic-debugging, verification-before-completion |

## Preserve the project contract

- Treat generic code, speeds, fuse durations, audio gains, shake and animation
  examples as examples. Use pinned observations for the faithful Saturn profile.
  Scope invented tuning, adaptive audio and polish to explicitly selected additions.
- Reuse the existing Godot authoritative simulation and LimboAI/hazard components.
  Keep game bot decisions bounded and local; do not call a model in a match tick.
- Keep public downloaded packs data-only, namespaced, immutable and versioned.
  Never run their scripts or replace existing content. Test a second clean client.
- Keep the existing Elgl factory, shared leases, supervision and budgets. Do not
  install an agent swarm, scheduler, service or approval policy as a skill dependency.
- Use REA for supported shipped artifacts. For raw Saturn SH-2 banks, validate the
  actual Ghidra language, loader, memory map and overlay identity separately.
  A working x86 decompiler does not establish Saturn import or recovered semantics.
- Keep original media and raw dumps local/private. Return selected derived evidence.
  Do not send binaries to an external analysis/model service as a convenience.
- Read SATURN_FIDELITY.md and RESEARCH_EXECUTION.md for fidelity claims. Retain
  reference/candidate identities, integer clocks, native pixels/PCM, first divergence
  and meaningful mutation controls. Synthetic tool fixtures certify tools only.

## Prepare and verify

Use `tools/factory/PROVISIONING.md` for existing Godot/emulator recipes and the
reviewed skill recipe in `tools/factory/agent_skills/README.md`. Acquire sources
in preparation; verify installed skill bytes offline:

```sh
python3 tools/factory/agent_skills/install.py --verify
```

Use the existing lab/catalogue entrypoints before building replacements:

```sh
python3 tools/saturn_lab/cli.py --help
python3 tools/research_catalog/cli.py report
```

For tooling changes run `python3 tools/factory/check.py` and applicable merge-gate
checks. For actual Godot/gameplay changes run the current native runner/runtime,
scenario and bot checks required by the changed paths. Require nonempty tests,
nonzero failures for missing/corrupt evidence, and actual execution logs.

Commit and push only task-owned changes in an isolated branch. Follow the current
MERGE_POLICY.md, including applicable successful checks at the exact head/current
base. Report tool readiness, real reference evidence, game fidelity and running
factory status separately. A new skill installation does not complete #508/#518.
