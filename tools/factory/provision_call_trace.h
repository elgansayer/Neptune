/* SPDX-License-Identifier: GPL-2.0-or-later
 * Bounded observation for the matched Mednafen/Beetle research core.
 * This file follows that component's licence; Neptune's root licence is unchanged.
 * No observed state is written back to the emulator or original game.
 */
#ifndef NEPTUNE_CALL_TRACE_H
#define NEPTUNE_CALL_TRACE_H

#include <stdint.h>
#include <string.h>

#if defined(__GNUC__)
#define NEPTUNE_TRACE_EXPORT __attribute__((visibility("default")))
#else
#define NEPTUNE_TRACE_EXPORT
#endif

enum { NEPTUNE_TRACE_ABI = 2, NEPTUNE_TRACE_RECORDS = 128, NEPTUNE_TRACE_STEP_LIMIT = 4096 };
typedef struct {
 uint32_t sequence, kind, cpu, frame, pc;
 int32_t timestamp;
 uint32_t dispatch_steps, opcode;
 uint32_t r[16];
 uint32_t sr, gbr, vbr, mach, macl, pr;
} NeptuneCallRecord;

typedef struct {
 uint32_t abi, record_bytes, capacity, count, dropped, errors;
 uint32_t pending, completed, active, frame_known, frame, step_limit;
 uint32_t master_dispatches;
} NeptuneCallStatus;

static struct {
 NeptuneCallRecord records[NEPTUNE_TRACE_RECORDS];
 uint32_t count, dropped, errors, pending, completed, active;
 uint32_t frame_known, frame, requested, entry, return_pc, steps, saw_rts, saw_delay;
 uint32_t master_dispatches;
} neptune_call_trace;

static void neptune_call_error(void)
{
 neptune_call_trace.errors++;
 neptune_call_trace.active = 0;
}

/* Entries are deliberately limited to original helpers whose byte boundaries
 * and return-delay contracts have been inspected. This is master-interpreter
 * observation, not slave/JIT tracing.
 */
NEPTUNE_TRACE_EXPORT uint32_t neptune_call_begin(uint32_t entry, uint32_t pairs)
{
 if((entry != 0x0600B934 && entry != 0x0600A0EC) ||
    pairs == 0 || pairs > NEPTUNE_TRACE_RECORDS / 2 ||
    neptune_call_trace.active || setting_sh2_jit)
  return 0;
 memset(&neptune_call_trace, 0, sizeof(neptune_call_trace));
 neptune_call_trace.requested = pairs;
 neptune_call_trace.entry = entry;
 neptune_call_trace.active = 1;
 return 1;
}

NEPTUNE_TRACE_EXPORT uint32_t neptune_call_frame(uint32_t frame)
{
 if(!neptune_call_trace.active)
  return 1;
 if(neptune_call_trace.frame_known &&
    (neptune_call_trace.frame == UINT32_MAX || frame != neptune_call_trace.frame + 1))
 {
  neptune_call_error();
  return 0;
 }
 neptune_call_trace.frame_known = 1;
 neptune_call_trace.frame = frame;
 return 1;
}

NEPTUNE_TRACE_EXPORT void neptune_call_stop(void)
{
 neptune_call_trace.active = 0;
}

NEPTUNE_TRACE_EXPORT uint32_t neptune_call_status(NeptuneCallStatus* out, uint32_t bytes)
{
 if(!out || bytes != sizeof(*out))
  return 0;
 memset(out, 0, sizeof(*out));
 out->abi = NEPTUNE_TRACE_ABI;
 out->record_bytes = sizeof(NeptuneCallRecord);
 out->capacity = NEPTUNE_TRACE_RECORDS;
 out->count = neptune_call_trace.count;
 out->dropped = neptune_call_trace.dropped;
 out->errors = neptune_call_trace.errors;
 out->pending = neptune_call_trace.pending;
 out->completed = neptune_call_trace.completed;
 out->active = neptune_call_trace.active;
 out->frame_known = neptune_call_trace.frame_known;
 out->frame = neptune_call_trace.frame;
 out->step_limit = NEPTUNE_TRACE_STEP_LIMIT;
 out->master_dispatches = neptune_call_trace.master_dispatches;
 return 1;
}

/* Snapshot, not a destructive partial drain. A short destination is rejected. */
NEPTUNE_TRACE_EXPORT uint32_t neptune_call_records(NeptuneCallRecord* out, uint32_t capacity)
{
 if(!out || capacity < neptune_call_trace.count || capacity > NEPTUNE_TRACE_RECORDS)
  return UINT32_MAX;
 memcpy(out, neptune_call_trace.records, neptune_call_trace.count * sizeof(*out));
 return neptune_call_trace.count;
}

static void neptune_call_record(SH7095* z, uint32_t kind, uint32_t pc)
{
 NeptuneCallRecord* record;
 if(neptune_call_trace.count >= NEPTUNE_TRACE_RECORDS)
 {
  neptune_call_trace.dropped++;
  neptune_call_trace.active = 0;
  return;
 }
 record = &neptune_call_trace.records[neptune_call_trace.count];
 memset(record, 0, sizeof(*record));
 record->sequence = neptune_call_trace.count++;
 record->kind = kind;
 record->cpu = 0;
 record->frame = neptune_call_trace.frame;
 record->pc = pc;
 record->timestamp = z->timestamp;
 record->dispatch_steps = neptune_call_trace.steps;
 record->opcode = z->Pipe_ID & 0xFFFF;
 memcpy(record->r, z->R, sizeof(record->r));
 record->sr = z->SR;
 record->gbr = z->GBR;
 record->vbr = z->VBR;
 record->mach = z->MACH;
 record->macl = z->MACL;
 record->pr = z->PR;
}

/* Called before the pinned master's C0/C1 dispatch, after the timer update.
 * In the normal pipeline PC is four bytes ahead of Pipe_ID. A delay slot uses
 * the branch target's PC instead, so NEVER label that slot with PC-4.
 * Exception pseudo-ops are not instructions and cannot establish a boundary.
 * The old PC_ID/PC_IF fields are not maintained by this source revision.
 */
static INLINE void neptune_call_step(SH7095* z)
{
 uint32_t operation, pc;
 if(!neptune_call_trace.active)
  return;
 if(neptune_call_trace.master_dispatches == UINT32_MAX)
 {
  neptune_call_error();
  return;
 }
 neptune_call_trace.master_dispatches++;
 if(!neptune_call_trace.frame_known || setting_sh2_jit)
 {
  neptune_call_error();
  return;
 }
 operation = z->Pipe_ID >> 24;
 if(operation == 0xFF)
  return;
 if(operation & 0x80)
 {
  if(neptune_call_trace.pending)
  {
   if(++neptune_call_trace.steps > NEPTUNE_TRACE_STEP_LIMIT)
    neptune_call_error();
   else if(neptune_call_trace.saw_rts)
   {
    uint32_t expected_delay = neptune_call_trace.entry == 0x0600B934 ? 0x4F16 : 0x0009;
    if((z->Pipe_ID & 0xFFFF) != expected_delay ||
       z->PC != neptune_call_trace.return_pc + 2)
     neptune_call_error();
    else
     neptune_call_trace.saw_delay = 1;
   }
  }
  return;
 }
 pc = z->PC - 4;
 if(neptune_call_trace.pending && pc == neptune_call_trace.return_pc)
 {
  if(!neptune_call_trace.saw_rts || !neptune_call_trace.saw_delay)
  {
   neptune_call_error();
   return;
  }
  neptune_call_record(z, 2, pc);
  neptune_call_trace.pending = 0;
  if(++neptune_call_trace.completed >= neptune_call_trace.requested)
   neptune_call_trace.active = 0;
  return;
 }
 if(neptune_call_trace.pending && ++neptune_call_trace.steps > NEPTUNE_TRACE_STEP_LIMIT)
 {
  neptune_call_error();
  return;
 }
 if(pc == neptune_call_trace.entry)
 {
  uint32_t expected_entry = neptune_call_trace.entry == 0x0600B934 ? 0x4F12 : 0x4F22;
  if(neptune_call_trace.pending || (z->Pipe_ID & 0xFFFF) != expected_entry ||
     (z->PR & 1) || z->PR == pc)
  {
   neptune_call_error();
   return;
  }
  neptune_call_trace.pending = 1;
  neptune_call_trace.return_pc = z->PR;
  neptune_call_trace.saw_rts = neptune_call_trace.saw_delay = 0;
  neptune_call_trace.steps = 1;
  neptune_call_record(z, 1, pc);
 }
 else if(neptune_call_trace.pending &&
         pc == (neptune_call_trace.entry == 0x0600B934 ? 0x0600B94C : 0x0600A10A))
 {
  if((z->Pipe_ID & 0xFFFF) != 0x000B || z->PR != neptune_call_trace.return_pc)
   neptune_call_error();
  else
   neptune_call_trace.saw_rts = 1;
 }
}
#endif
