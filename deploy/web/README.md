# Continuous web build

`Web release` imports and exports the actual project using the hash-pinned Godot
and templates in `tools/godot/toolchain.json`. A Chromium startup check must pass
before main builds publish `ghcr.io/elgansayer/neptune-bomberman-web`, tagged
`latest` and `sha-<full commit>`. PR builds validate without registry credentials.

The serving image contains only `build/web`, not repository or research inputs.
Nginx serves WASM and PCK with explicit MIME types, cross-origin isolation headers,
and revalidation so browsers do not mix releases. Runtime multiplayer availability
is separate from the web-client startup check.

Production uses a Compose project managed through Arcane and Cloudflare Tunnel at
`bomberman.elgansayer.com`. After image publication, the repository secret
`DEPLOY_WEBHOOK_URL` triggers the project's Arcane webhook. The server keeps its
webhook token and registry credentials outside this repository. Check Arcane's
Event Log for the actual deployment result; webhook acceptance is asynchronous.

To roll back, set the production service image to a prior `sha-<full commit>` or
immutable digest and redeploy through Arcane. Keep the pinned image until ready
to resume following `latest`.
