/* Neptune-owned synthetic producer for the separately supplied pinned serializer.
 * This is not a Saturn emulator and contains no original game data. */
#include <stdio.h>
#include <stdlib.h>
#include "state.h"
#include "libretro.h"

retro_log_printf_t log_cb = NULL;
static uint16_t v1[0x40000], v2[0x40000], cram[2048], regs[256];
/* Match the actual vdp1_common.h aliases and SFVAR calls. The dispatch macro
 * expands aliases before its inner stringification, producing prefixed keys. */
#define TVMR VDP1_TVMR
#define FBCR VDP1_FBCR

int LibRetro_StateAction(StateMem *sm, const unsigned load) {
    uint32_t cur = 0x120;
    int32_t ret = -1, phase = 2;
    uint8_t active = 1, draw = 0, mode = 0, hres = 0, vres = 0, interlace = 0;
    uint8_t VDP1_TVMR = 3, VDP1_FBCR = 16, ptmr = 1, edsr = 2;
    uint16_t ramctl = 0;
    SFORMAT one[] = {
        SFPTR16N(v1, 0x40000, "VRAM"),
        SFVARN(cur, "CurCommandAddr"), SFVARN(ret, "RetCommandAddr"),
        SFVARN(phase, "CommandPhase"), SFVARN(active, "DrawingActive"),
        SFVARN(draw, "FBDrawWhich"), SFVAR(TVMR),
        SFVAR(FBCR), SFVARN(ptmr, "PTMR"), SFVARN(edsr, "EDSR"), SFEND
    };
    SFORMAT two[] = {
        SFPTR16N(v2, 0x40000, "VRAM"), SFPTR16N(cram, 2048, "CRAM"),
        SFPTR16N(regs, 256, "RawRegs"), SFVARN(mode, "CRAM_Mode"),
        SFVARN(hres, "HRes"), SFVARN(vres, "VRes"),
        SFVARN(interlace, "InterlaceMode"), SFVARN(ramctl, "RAMCTL_Raw"), SFEND
    };
    return MDFNSS_StateAction(sm, load, 0, one, "VDP1", false) &&
           MDFNSS_StateAction(sm, load, 0, two, "VDP2", false);
}

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    for (unsigned i = 0; i < 0x40000; i++) {
        v1[i] = (uint16_t)(i ^ 0x50A3); v2[i] = (uint16_t)(i ^ 0xB400);
    }
    for (unsigned i = 0; i < 2048; i++) cram[i] = (uint16_t)(i * 3);
    for (unsigned i = 0; i < 256; i++) regs[i] = (uint16_t)(i * 19);
    StateMem sm = {0};
    if (!MDFNSS_SaveSM(&sm, 0x00103201)) return 3;
    FILE *out = fopen(argv[1], "wb");
    if (!out) { free(sm.data); return 4; }
    size_t n = fwrite(sm.data, 1, sm.len, out);
    int closed = fclose(out);
    free(sm.data);
    return n == sm.len && !closed ? 0 : 5;
}
