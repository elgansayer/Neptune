# Original Saturn Bomberman menu route and bounded call observation

This is a bounded navigation and observer result toward issue #492 and the
all-original-code recovery programme. It does not establish a gameplay capture,
complete a function, recover all game code, or extract the full asset set.

## Original and observer identity

The executed image was the private USA MK-81070 Saturn Bomberman disc from the
existing media lock (`eb0d91e0bebd63af78181ce4d4d6af354554466b1f726bfe700e78eff6275cba`).
The source kernel was the unchanged `0KRNL.BIN` with SHA-256
`20109f506afd076af8a8583121dbb5a4880e0a764ee8e004c17b0cb055c798a7`. Runs used
the accepted Beetle/Mednafen Saturn reference core, SH-2 JIT disabled, and the
prepared observer generation with SHA-256
`a7f9d41099da929029ed7672e0c81b27eda1f14e385e611f2fef39e71ebfe328`. The native
observer remains limited to inspected entries `0x0600B934` and `0x0600A0EC`,
128 records, and 4096 master dispatches per pending call.

## Actual menu observations

Separate original executions continued from accepted original save states.
Observed screens included the Battle/Rules/Bombers setup tabs, Character Select,
and the Match/Series/Quit prompt. A left input moved the character cursor from
W-Bomberman to KONU. Start returned from Character Select to the setup menu.
Further inputs reached the Match prompt and setup shell. The saved frame-9451
checkpoint is the setup shell after Match mode selection; no match arena or
active battle has been verified. The exploratory inputs and every checkpoint are retained outside Git
under `/home/dev/neptune-evidence/code712-20261103/original-a0ec-study-20261103/`
in `navigation-034` through `navigation-054`.

The latest resumable state is
`navigation-054/start-pulse-then-release-60/checkpoint.json`, frame 9451, state
SHA-256 `0f2c9a8651bd23ff2195046802f4a9ca77a854894fbc35b7e25966390fd7857d`.
Its result and supervisor receipts preserve core/media identity, input schedule,
screenshots, process status, and hashes. The private application checkpoint at
`/home/dev/neptune-evidence/code-recovery-app-20261102.json` records the complete
evidence map, active owners, configured limits, and next step.

## B934 result and A0EC status

The prepared observer ran for 600 frames from the retained setup-shell menu
checkpoint. The core completed 149,548,301 master SH-2 dispatches. It recorded
zero `0x0600B934` entries, so the run correctly ended with an empty-trace
rejection. The complete failure receipt, native observations, final state,
rejected trace diagnostic, and supervisor log remain at
`/home/dev/neptune-evidence/code712-20261103/original-a0ec-study-20261103/attempt-004/`.
The supervisor receipt inherited a stale `checkpoint_frame: 4411` and an
A0EC-flavoured owner label from the previous script. The actual input checkpoint
is frame 9451, established by its checkpoint JSON and the executed result's
`reference_frame: 9451`. The original receipt remains unchanged; this metadata
discrepancy is recorded rather than silently repaired. This is evidence that the
observer ran through the declared window, not evidence of a B934 call.

Three earlier 600-frame original windows targeted `0x0600A0EC`: title input,
the post-Battle-Game transition, and Character Select idle. Each completed its
declared master-dispatch window with no A0EC records. Their empty-trace failures
are retained under `attempt-001` through `attempt-003`. No natural A0EC caller,
register/stack context, or gameplay call has been captured.

## Reproduction boundaries and next work

The shared resource gate used its configured concurrency limit of 3 and
180-second leases. Original media, kernel, source, checkpoint, and prepared core
were read-only inside the offline worker namespace. No owner reservation was
modified. The host had about 4.3 GiB free, below the retained 6 GiB native-build
reserve, so no local emulator build was started.

Resume from the saved menu checkpoint, reach and verify an active match before
claiming gameplay coverage, then run fresh bounded reference/disabled/enabled
windows for natural A0EC calls. If menu navigation remains unproductive, move to
another inspected original function or module. A second validated Saturn
emulator may help independent corroboration when available; this host's current
evidence is from the pinned Beetle/Mednafen lineage and does not claim an
independent emulator result. Keep the all-code and all-assets programme active.
