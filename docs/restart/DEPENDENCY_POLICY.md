# Keep development dependencies current

Elgan's direction, 30 October 2026: always update to the latest packages and
versions, including Godot. Keeping development current is ongoing work, not an
optional cleanup after feature development. This supersedes earlier instructions
to retain Godot 4.5 as the development target.

## Default for all development

- Use the latest stable upstream releases of Godot, packages, addons, SDKs,
  build tools and development tooling. Include major and minor upgrades; do not
  limit maintenance to security patches. Prereleases require an explicit need.
- At task intake and before adding or changing a dependency, check its official
  release source or package registry. Record the source, check date and selected
  version in the change's evidence. Do not assume an installed version, existing
  lockfile or remembered version is current.
- Upgrade outdated dependencies as part of the work. When an upgrade needs a
  separate compatibility change, create or reuse a bounded task with priority,
  an owner and acceptance checks. Record the concrete blocker and next action;
  an old baseline alone is not a reason to defer.
- Keep exact versions, checksums and lockfiles for reproducibility. Refresh them
  when adopting a release, together with provisioning recipes, CI, containers,
  setup examples and documentation. Resolve current versions during maintenance;
  builds and offline verification consume the reviewed pins.
- Fix compatibility failures and run applicable build, runtime and regression
  checks before integrating the upgrade. Never weaken tests to accept it. A
  temporary older pin needs a documented failure, a tracked fix and a recheck at
  the next maintenance pass; do not silently treat it as the preferred version.

## Godot upgrades

Upgrade the editor, headless server, desktop/browser export templates and native
addons as one compatibility change. Check the official release and migration
notes, addon/GDExtension compatibility and any protocol or pack implications.
Update the installer and factory toolchain locks and their integrity hashes.
Validate project import, native class registration, runner contracts, applicable
gameplay/bot scenarios, client/server startup and desktop/browser exports. Report
any checks that could not run and keep that gap visible in the upgrade task.

The current recorded toolchain is Godot 4.7.2. Release sources and verified
archive hashes are recorded in [the release inventory](../../tools/godot/dependency-releases.json).
Recheck upstream releases during maintenance; this version is not a permanent ceiling.

## Factory maintenance and reference evidence

Check for upstream stable releases at the start of each development cycle and
during the factory's regular intake sweep. Deduplicate upgrade work against open
tasks and PRs, include dependency freshness in readiness reports, and apply the
existing tests-gated merge policy. This document does not install a scheduler.

Preserve the exact original game releases, emulator builds, captures and input
locks used by accepted research evidence. Install newer research tools alongside
those versions and validate new evidence explicitly. Historical reference identity
must remain reproducible as development tooling moves forward.
