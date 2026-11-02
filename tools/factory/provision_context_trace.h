/* SPDX-License-Identifier: GPL-2.0-or-later
 * Bounded master-interpreter context observations. No emulated state is written.
 * This component follows the matched core's licence; root Apache is unchanged.
 */
#ifndef NEPTUNE_CONTEXT_TRACE_H
#define NEPTUNE_CONTEXT_TRACE_H
#include <stdint.h>
#include <string.h>
#if defined(__GNUC__)
#define NEPTUNE_CTX_EXPORT __attribute__((visibility("default")))
#else
#define NEPTUNE_CTX_EXPORT
#endif

enum { NEPTUNE_CTX_ABI=1, NEPTUNE_CTX_CAPACITY=128, NEPTUNE_CTX_STEPS=4096,
       NEPTUNE_CTX_WITNESS=339, NEPTUNE_CTX_PAIRS=16 };
enum { CTX_ENTRY=1, CTX_SAVE=2, CTX_SAVED=3, CTX_RESTORE=4, CTX_TRANSFER=5 };
enum { CTX_BAD_FRAME=1, CTX_BAD_PIPELINE=2, CTX_BAD_ADDRESS=3, CTX_BUDGET=4,
       CTX_OVERFLOW=5, CTX_SOURCE_CHANGED=6, CTX_COUNTER=7 };
typedef struct {
 uint32_t sequence, kind, profile, cpu, frame, pc;
 int32_t timestamp;
 uint32_t dispatch_steps, opcode, r[16], sr, gbr, vbr, mach, macl, pr;
 uint32_t context_address, stack_address;
 uint32_t header[14], root[12], table[396], context[12], stack[32];
} NeptuneContextRecord;
typedef struct {
 uint32_t abi, record_bytes, capacity, count, dropped, errors, active, pending,
          completed, requested, profile, frame_known, frame, step_limit, steps,
          master_dispatches, outside_inspected, source_mismatch_candidates,
          source_checks, last_error, last_pc, last_address;
} NeptuneContextStatus;
static struct {
 NeptuneContextRecord records[NEPTUNE_CTX_CAPACITY];
 uint16_t expected[NEPTUNE_CTX_WITNESS], mismatch[NEPTUNE_CTX_WITNESS];
 uint32_t count, dropped, errors, active, stage, completed, requested, profile,
          frame_known, frame, steps, master_dispatches, outside_inspected,
          source_mismatch_candidates, source_checks, last_error, last_pc,
          last_address, mismatch_known, save_context, save_return, target,
          save_call, save_delay, save_rts, save_restored, restore_call,
          restore_delay, restore_rts, restore_restored;
} neptune_context_trace;

static void neptune_context_error(uint32_t kind, uint32_t pc, uint32_t address)
{
 neptune_context_trace.errors++;
 neptune_context_trace.last_error=kind;
 neptune_context_trace.last_pc=pc;
 neptune_context_trace.last_address=address;
 neptune_context_trace.active=0;
}
static uint32_t neptune_context_ram(uint32_t address, uint32_t bytes)
{
 return WorkRAMH && !(address&3) && bytes && address>=0x06000000 &&
        bytes<=0x100000 && address<=0x06100000-bytes;
}
static uint32_t neptune_context_word(uint32_t address)
{
 const uint32_t i=(address-0x06000000)>>1;
 return ((uint32_t)WorkRAMH[i]<<16)|WorkRAMH[i+1];
}
static void neptune_context_words(uint32_t address, uint32_t* out, uint32_t count)
{
 for(uint32_t i=0;i<count;i++) out[i]=neptune_context_word(address+4*i);
}
static uint32_t neptune_context_address(uint32_t address)
{
 return address==0x060BD020 || (address>=0x060BC1B0 &&
        address<=0x060BC1B0+17*88 && (address-0x060BC1B0)%88==0);
}
static uint32_t neptune_context_source(uint32_t idle)
{
 static const uint32_t starts[3]={0x060061C4,0x06006B9C,0x06006E00};
 static const uint32_t counts[3]={35,278,26};
 uint16_t words[NEPTUNE_CTX_WITNESS];
 uint32_t n=0, equal=1;
 if(!WorkRAMH) return 0;
 for(uint32_t block=0;block<3;block++)
  for(uint32_t i=0;i<counts[block];i++)
  {
   words[n]=WorkRAMH[((starts[block]-0x06000000)>>1)+i];
   if(words[n]!=neptune_context_trace.expected[n]) equal=0;
   n++;
  }
 if(equal) { neptune_context_trace.source_checks++; return 1; }
 if(!neptune_context_trace.mismatch_known)
 {
  memcpy(neptune_context_trace.mismatch,words,sizeof(words));
  neptune_context_trace.mismatch_known=1;
 }
 if(idle)
 {
  if(neptune_context_trace.source_mismatch_candidates==UINT32_MAX)
   neptune_context_error(CTX_COUNTER,0,0);
  else neptune_context_trace.source_mismatch_candidates++;
 }
 return 0;
}
static uint32_t neptune_context_record(const SH7095* z,uint32_t kind,uint32_t pc,uint32_t context)
{
 static const uint32_t addresses[14]={0x06006018,0x0600601C,0x06006020,0x06006024,
  0x06006028,0x0600602C,0x06006038,0x06006040,0x06006044,0x060B2D2C,
  0x060B2D30,0x060B2D34,0x060B2D38,0x060BD050};
 NeptuneContextRecord* out;
 uint32_t stack;
 if(neptune_context_trace.count>=NEPTUNE_CTX_CAPACITY)
 {
  neptune_context_trace.dropped++;neptune_context_error(CTX_OVERFLOW,pc,0);return 0;
 }
 if(!neptune_context_address(context) || !neptune_context_ram(context,48))
 { neptune_context_error(CTX_BAD_ADDRESS,pc,context);return 0; }
 if((z->R[15]&3) || z->R[15]<0x06000000 || z->R[15]>0x06100000)
 { neptune_context_error(CTX_BAD_ADDRESS,pc,z->R[15]);return 0; }
 stack=z->R[15]>=0x06000040?z->R[15]-64:0x06000000;
 if(stack>0x060FFF80) stack=0x060FFF80;
 if(!neptune_context_source(0))
 { neptune_context_error(CTX_SOURCE_CHANGED,pc,0);return 0; }
 out=&neptune_context_trace.records[neptune_context_trace.count];memset(out,0,sizeof(*out));
 out->sequence=neptune_context_trace.count;out->kind=kind;out->profile=neptune_context_trace.profile;
 out->frame=neptune_context_trace.frame;out->pc=pc;out->timestamp=z->timestamp;
 out->dispatch_steps=neptune_context_trace.steps;out->opcode=z->Pipe_ID&0xFFFF;
 memcpy(out->r,z->R,sizeof(out->r));out->sr=z->SR;out->gbr=z->GBR;out->vbr=z->VBR;
 out->mach=z->MACH;out->macl=z->MACL;out->pr=z->PR;out->context_address=context;out->stack_address=stack;
 for(uint32_t i=0;i<14;i++) out->header[i]=neptune_context_word(addresses[i]);
 neptune_context_words(0x060BD020,out->root,12);neptune_context_words(0x060BC190,out->table,396);
 neptune_context_words(context,out->context,12);neptune_context_words(stack,out->stack,32);
 neptune_context_trace.count++;return 1;
}

NEPTUNE_CTX_EXPORT uint32_t neptune_context_begin(uint32_t profile,uint32_t pairs,
                                                const uint16_t* witness,uint32_t words)
{
 if(profile<1 || profile>3 || !pairs || pairs>NEPTUNE_CTX_PAIRS || !witness ||
    words!=NEPTUNE_CTX_WITNESS || neptune_context_trace.active || setting_sh2_jit) return 0;
 memset(&neptune_context_trace,0,sizeof(neptune_context_trace));
 neptune_context_trace.profile=profile;neptune_context_trace.requested=pairs;
 memcpy(neptune_context_trace.expected,witness,sizeof(neptune_context_trace.expected));
 neptune_context_trace.active=1;return 1;
}
NEPTUNE_CTX_EXPORT uint32_t neptune_context_frame(uint32_t frame)
{
 if(!neptune_context_trace.active) return 1;
 if(neptune_context_trace.frame_known && (neptune_context_trace.frame==UINT32_MAX ||
    frame!=neptune_context_trace.frame+1)) { neptune_context_error(CTX_BAD_FRAME,0,0);return 0; }
 neptune_context_trace.frame_known=1;neptune_context_trace.frame=frame;return 1;
}
NEPTUNE_CTX_EXPORT void neptune_context_stop(void) { neptune_context_trace.active=0; }
NEPTUNE_CTX_EXPORT uint32_t neptune_context_status(NeptuneContextStatus* out,uint32_t bytes)
{
 if(!out || bytes!=sizeof(*out)) return 0;
 memset(out,0,sizeof(*out));out->abi=NEPTUNE_CTX_ABI;out->record_bytes=sizeof(NeptuneContextRecord);
 out->capacity=NEPTUNE_CTX_CAPACITY;out->step_limit=NEPTUNE_CTX_STEPS;
#define CTX_STATUS(name) out->name=neptune_context_trace.name
 CTX_STATUS(count);CTX_STATUS(dropped);CTX_STATUS(errors);CTX_STATUS(active);
 out->pending=neptune_context_trace.stage;CTX_STATUS(completed);CTX_STATUS(requested);CTX_STATUS(profile);
 CTX_STATUS(frame_known);CTX_STATUS(frame);CTX_STATUS(steps);CTX_STATUS(master_dispatches);
 CTX_STATUS(outside_inspected);CTX_STATUS(source_mismatch_candidates);CTX_STATUS(source_checks);
 CTX_STATUS(last_error);CTX_STATUS(last_pc);CTX_STATUS(last_address);
#undef CTX_STATUS
 return 1;
}
NEPTUNE_CTX_EXPORT uint32_t neptune_context_records(NeptuneContextRecord* out,uint32_t capacity)
{
 if(!out || capacity<neptune_context_trace.count || capacity>NEPTUNE_CTX_CAPACITY) return UINT32_MAX;
 memcpy(out,neptune_context_trace.records,neptune_context_trace.count*sizeof(*out));return neptune_context_trace.count;
}
NEPTUNE_CTX_EXPORT uint32_t neptune_context_witness(uint16_t* out,uint32_t capacity,uint32_t mismatch)
{
 if(!out || capacity!=NEPTUNE_CTX_WITNESS || mismatch>1 ||
    (mismatch && !neptune_context_trace.mismatch_known)) return UINT32_MAX;
 memcpy(out,mismatch?neptune_context_trace.mismatch:neptune_context_trace.expected,
        sizeof(neptune_context_trace.expected));return NEPTUNE_CTX_WITNESS;
}

/* Normal pipeline PC is four bytes ahead. Delay PCs are branch-target based:
 * recognize only the inspected opcode/target relationship, never PC-4. */
static INLINE void neptune_context_step(const SH7095* z)
{
 uint32_t op,pc,code,profile,context,entry;
 if(!neptune_context_trace.active) return;
 if(!neptune_context_trace.frame_known || setting_sh2_jit)
 { neptune_context_error(CTX_BAD_FRAME,0,0);return; }
 if(neptune_context_trace.master_dispatches==UINT32_MAX)
 { neptune_context_error(CTX_COUNTER,0,0);return; }
 neptune_context_trace.master_dispatches++;
 op=z->Pipe_ID>>24;code=z->Pipe_ID&0xFFFF;profile=neptune_context_trace.profile;
 if(op==0xFF)
 {
  if(neptune_context_trace.stage) neptune_context_trace.outside_inspected++;
  return;
 }
 if(neptune_context_trace.stage && ++neptune_context_trace.steps>NEPTUNE_CTX_STEPS)
 { neptune_context_error(CTX_BUDGET,0,0);return; }
 if(op&0x80)
 {
  if(neptune_context_trace.stage==1 && neptune_context_trace.save_call && z->PC==0x060061C6 &&
     code==(profile==1?0x0009U:0x7420U)) neptune_context_trace.save_delay=1;
  if(neptune_context_trace.stage==2 && neptune_context_trace.save_rts && code==0xE000 &&
     z->PC==neptune_context_trace.save_return+2) neptune_context_trace.save_restored=1;
  if(neptune_context_trace.stage==3 && neptune_context_trace.restore_call && z->PC==0x060061E8 &&
     code==(profile==3?0x0009U:0x6EF6U)) neptune_context_trace.restore_delay=1;
  if(neptune_context_trace.stage==4 && neptune_context_trace.restore_rts && code==0x6053 &&
     z->PC==neptune_context_trace.target+2) neptune_context_trace.restore_restored=1;
  return;
 }
 pc=z->PC-4;
 if(!neptune_context_trace.stage)
 {
  entry=profile==1?0x06006BE4:(profile==2?0x06006C00:0x06006D36);
  if(pc!=entry) return;
  if(!neptune_context_source(1)) return;
  if(code!=(profile==1?0x2FE6U:(profile==2?0xD084U:0x0022U)))
  { neptune_context_error(CTX_BAD_PIPELINE,pc,0);return; }
  context=0x060BD020;
  if(profile==3)
  {
   context=neptune_context_word(0x06006020+4*((z->VBR>>10)&1));
   if(context>UINT32_MAX-32) { neptune_context_error(CTX_BAD_ADDRESS,pc,context);return; }
   context+=32;
  }
  neptune_context_trace.steps=1;neptune_context_trace.stage=profile==2?3:1;
  neptune_context_trace.save_call=neptune_context_trace.save_delay=neptune_context_trace.save_rts=0;
  neptune_context_trace.save_restored=neptune_context_trace.restore_call=neptune_context_trace.restore_delay=0;
  neptune_context_trace.restore_rts=neptune_context_trace.restore_restored=0;
  neptune_context_record(z,CTX_ENTRY,pc,context);return;
 }
 if(neptune_context_trace.stage==4 && pc==neptune_context_trace.target)
 {
  if(!neptune_context_trace.restore_rts || !neptune_context_trace.restore_restored)
  { neptune_context_error(CTX_BAD_PIPELINE,pc,0);return; }
  if(!neptune_context_record(z,CTX_TRANSFER,pc,neptune_context_trace.save_context)) return;
  neptune_context_trace.stage=0;
  if(++neptune_context_trace.completed>=neptune_context_trace.requested) neptune_context_trace.active=0;
  return;
 }
 if(!((pc>=0x060061C4 && pc<0x0600620A) || (pc>=0x06006B9C && pc<0x06006DC8)))
  neptune_context_trace.outside_inspected++;
 if(neptune_context_trace.stage==1 && pc==(profile==1?0x06006BFCU:0x06006D82U) && code==0x430B)
  neptune_context_trace.save_call=1;
 if(neptune_context_trace.stage==1 && pc==0x060061C4)
 {
  context=z->R[4];
  if(!neptune_context_trace.save_call || !neptune_context_trace.save_delay || code!=0x1480 ||
     z->PR!=(profile==1?0x06006C00U:0x06006D86U) || (profile==1 && context!=0x060BD020) ||
     (profile==3 && context==0x060BD020))
  { neptune_context_error(CTX_BAD_PIPELINE,pc,context);return; }
  neptune_context_trace.save_context=context;neptune_context_trace.save_return=z->PR;
  if(neptune_context_record(z,CTX_SAVE,pc,context)) neptune_context_trace.stage=2;
  return;
 }
 if(neptune_context_trace.stage==2 && pc==0x060061E2 && code==0x000B) neptune_context_trace.save_rts=1;
 if(neptune_context_trace.stage==2 && pc==neptune_context_trace.save_return)
 {
  if(!neptune_context_trace.save_rts || !neptune_context_trace.save_restored)
  { neptune_context_error(CTX_BAD_PIPELINE,pc,0);return; }
  if(neptune_context_record(z,CTX_SAVED,pc,neptune_context_trace.save_context)) neptune_context_trace.stage=3;
  return;
 }
 if(neptune_context_trace.stage==3 && pc==(profile==3?0x06006D90U:0x06006D32U) &&
    code==(profile==3?0x430BU:0x412BU)) neptune_context_trace.restore_call=1;
 if(neptune_context_trace.stage==3 && pc==0x060061E6)
 {
  context=z->R[4];
  if(!neptune_context_trace.restore_call || !neptune_context_trace.restore_delay || code!=0x5841 ||
     (profile==3 && context!=0x060BD020) || (profile!=3 && context==0x060BD020))
  { neptune_context_error(CTX_BAD_PIPELINE,pc,context);return; }
  if(!neptune_context_record(z,CTX_RESTORE,pc,context)) return;
  neptune_context_trace.save_context=context;
  neptune_context_trace.target=neptune_context_trace.records[neptune_context_trace.count-1].context[9];
  if(neptune_context_trace.target&1) { neptune_context_error(CTX_BAD_ADDRESS,pc,neptune_context_trace.target);return; }
  neptune_context_trace.stage=4;return;
 }
 if(neptune_context_trace.stage==4 && pc==0x06006206 && code==0x000B) neptune_context_trace.restore_rts=1;
}
#endif
