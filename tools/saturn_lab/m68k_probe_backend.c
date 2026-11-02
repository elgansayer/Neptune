/* Bounded isolated-function adapter around externally pinned Musashi.
 * No original game instructions or third-party CPU implementation bundled.
 * Process-global CPU: one serialized run per process, no concurrent callers.
 */
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <setjmp.h>
#include "m68k.h"

#define MAX_STEPS 256
#define MAX_EVENTS 128
#define MAX_REGIONS 8
#define MAX_RANGES 4

typedef struct { uint32_t lo, size, writable; uint8_t *data; } Region;
typedef struct { uint32_t lo, end; } Range;
typedef struct {
    uint8_t *code;
    uint32_t code_size;
    Region *regions;
    uint32_t region_count;
    Range *ranges;
    uint32_t range_count;
    uint32_t entry, stop, budget;
    uint32_t registers[18]; /* D0..D7,A0..A7,PC,SR: exact Musashi enums. */
} Request;
typedef struct { uint32_t kind, address, size, value; } Event;
typedef struct {
    uint32_t status, error_address, error_size, steps, event_count;
    uint32_t pcs[MAX_STEPS], after[18];
    int32_t model_cycles;
    Event events[MAX_EVENTS];
} Result;

_Static_assert(M68K_REG_D0 == 0 && M68K_REG_A7 == 15 && M68K_REG_PC == 16 && M68K_REG_SR == 17,
               "Unexpected pinned Musashi register ABI");

static Request *request;
static Result *result;
static jmp_buf escaped;
static int initializing;

static void fail(uint32_t status, uint32_t address, uint32_t size) {
    result->status = status;
    result->error_address = address;
    result->error_size = size;
    longjmp(escaped, 1);
}

static void event(uint32_t kind, uint32_t address, uint32_t size, uint32_t value) {
    if (result->event_count >= MAX_EVENTS) fail(6, address, size);
    result->events[result->event_count++] = (Event){kind, address, size, value};
}

static int contains(uint32_t lo, uint32_t length, uint32_t address, uint32_t size) {
    return (uint64_t)lo <= address && (uint64_t)address + size <= (uint64_t)lo + length;
}

static uint32_t read_code(uint32_t address, uint32_t size) {
    if (initializing) {
        if (size == 4 && address == 0) return request->registers[15];
        if (size == 4 && address == 4) return request->entry;
        fail(9, address, size);
    }
    if (address & 1 || !contains(0, request->code_size, address, size)) fail(3, address, size);
    int allowed = 0;
    for (uint32_t i = 0; i < request->range_count; i++) {
        Range *r = &request->ranges[i];
        if (contains(r->lo, r->end-r->lo, address, size)) allowed = 1;
    }
    if (!allowed) fail(3, address, size);
    uint32_t value = 0;
    for (uint32_t i = 0; i < size; i++) value = (value << 8) | request->code[address+i];
    return value;
}

static uint32_t read_data(uint32_t address, uint32_t size) {
    if (size > 1 && address & 1) fail(3, address, size);
    for (uint32_t i = 0; i < request->region_count; i++) {
        Region *r = &request->regions[i];
        if (contains(r->lo, r->size, address, size)) {
            uint32_t value = 0;
            for (uint32_t j = 0; j < size; j++) value = (value << 8) | r->data[address-r->lo+j];
            event(1, address, size, value);
            return value;
        }
    }
    fail(4, address, size);
    return 0;
}

static void write_data(uint32_t address, uint32_t size, uint32_t value) {
    if (size > 1 && address & 1) fail(3, address, size);
    for (uint32_t i = 0; i < request->region_count; i++) {
        Region *r = &request->regions[i];
        if (contains(r->lo, r->size, address, size) && r->writable) {
            event(2, address, size, value);
            for (uint32_t j = 0; j < size; j++) r->data[address-r->lo+j] = value >> ((size-j-1)*8);
            return;
        }
    }
    fail(5, address, size);
}

unsigned int m68k_read_memory_8(unsigned int a) { return read_data(a, 1); }
unsigned int m68k_read_memory_16(unsigned int a) { return read_data(a, 2); }
unsigned int m68k_read_memory_32(unsigned int a) { return read_data(a, 4); }
void m68k_write_memory_8(unsigned int a, unsigned int v) { write_data(a, 1, v); }
void m68k_write_memory_16(unsigned int a, unsigned int v) { write_data(a, 2, v); }
void m68k_write_memory_32(unsigned int a, unsigned int v) { write_data(a, 4, v); }
unsigned int m68k_read_immediate_16(unsigned int a) { return read_code(a, 2); }
unsigned int m68k_read_immediate_32(unsigned int a) { return read_code(a, 4); }
unsigned int m68k_read_pcrelative_8(unsigned int a) { return read_data(a, 1); }
unsigned int m68k_read_pcrelative_16(unsigned int a) { return read_data(a, 2); }
unsigned int m68k_read_pcrelative_32(unsigned int a) { return read_data(a, 4); }

static void instruction(unsigned int pc) {
    if (result->steps >= request->budget) fail(2, pc, 0);
    int found = 0;
    for (uint32_t i = 0; i < request->range_count; i++)
        if (!(pc & 1) && request->ranges[i].lo <= pc && pc < request->ranges[i].end) found = 1;
    if (!found) fail(3, pc, 0);
    result->pcs[result->steps++] = pc;
}

uint32_t neptune_m68k_abi(void) { return 1; }

int neptune_m68k_run(Request *r, Result *out) {
    if (!r || !out) return -1;
    memset(out, 0, sizeof(*out));
    request = r; result = out;
    if (!r->code || !r->code_size || r->code_size > 0x80000 ||
        !r->regions || !r->region_count || r->region_count > MAX_REGIONS ||
        !r->ranges || !r->range_count || r->range_count > MAX_RANGES ||
        !r->budget || r->budget > MAX_STEPS || r->entry & 1 || r->stop & 1 ||
        r->entry == r->stop || r->registers[16] != r->entry ||
        !(r->registers[17] & 0x2000) || r->registers[17] & 0xC000) {
        out->status = 8; return 8;
    }
    for (uint32_t i = 0; i < r->region_count; i++) {
        Region *a = &r->regions[i];
        if (!a->data || !a->size || (uint64_t)a->lo + a->size > 0x80000 ||
            a->writable > 1) { out->status = 8; return 8; }
        /* A controlled data overlay must not replace executable instruction bytes. */
        for (uint32_t j = 0; j < r->range_count; j++) {
            Range *b = &r->ranges[j];
            if (b->lo >= b->end || b->end > r->code_size || b->lo & 1 || b->end & 1 ||
                ((uint64_t)a->lo < b->end && (uint64_t)b->lo < (uint64_t)a->lo+a->size)) {
                out->status = 8; return 8;
            }
        }
        for (uint32_t j = i+1; j < r->region_count; j++) {
            Region *b = &r->regions[j];
            if ((uint64_t)a->lo < (uint64_t)b->lo+b->size && (uint64_t)b->lo < (uint64_t)a->lo+a->size) {
                out->status = 8; return 8;
            }
        }
    }
    if (setjmp(escaped) == 0) {
        /* Construct CPU reset state with synthetic vectors, execute zero original
         * reset instructions, drain reset accounting, then set every visible reg.
         * All initialization accesses are excluded from experiment evidence.
         */
        initializing = 1;
        m68k_init();
        m68k_set_cpu_type(M68K_CPU_TYPE_68000);
        m68k_pulse_reset();
        m68k_execute(1);
        initializing = 0;
        m68k_set_reg(M68K_REG_SR, r->registers[17]);
        for (uint32_t i = 0; i < 16; i++) m68k_set_reg((m68k_register_t)i, r->registers[i]);
        m68k_set_reg(M68K_REG_PC, r->entry);
        m68k_set_instr_hook_callback(instruction);
        while (m68k_get_reg(NULL, M68K_REG_PC) != r->stop) {
            uint32_t before = out->steps;
            int cycles = m68k_execute(1);
            if (out->steps != before+1 || cycles <= 0 || cycles > 1000) fail(7, 0, 0);
            out->model_cycles += cycles;
        }
        out->status = 1;
    }
    for (uint32_t i = 0; i < 18; i++) out->after[i] = m68k_get_reg(NULL, (m68k_register_t)i);
    initializing = 0;
    return out->status;
}
