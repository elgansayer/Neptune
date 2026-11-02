# Continuous web and authoritative server builds

`Web release` exports the real browser client and a dedicated Linux Godot server
with the hash-pinned toolchain in `tools/godot/toolchain.json`. Chromium must load
the exported WASM/PCK, connect through Nginx `/ws`, negotiate the multiplayer
protocol, authenticate, and render the server map before images are published.
The existing required native/merge tests remain applicable. This connection test
does not certify full gameplay parity or the broader transport scope in #110.

Main builds publish `ghcr.io/elgansayer/neptune-bomberman-web` and
`ghcr.io/elgansayer/neptune-bomberman-server`, tagged `latest` and
`sha-<full commit>`. PRs run the same build and browser test without publication.
Nginx serves explicit WASM/PCK MIME types, cross-origin isolation headers and
revalidation to avoid mixing releases. Browser sockets use the page's own host
and TLS scheme. Native clients/servers retain ENet by default; an explicit
`--transport=websocket` selects the WebSocket peer without changing the RPC or
authoritative simulation. The dedicated server preset selects its main scene
through a project feature override, without release-binary path overrides.

Production is an Arcane Compose project behind Cloudflare Tunnel at
`bomberman.elgansayer.com`. Its server port is private to the Compose network.
Data persists in the server volume. After publication, the repository secret
`DEPLOY_WEBHOOK_URL` triggers that project's Arcane webhook. `DEPLOY_RESOLVE`
selects the certificate-verified HTTPS origin, avoiding an interactive browser
challenge. No deployment credential is stored in this repository.

Check Arcane's Event Log for the rollout result; webhook acceptance is
asynchronous. To roll back, set both images to the same previous `sha-<full
commit>` or recorded digests and redeploy. Keep those pins until ready to resume
following `latest`. Exported release inputs exclude the research-private tree.


The browser gate opens two clean visitors sequentially against the same server.
The first visitor leaves after its match starts; the second must still
negotiate, authenticate and render a fresh map. This catches the hosted
`round_finished` admission failure that a fresh-server-only smoke misses.

The server replaces a completed joinable room with a new authority for later
visitors. Existing clients retain the completed room and its terminal result
until their last connection leaves, then that retired authority is freed.
Active matches and in-flight exact-content transfers prevent replacement.
The new room uses the same configured map, pack and room options. Console
commands remain on the server autoload and are rebound to the current room.
This is hosted admission recovery, not a complete rematch UI or fidelity claim.
