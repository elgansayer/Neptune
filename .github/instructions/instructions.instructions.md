---
applyTo: '**'
---
Read #file:AGENTS.md and #file:docs/restart/README.md first.

The October 2026 restart includes faithful Saturn campaign/battle, online bots,
browser/desktop cross-play, portable community packs and a complete community site.
Follow #file:docs/restart/REVERSE_ENGINEERING.md and #file:docs/restart/BOTS.md.
Read #file:docs/restart/COMMUNITY_CONTENT.md: prioritise multiplayer and bots, and
support creator power-ups and complete solo/co-op stories through public pack APIs.
The owner's clarified ethos is Saturn-identical starting presentation/behaviour,
then additions-only extensibility. Mods add namespaced content; never overwrite
built-ins/other packs or silently change defaults. Player-hosted server discovery,
automatic exact-version downloads and automatic sharing of each participant's
custom character are core acceptance journeys. Use clean clients to prove them.
Read #file:docs/restart/PROJECT_EVALUATION.md for current source-backed gaps.
Inspect PRs #49/#51 and #50 before choosing new work; preserve the active server task.
Power Bomberman is a second reference; read #file:docs/restart/POWER_BOMBERMAN.md,
#file:docs/restart/FACTORY_PLAYBOOK.md and #file:docs/restart/NETPLAY_BENCHMARKS.md.
Separate documented reference claims from observed and implemented behaviour.
Preserve current server task #40 and its branch when updating foundation docs.

Older prompt.md, PLAN.md and ARCHITECTURE.md contain historical assumptions. Do not
silently restore the superseded TypeScript gameplay server or trust completion
claims without running the actual checks. Keep authoritative gameplay in Godot.

Use bounded runs, inspect server.log for gameplay changes when available, and
report missing dependencies honestly. Read current open PRs before duplicating work.
