# Japan AD60 ready poll

Original AD60 loads the cache-through ready-word alias `0x2600A028`, selects one
of two words from VBR bit 2, and tests it. Zero takes the BT to AD76 and returns
without changing R4; nonzero takes the BRA to ACE8 and sets R4 to one in the
delay slot. The probe executes the original helper for zero and one in each
VBR slot, with two independent register seeds per input: eight original-byte
runs. It verifies the returned/ACE8 edge, selected alias read, delay-slot
effect, and unchanged stack/linkage. An AD70 `BT` to `BF` mutation makes the
zero-ready case reach ACE8 and is rejected.

The run starts from captured frame-1200 WorkRAM-H but constructs the selected
ready words, VBR, and registers. It stops at ACE8 before that routine executes;
ready-word provenance and natural poll reachability are not established.

Private report: `execution-272/japan-ad60-ready-poll.json` (SHA-256
`e53dacc5fd76822350ed7177dbf8f9f3c3910d582c7e2b2ba614aed5bda8a02e`, mode
0600). Three failed harness attempts in executions 269–271 are preserved.
Next, compose the nonzero edge with ACE8/A164/A186, then follow its restored
task continuation into further original functions. Full code and asset recovery
remains ongoing.
