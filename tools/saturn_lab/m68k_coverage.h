/* Neptune natural 68000 coverage observer, ABI 1.
 *
 * Included exactly once into the pinned Beetle Saturn
 * mednafen/hw_cpu/m68k/m68k.c by tools/saturn_lab/m68k_coverage_core.py.
 * Neptune-authored observation code (Apache-2.0 repository); the patched core
 * that includes it remains GPL with its upstream notices.
 *
 * Observation only. Hooks read the program counter and the opcode word that
 * the interpreter has already fetched through its own bus path; they never call
 * a bus accessor, never alter CPU, device, timing or event state and never
 * allocate while the CPU is mid-instruction except at an observed reset.
 *
 * Recording is per 68000 reset "epoch": each reset processed by M68K_Run starts
 * a fresh table, because different sound programs reuse sound-CPU address zero.
 * Instructions executed before the first observed reset are only counted.
 * Exhausting any declared capacity is a recorded overflow; the Python side must
 * treat overflow as failure rather than as truncated evidence.
 */
#ifndef NEPTUNE_M68K_COVERAGE_H
#define NEPTUNE_M68K_COVERAGE_H

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define NEPTUNE_M68KCOV_ABI 1u
#define NEPTUNE_M68KCOV_EPOCHS 16u
#define NEPTUNE_M68KCOV_WORDS 0x40000u /* even PCs in [0, 0x80000): sound RAM */
#define NEPTUNE_M68KCOV_EDGE_BITS 16u
#define NEPTUNE_M68KCOV_EDGES (1u << NEPTUNE_M68KCOV_EDGE_BITS)
#define NEPTUNE_M68KCOV_EDGE_LIMIT ((NEPTUNE_M68KCOV_EDGES / 4u) * 3u)
#define NEPTUNE_M68KCOV_NONE 0xFFFFFFFFu

/* Edge kinds stored in key bits 15..8. */
#define NEPTUNE_M68KCOV_EDGE_FLOW 0u      /* previous instruction -> this one */
#define NEPTUNE_M68KCOV_EDGE_EXCEPTION 1u /* stacked return PC -> vector target */
#define NEPTUNE_M68KCOV_EDGE_EPOCH 2u     /* first instruction after reset */

typedef struct
{
 uint64_t key; /* from << 40 | to << 16 | (0x80|kind) << 8 | vector; 0 = empty */
 uint32_t count;
 uint32_t first_frame;
} neptune_m68kcov_edge;

typedef struct
{
 uint32_t reset_pc, reset_ssp, first_frame, last_frame;
 uint32_t opcode_changes, outside, first_outside_pc, edges_used, edge_overflow, reserved;
 uint64_t steps;
 uint64_t exceptions[256];
 uint32_t hits[NEPTUNE_M68KCOV_WORDS];
 uint32_t first[NEPTUNE_M68KCOV_WORDS]; /* first frame + 1; 0 = never */
 uint16_t op[NEPTUNE_M68KCOV_WORDS];    /* first fetched opcode word */
 uint8_t changed[NEPTUNE_M68KCOV_WORDS];
 neptune_m68kcov_edge edges[NEPTUNE_M68KCOV_EDGES];
} neptune_m68kcov_epoch_t;

/* Fixed-size header copied to the frontend; layout mirrored in Python. */
typedef struct
{
 uint32_t reset_pc, reset_ssp, first_frame, last_frame;
 uint32_t opcode_changes, outside, first_outside_pc, edges_used, edge_overflow, executed_words;
 uint64_t steps;
 uint64_t exceptions[256];
} neptune_m68kcov_header;

static int neptune_m68kcov_on, neptune_m68kcov_started;
static uint32_t neptune_m68kcov_frame_no;
static int neptune_m68kcov_cur = -1;
static uint32_t neptune_m68kcov_prev = NEPTUNE_M68KCOV_NONE;
static uint32_t neptune_m68kcov_pending; /* 0x100 | vector when an exception was taken */
static uint32_t neptune_m68kcov_pending_save;
static uint32_t neptune_m68kcov_epoch_count, neptune_m68kcov_epoch_overflow, neptune_m68kcov_alloc_failed;
static uint64_t neptune_m68kcov_unepoched;
static neptune_m68kcov_epoch_t *neptune_m68kcov_epoch[NEPTUNE_M68KCOV_EPOCHS];

static void neptune_m68kcov_edge_add(neptune_m68kcov_epoch_t *e, uint32_t from, uint32_t to, uint32_t kind, uint32_t vec)
{
 /* Kind byte carries a 0x80 presence marker, so a stored key is never zero. */
 const uint64_t key = ((uint64_t)(from & 0xFFFFFFu) << 40) | ((uint64_t)(to & 0xFFFFFFu) << 16) |
                      ((uint64_t)((kind & 0x7Fu) | 0x80u) << 8) | (uint64_t)(vec & 0xFFu);
 uint32_t slot = (uint32_t)((key * 0x9E3779B97F4A7C15ull) >> (64u - NEPTUNE_M68KCOV_EDGE_BITS));
 for(uint32_t probe = 0; probe < NEPTUNE_M68KCOV_EDGES; probe++)
 {
  neptune_m68kcov_edge *edge = &e->edges[slot];
  if(edge->key == key)
  {
   if(edge->count != 0xFFFFFFFFu) edge->count++;
   return;
  }
  if(!edge->key)
  {
   if(e->edges_used >= NEPTUNE_M68KCOV_EDGE_LIMIT)
   {
    e->edge_overflow++;
    return;
   }
   edge->key = key;
   edge->count = 1;
   edge->first_frame = neptune_m68kcov_frame_no;
   e->edges_used++;
   return;
  }
  slot = (slot + 1u) & (NEPTUNE_M68KCOV_EDGES - 1u);
 }
 e->edge_overflow++;
}

static void neptune_m68kcov_reset(M68K *z)
{
 if(!neptune_m68kcov_on) return;
 neptune_m68kcov_prev = NEPTUNE_M68KCOV_NONE;
 neptune_m68kcov_pending = 0;
 if(neptune_m68kcov_epoch_count >= NEPTUNE_M68KCOV_EPOCHS)
 {
  neptune_m68kcov_epoch_overflow++;
  neptune_m68kcov_cur = -1;
  return;
 }
 neptune_m68kcov_epoch_t *e = (neptune_m68kcov_epoch_t *)calloc(1, sizeof(*e));
 if(!e)
 {
  neptune_m68kcov_alloc_failed++;
  neptune_m68kcov_cur = -1;
  return;
 }
 e->reset_pc = z->PC;
 e->reset_ssp = z->A[7];
 e->first_frame = neptune_m68kcov_frame_no;
 e->last_frame = neptune_m68kcov_frame_no;
 e->first_outside_pc = NEPTUNE_M68KCOV_NONE;
 neptune_m68kcov_epoch[neptune_m68kcov_epoch_count] = e;
 neptune_m68kcov_cur = (int)neptune_m68kcov_epoch_count++;
}

static void neptune_m68kcov_exception(M68K *z, unsigned vecnum, uint32_t saved_pc)
{
 (void)z;
 if(!neptune_m68kcov_on) return;
 neptune_m68kcov_pending = 0x100u | (vecnum & 0xFFu);
 neptune_m68kcov_pending_save = saved_pc;
 if(neptune_m68kcov_cur >= 0) neptune_m68kcov_epoch[neptune_m68kcov_cur]->exceptions[vecnum & 0xFFu]++;
}

/* Called after M68K_Run's own ReadOp: PC-2 is the instruction just fetched. */
static void neptune_m68kcov_step(M68K *z, uint16_t instr)
{
 if(!neptune_m68kcov_on) return;
 const uint32_t pc = z->PC - 2u;
 if(neptune_m68kcov_cur < 0)
 {
  neptune_m68kcov_unepoched++;
  neptune_m68kcov_prev = pc;
  neptune_m68kcov_pending = 0;
  return;
 }
 neptune_m68kcov_epoch_t *e = neptune_m68kcov_epoch[neptune_m68kcov_cur];
 e->steps++;
 e->last_frame = neptune_m68kcov_frame_no;
 if((pc & 1u) || pc >= 0x80000u)
 {
  if(!e->outside) e->first_outside_pc = pc;
  e->outside++;
 }
 else
 {
  const uint32_t index = pc >> 1;
  if(e->hits[index] == 0)
  {
   e->op[index] = instr;
   e->first[index] = neptune_m68kcov_frame_no + 1u;
  }
  else if(e->op[index] != instr)
  {
   e->changed[index] = 1;
   e->opcode_changes++;
  }
  if(e->hits[index] != 0xFFFFFFFFu) e->hits[index]++;
 }
 if(neptune_m68kcov_pending)
  neptune_m68kcov_edge_add(e, neptune_m68kcov_pending_save, pc, NEPTUNE_M68KCOV_EDGE_EXCEPTION, neptune_m68kcov_pending & 0xFFu);
 else if(neptune_m68kcov_prev == NEPTUNE_M68KCOV_NONE)
  neptune_m68kcov_edge_add(e, 0, pc, NEPTUNE_M68KCOV_EDGE_EPOCH, 0);
 else
  neptune_m68kcov_edge_add(e, neptune_m68kcov_prev, pc, NEPTUNE_M68KCOV_EDGE_FLOW, 0);
 neptune_m68kcov_pending = 0;
 neptune_m68kcov_prev = pc;
}

uint32_t neptune_m68kcov_abi(void) { return NEPTUNE_M68KCOV_ABI; }

int neptune_m68kcov_begin(void)
{
 /* One observation window per process: evidence from separate windows never mixes. */
 if(neptune_m68kcov_started) return -1;
 neptune_m68kcov_started = 1;
 neptune_m68kcov_cur = -1;
 neptune_m68kcov_prev = NEPTUNE_M68KCOV_NONE;
 neptune_m68kcov_pending = 0;
 neptune_m68kcov_unepoched = 0;
 neptune_m68kcov_on = 1;
 return 0;
}

void neptune_m68kcov_frame(uint32_t frame) { neptune_m68kcov_frame_no = frame; }

void neptune_m68kcov_stop(void) { neptune_m68kcov_on = 0; }

/* status[0..7]: abi, on, epochs, epoch overflow, alloc failures, unepoched lo/hi, layout bytes */
void neptune_m68kcov_status(uint32_t *status)
{
 status[0] = NEPTUNE_M68KCOV_ABI;
 status[1] = (uint32_t)neptune_m68kcov_on;
 status[2] = neptune_m68kcov_epoch_count;
 status[3] = neptune_m68kcov_epoch_overflow;
 status[4] = neptune_m68kcov_alloc_failed;
 status[5] = (uint32_t)neptune_m68kcov_unepoched;
 status[6] = (uint32_t)(neptune_m68kcov_unepoched >> 32);
 status[7] = (uint32_t)sizeof(neptune_m68kcov_header);
}

int neptune_m68kcov_header_get(uint32_t index, neptune_m68kcov_header *out)
{
 if(index >= neptune_m68kcov_epoch_count || !out) return -1;
 const neptune_m68kcov_epoch_t *e = neptune_m68kcov_epoch[index];
 uint32_t executed = 0;
 for(uint32_t i = 0; i < NEPTUNE_M68KCOV_WORDS; i++) executed += e->hits[i] != 0;
 memset(out, 0, sizeof(*out));
 out->reset_pc = e->reset_pc;
 out->reset_ssp = e->reset_ssp;
 out->first_frame = e->first_frame;
 out->last_frame = e->last_frame;
 out->opcode_changes = e->opcode_changes;
 out->outside = e->outside;
 out->first_outside_pc = e->first_outside_pc;
 out->edges_used = e->edges_used;
 out->edge_overflow = e->edge_overflow;
 out->executed_words = executed;
 out->steps = e->steps;
 memcpy(out->exceptions, e->exceptions, sizeof(out->exceptions));
 return 0;
}

int neptune_m68kcov_words(uint32_t index, uint32_t *hits, uint32_t *first, uint16_t *op, uint8_t *changed)
{
 if(index >= neptune_m68kcov_epoch_count || !hits || !first || !op || !changed) return -1;
 const neptune_m68kcov_epoch_t *e = neptune_m68kcov_epoch[index];
 memcpy(hits, e->hits, sizeof(e->hits));
 memcpy(first, e->first, sizeof(e->first));
 memcpy(op, e->op, sizeof(e->op));
 memcpy(changed, e->changed, sizeof(e->changed));
 return 0;
}

int neptune_m68kcov_edges(uint32_t index, uint64_t *keys, uint32_t *counts, uint32_t *first, uint32_t capacity)
{
 if(index >= neptune_m68kcov_epoch_count || !keys || !counts || !first) return -1;
 const neptune_m68kcov_epoch_t *e = neptune_m68kcov_epoch[index];
 uint32_t n = 0;
 for(uint32_t i = 0; i < NEPTUNE_M68KCOV_EDGES; i++)
 {
  if(!e->edges[i].key) continue;
  if(n >= capacity) return -2;
  keys[n] = e->edges[i].key;
  counts[n] = e->edges[i].count;
  first[n] = e->edges[i].first_frame;
  n++;
 }
 return (int)n;
}

#endif
