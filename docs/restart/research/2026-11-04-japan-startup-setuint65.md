# Japan startup SCU mask and service 65

## Original inputs and execution

The probe executes the Japan `0KRNL.BIN` (`0KRNL.BIN`, 786,432 bytes,
SHA-256 `23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`)
at its observed WorkRAM-H mapping. The full source bytes at `0x0600A338–0x0600A34E`
and helper bytes at `0x0609E988–0x0609E9AC` are checked against the captured
frame-1200 WorkRAM-H image (state SHA-256
`c115d4b4da8a24f62834235456263465d9bc2c1b8d4ab0deecb7784c1afe8f2f`). The
captured BIOS vector slots and runtime stubs are taken from that same state.
Interpreter source is pinned to `saturn-recomp` revision
`f20de940e8013fc84103a5b39c4069ed8071b1f9`.

Two reports in private evidence directory
`/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/execution-199/`
are byte-identical. Each report contains four constructed register cases, each
executed twice, and three rejected mutation controls. Report SHA-256:
`442f308e88aa26f842f3749e4d69e29e9b4ba40ef43b33caf2fd6bfe786c81b8`.
The normalized results SHA-256 is
`2df29563dd6dd2186ede56696d64499a2a59a1913a6314ad013b3de3546c00fc`;
the final probe SHA-256 is
`e369d92168b7a3c442b853be9fd78926763c8773f2f777746b6986bdad7af542`.

## Recovered bounded behavior

Execution begins at `0x0600A338`, after earlier startup setup. Original
instructions load the captured `SYS_CHGSCUIM` vector slot at `0x06000344`, call
the captured runtime stub at `0x060007C0`, then call the original helper at
`0x0609E988`. The caller next loads the captured `SYS_SETUINT` vector at
`0x06000300`, passes service-table value `0x0600A308`, and calls the captured
stub at `0x06000794`. The setter scales service 65 to index 260 and writes
`0x06000A04` from `0x0600B344` to `0x0600A308`; execution returns to
`0x0600A350` with SR restored to `0xF0`.

The SCU stub reads mask word `0xFFFFD77C` from slot `0x06000348`, applies the
caller's `R4=-1` and `R5=2`, and stores `0xFFFFD77E` back to that slot. The
probe records write intents to SCU IMS `0x25FE00A0` with value `0xFFFFD77E`
and IMS+4 `0x25FE00A4` with value `0xFFFFFFFF`. No write to IMS+8 is observed
for this input. The bus addresses are isolated as MMIO events, not backed by
flat RAM.

The original `0x0609E988` helper writes eight startup globals: a zero halfword
at `0x060BC678`, a one longword at `0x060BC67C`, zero longwords at
`0x060BC680`, `0x060BC684`, `0x060BC688`, `0x060BC68C`, `0x060BC690`, and
`0x060FCBF8`. The bytewise WorkRAM comparison permits only these eight helper
stores, the mask slot update, and the service-65 table store, leaving 1,048,538
WorkRAM bytes unchanged.

Mutation controls change the service pointer literal at `0x0600A3C4`, the
setter vector slot, and the SCU address literal at `0x060007E8`. Each is
rejected by its corresponding table-write, PC-fence, or MMIO-address contract.

## Limits and continuation

This is a bounded CPU interpretation of original Japan kernel instructions
combined with frame-1200 captured WorkRAM state. Registers and the entry boundary
are constructed. The captured runtime stubs are not proven BIOS-ROM copies;
SCU writes are intents without hardware timing or completion. Earlier startup
calls, polling, later initialization, natural caller reachability, gameplay,
and other functions remain untested. The startup function and whole-code
reverse-engineering programme remain active and incomplete.

The first startup-only run is retained as a failure because its literal map
initially omitted the source literal at `0x0600A3B8`; it stopped on that
unexpected read before producing cases. The follow-up diagnostic run exposed a
mutation-sink routing issue; the corrected MMIO sink rejects the altered SCU
address explicitly. These failures are not counted as original function
results.
