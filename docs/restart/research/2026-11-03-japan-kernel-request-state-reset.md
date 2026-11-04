# Japanese kernel request-state reset helper

This result uses the unchanged Japanese `0KRNL.BIN`, SHA-256
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`, mapped
at `0x0600A000`.

## Original-byte execution

The helper at `0x060A6D3A` has range `[0x060A6D3A, 0x060A6D46)`, including its
RTS delay slot. It reads and returns the old longword at request offset `+56`,
stores incoming `r5` at `+56`, then clears `+36` and `+40`; the last clear is
the return delay-slot store. It leaves `r5` zero. The isolated probe uses a
constructed 60-byte request and permits only the source code fetches, one read
at `+56`, and writes at `+56`, `+36`, and `+40`.

`tools/saturn_lab/probe_japan_request_state_reset.py` covers eight old-state
patterns crossed with four new-state values (32 cases), each executed twice
per report. The full request record is compared after every call. Changing the
store at `0x060A6D3C` from offset `+56` to `+52` is rejected by the exact-write
and record-image controls.

The paired reports
`/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/execution-093/japan-request-state-reset-run1.json`
and `japan-request-state-reset-run2.json` are byte-identical at SHA-256
`36df61fe4858dc5337c271a47bfb710bd1a50ee3fedf66d2cb14cdd8f8d11f1c`. The
executed code SHA-256 is
`dcb99e13501a44dc275c42d25ea21cea3844a7193a7e7c202c16540704d43f34`; the
probe SHA-256 is
`1d0ee3e2a34e6ed47b8ea0d6d99ea53c74f46d75f75a2fd5cd153ea26a6bad18`, and
the ordered result digest is
`c7335ef80a058b486e52c38c428c10813eb7a137a0844c6d50990ae708a232c1`.

The static caller at `0x060A6D04` initializes a request record and calls this
helper with state 3. That caller and its downstream work are not composed in
this result. There is no natural request provenance, callback or BIOS service
validation, device/timing/gameplay proof, or independent-emulator confirmation.
Continue with the composed initializer and follow its request-copy/service
dependencies, then other original modules and assets.
