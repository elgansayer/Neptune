/* SPDX-License-Identifier: GPL-2.0-or-later
 * Value-only first-task/library observations in the matched master interpreter.
 * Follows the core's licence; Neptune's root Apache licence is unchanged.
 */
#ifndef NEPTUNE_INIT_TRACE_H
#define NEPTUNE_INIT_TRACE_H
#include <stdint.h>
#include <string.h>
#if defined(__GNUC__)
#define NEPTUNE_INIT_EXPORT __attribute__((visibility("default")))
#else
#define NEPTUNE_INIT_EXPORT
#endif
enum { NEPTUNE_INIT_ABI=1, NEPTUNE_INIT_CAPACITY=128, NEPTUNE_INIT_DEPTH=16,
       NEPTUNE_INIT_STEPS=4194304, NEPTUNE_INIT_FRAMES=120, NEPTUNE_INIT_WITNESS=2572 };
enum { INIT_ROOT_ENTRY=1, INIT_CALL=2, INIT_DELAY=3, INIT_CALLEE=4,
       INIT_CALL_RETURN=5, INIT_TAIL=6, INIT_TAIL_TARGET=7,
       INIT_ROOT_RTS=8, INIT_ROOT_DELAY=9, INIT_ROOT_RETURN=10 };
enum { INIT_BAD_FRAME=1, INIT_BAD_PIPELINE=2, INIT_BAD_ADDRESS=3, INIT_BUDGET=4,
       INIT_OVERFLOW=5, INIT_SOURCE_CHANGED=6, INIT_COUNTER=7, INIT_BAD_DEPTH=8 };
typedef struct {
 uint32_t sequence, kind, profile, frame, pc, opcode, pipe_op, edge, call_pc,
          target, return_pc, depth;
 int32_t timestamp;
 uint32_t steps, r[16], sr, gbr, vbr, mach, macl, pr,
          stack_address, library_address, library_valid;
 uint32_t globals[28], descriptor[3], result_handle, vectors[3], error_word,
          status_word, library[64], tables[10], slots[24], stack[32];
} NeptuneInitRecord;
typedef struct {
 uint32_t abi, record_bytes, capacity, count, dropped, errors, active, pending,
          completed, requested, profile, frame_known, frame, step_limit, steps,
          master_dispatches, source_mismatch_candidates, source_checks,
          last_error, last_pc, last_address, fused_nops, depth, frame_limit,
          depth_limit, witness_words, exceptional_dispatches;
} NeptuneInitStatus;
typedef struct { uint32_t edge, pc, target, returned, sp; } NeptuneInitCall;
static struct {
 NeptuneInitRecord records[NEPTUNE_INIT_CAPACITY];
 uint16_t expected[NEPTUNE_INIT_WITNESS], mismatch[NEPTUNE_INIT_WITNESS];
 NeptuneInitCall calls[NEPTUNE_INIT_DEPTH], branch;
 uint32_t count, dropped, errors, active, pending, completed, requested, profile,
          frame_known, frame, steps, master_dispatches, source_mismatch_candidates,
          source_checks, last_error, last_pc, last_address, fused_nops, depth,
          mismatch_known, entry_frame, root_return, root_sp, root_r14,
          branch_phase, branch_tail, branch_delay, next_edge, root_rts,
          root_delay, exceptional_dispatches;
} neptune_init_trace;

static void neptune_init_error(uint32_t error,uint32_t pc,uint32_t address)
{
 neptune_init_trace.errors++;neptune_init_trace.last_error=error;
 neptune_init_trace.last_pc=pc;neptune_init_trace.last_address=address;
 neptune_init_trace.active=0;
}
static uint32_t neptune_init_ram(uint32_t address,uint32_t bytes)
{
 return WorkRAMH && !(address&3) && bytes && bytes<=0x100000 &&
        address>=0x06000000 && address<=0x06100000-bytes;
}
static uint32_t neptune_init_word(uint32_t address)
{
 uint32_t i=(address-0x06000000)>>1;
 return ((uint32_t)WorkRAMH[i]<<16)|WorkRAMH[i+1];
}
static void neptune_init_words(uint32_t address,uint32_t* out,uint32_t count)
{
 for(uint32_t i=0;i<count;i++) out[i]=neptune_init_word(address+4*i);
}
static uint32_t neptune_init_source(uint32_t idle)
{
 static const uint32_t starts[5]={0x0600623A,0x060089AC,0x06008BF0,0x06095B04,0x060A6790};
 static const uint32_t counts[5]={3,95,32,2296,146};
 uint16_t words[NEPTUNE_INIT_WITNESS];uint32_t n=0,equal=1;
 if(!WorkRAMH) return 0;
 for(uint32_t block=0;block<5;block++) for(uint32_t i=0;i<counts[block];i++)
 {
  words[n]=WorkRAMH[((starts[block]-0x06000000)>>1)+i];
  if(words[n]!=neptune_init_trace.expected[n]) equal=0;
  n++;
 }
 if(equal) {neptune_init_trace.source_checks++;return 1;}
 if(!neptune_init_trace.mismatch_known)
 {
  memcpy(neptune_init_trace.mismatch,words,sizeof(words));neptune_init_trace.mismatch_known=1;
 }
 if(idle)
 {
  if(neptune_init_trace.source_mismatch_candidates==UINT32_MAX)
   neptune_init_error(INIT_COUNTER,0,0);
  else neptune_init_trace.source_mismatch_candidates++;
 }
 return 0;
}
static uint32_t neptune_init_record(const SH7095* z,uint32_t kind,uint32_t pc,
                                    const NeptuneInitCall* edge)
{
 NeptuneInitRecord* out;uint32_t stack,library;
 if(neptune_init_trace.count>=NEPTUNE_INIT_CAPACITY)
 {neptune_init_trace.dropped++;neptune_init_error(INIT_OVERFLOW,pc,0);return 0;}
 if((z->R[15]&3) || z->R[15]<0x06000000 || z->R[15]>0x06100000)
 {neptune_init_error(INIT_BAD_ADDRESS,pc,z->R[15]);return 0;}
 if(!neptune_init_source(0)) {neptune_init_error(INIT_SOURCE_CHANGED,pc,0);return 0;}
 stack=z->R[15]>=0x06000040?z->R[15]-64:0x06000000;
 if(stack>0x060FFF80) stack=0x060FFF80;
 out=&neptune_init_trace.records[neptune_init_trace.count];memset(out,0,sizeof(*out));
 out->sequence=neptune_init_trace.count;out->kind=kind;out->profile=neptune_init_trace.profile;
 out->frame=neptune_init_trace.frame;out->pc=pc;out->opcode=z->Pipe_ID&0xFFFF;
 out->pipe_op=z->Pipe_ID>>24;out->timestamp=z->timestamp;out->steps=neptune_init_trace.steps;
 out->depth=neptune_init_trace.depth;
 if(edge) {out->edge=edge->edge;out->call_pc=edge->pc;out->target=edge->target;out->return_pc=edge->returned;}
 memcpy(out->r,z->R,sizeof(out->r));out->sr=z->SR;out->gbr=z->GBR;out->vbr=z->VBR;
 out->mach=z->MACH;out->macl=z->MACL;out->pr=z->PR;out->stack_address=stack;
 neptune_init_words(0x060BD8BC,out->globals,28);
 neptune_init_words(0x060BF00C,out->descriptor,3);out->result_handle=neptune_init_word(0x060BF498);
 neptune_init_words(0x06000340,out->vectors,3);
 out->error_word=neptune_init_word(0x060FA8C4);out->status_word=neptune_init_word(0x060FC080);
 library=neptune_init_word(0x060FA8BC);out->library_address=library;
 if(neptune_init_ram(library,0x1B7C))
 {
  out->library_valid=1;neptune_init_words(library,out->library,64);
  neptune_init_words(library+0x438,out->tables,10);
  for(uint32_t i=0;i<24;i++) out->slots[i]=neptune_init_word(library+0xC60+0xA8*i);
 }
 neptune_init_words(stack,out->stack,32);neptune_init_trace.count++;return 1;
}
NEPTUNE_INIT_EXPORT uint32_t neptune_init_begin(uint32_t profile,uint32_t roots,
                                               const uint16_t* witness,uint32_t words)
{
 if(profile<1 || profile>2 || roots!=1 || !witness || words!=NEPTUNE_INIT_WITNESS ||
    neptune_init_trace.active || setting_sh2_jit) return 0;
 memset(&neptune_init_trace,0,sizeof(neptune_init_trace));
 neptune_init_trace.profile=profile;neptune_init_trace.requested=roots;
 memcpy(neptune_init_trace.expected,witness,sizeof(neptune_init_trace.expected));
 neptune_init_trace.active=1;return 1;
}
NEPTUNE_INIT_EXPORT uint32_t neptune_init_frame(uint32_t frame)
{
 if(!neptune_init_trace.active) return 1;
 if((neptune_init_trace.frame_known && (neptune_init_trace.frame==UINT32_MAX || frame!=neptune_init_trace.frame+1)) ||
    (neptune_init_trace.pending && frame-neptune_init_trace.entry_frame>=NEPTUNE_INIT_FRAMES))
 {neptune_init_error(INIT_BAD_FRAME,0,0);return 0;}
 neptune_init_trace.frame_known=1;neptune_init_trace.frame=frame;return 1;
}
NEPTUNE_INIT_EXPORT void neptune_init_stop(void) {neptune_init_trace.active=0;}
NEPTUNE_INIT_EXPORT uint32_t neptune_init_status(NeptuneInitStatus* out,uint32_t bytes)
{
 if(!out || bytes!=sizeof(*out)) return 0;
 memset(out,0,sizeof(*out));out->abi=NEPTUNE_INIT_ABI;out->record_bytes=sizeof(NeptuneInitRecord);
 out->capacity=NEPTUNE_INIT_CAPACITY;out->step_limit=NEPTUNE_INIT_STEPS;
 out->frame_limit=NEPTUNE_INIT_FRAMES;out->depth_limit=NEPTUNE_INIT_DEPTH;out->witness_words=NEPTUNE_INIT_WITNESS;
#define INIT_STATUS(name) out->name=neptune_init_trace.name
 INIT_STATUS(count);INIT_STATUS(dropped);INIT_STATUS(errors);INIT_STATUS(active);INIT_STATUS(pending);
 INIT_STATUS(completed);INIT_STATUS(requested);INIT_STATUS(profile);INIT_STATUS(frame_known);INIT_STATUS(frame);
 INIT_STATUS(steps);INIT_STATUS(master_dispatches);INIT_STATUS(source_mismatch_candidates);INIT_STATUS(source_checks);
 INIT_STATUS(last_error);INIT_STATUS(last_pc);INIT_STATUS(last_address);INIT_STATUS(fused_nops);
 INIT_STATUS(depth);INIT_STATUS(exceptional_dispatches);
#undef INIT_STATUS
 return 1;
}
NEPTUNE_INIT_EXPORT uint32_t neptune_init_records(NeptuneInitRecord* out,uint32_t capacity)
{
 if(!out || capacity<neptune_init_trace.count || capacity>NEPTUNE_INIT_CAPACITY) return UINT32_MAX;
 memcpy(out,neptune_init_trace.records,neptune_init_trace.count*sizeof(*out));return neptune_init_trace.count;
}
NEPTUNE_INIT_EXPORT uint32_t neptune_init_witness(uint16_t* out,uint32_t capacity,uint32_t mismatch)
{
 if(!out || capacity!=NEPTUNE_INIT_WITNESS || mismatch>1 || (mismatch && !neptune_init_trace.mismatch_known)) return UINT32_MAX;
 memcpy(out,mismatch?neptune_init_trace.mismatch:neptune_init_trace.expected,sizeof(neptune_init_trace.expected));
 return NEPTUNE_INIT_WITNESS;
}
static uint32_t neptune_init_site(uint32_t pc)
{
 switch(pc) {
 case 0x060089F8:case 0x06008A14:case 0x06008A1E:case 0x06008A34:case 0x06008A4A:
 case 0x06095B5A:case 0x06095B66:case 0x06095B76:case 0x06095B9A:case 0x06095BB4:return 1;
 case 0x06095B96:case 0x06095BAE:return 2;
 default:return 0;
 }
}
static uint32_t neptune_init_root_rts(uint32_t pc)
{
 if(neptune_init_trace.profile==2) return pc==0x06095BCA || pc==0x06096CAC;
 return pc==0x06008A2C || pc==0x06008A44 || pc==0x06008A5C || pc==0x06008A66;
}
static INLINE void neptune_init_step_at(const SH7095* z,uint32_t pipeline_pc)
{
 uint32_t op,code,pc,entry,site,target;
 NeptuneInitCall* edge;
 if(!neptune_init_trace.active) return;
 if(!neptune_init_trace.frame_known || setting_sh2_jit) {neptune_init_error(INIT_BAD_FRAME,0,0);return;}
 if(neptune_init_trace.master_dispatches==UINT32_MAX) {neptune_init_error(INIT_COUNTER,0,0);return;}
 neptune_init_trace.master_dispatches++;op=z->Pipe_ID>>24;code=z->Pipe_ID&0xFFFF;
 if(op==0xFF)
 {
  if(neptune_init_trace.exceptional_dispatches==UINT32_MAX) neptune_init_error(INIT_COUNTER,0,0);
  else neptune_init_trace.exceptional_dispatches++;
  return;
 }
 if(neptune_init_trace.pending && ++neptune_init_trace.steps>NEPTUNE_INIT_STEPS)
 {neptune_init_error(INIT_BUDGET,0,0);return;}
 if(op&0x80)
 {
  if(neptune_init_trace.branch_phase==1 && pipeline_pc==neptune_init_trace.branch.target+2)
  {
   uint32_t slot=WorkRAMH[(neptune_init_trace.branch.pc+2-0x06000000)>>1];
   if(code!=slot) {neptune_init_error(INIT_BAD_PIPELINE,neptune_init_trace.branch.pc+2,code);return;}
   neptune_init_trace.branch_delay=1;
   neptune_init_record(z,INIT_DELAY,neptune_init_trace.branch.pc+2,&neptune_init_trace.branch);
  }
  if(neptune_init_trace.root_rts && pipeline_pc==neptune_init_trace.root_return+2)
  {
   if(code!=0x6EF6) {neptune_init_error(INIT_BAD_PIPELINE,neptune_init_trace.root_rts+2,code);return;}
   neptune_init_trace.root_delay=1;
   neptune_init_record(z,INIT_ROOT_DELAY,neptune_init_trace.root_rts+2,0);
  }
  return;
 }
 pc=pipeline_pc-4;
 if(!neptune_init_trace.pending)
 {
  entry=neptune_init_trace.profile==1?0x060089C8:0x06095B04;
  if(pc!=entry || !neptune_init_source(1)) return;
  if(code!=0x2FE6 || z->PR!=(neptune_init_trace.profile==1?0x06006240U:0x06008A18U))
  {neptune_init_error(INIT_BAD_PIPELINE,pc,z->PR);return;}
  neptune_init_trace.root_return=z->PR;neptune_init_trace.root_sp=z->R[15];neptune_init_trace.root_r14=z->R[14];
  neptune_init_trace.entry_frame=neptune_init_trace.frame;neptune_init_trace.steps=1;neptune_init_trace.pending=1;
  neptune_init_record(z,INIT_ROOT_ENTRY,pc,0);return;
 }
 if(neptune_init_trace.branch_phase==1 && pc==neptune_init_trace.branch.target)
 {
  if(!neptune_init_trace.branch_delay || z->PR!=neptune_init_trace.branch.returned)
  {neptune_init_error(INIT_BAD_PIPELINE,pc,z->PR);return;}
  neptune_init_record(z,neptune_init_trace.branch_tail?INIT_TAIL_TARGET:INIT_CALLEE,pc,&neptune_init_trace.branch);
  neptune_init_trace.branch_phase=0;
 }
 if(neptune_init_trace.depth)
 {
  edge=&neptune_init_trace.calls[neptune_init_trace.depth-1];
  if(pc==edge->returned)
  {
   if(neptune_init_trace.branch_phase || z->R[15]!=edge->sp || z->PR!=edge->returned)
   {neptune_init_error(INIT_BAD_PIPELINE,pc,z->R[15]);return;}
   neptune_init_record(z,INIT_CALL_RETURN,pc,edge);neptune_init_trace.depth--;
  }
 }
 if(pc==neptune_init_trace.root_return)
 {
  if(!neptune_init_trace.root_rts || !neptune_init_trace.root_delay || neptune_init_trace.depth || neptune_init_trace.branch_phase ||
     z->R[15]!=neptune_init_trace.root_sp || z->PR!=neptune_init_trace.root_return || z->R[14]!=neptune_init_trace.root_r14)
  {neptune_init_error(INIT_BAD_PIPELINE,pc,z->R[15]);return;}
  if(neptune_init_record(z,INIT_ROOT_RETURN,pc,0))
  {neptune_init_trace.pending=0;neptune_init_trace.completed=1;neptune_init_trace.active=0;}
  return;
 }
 if(neptune_init_root_rts(pc) && z->PR==neptune_init_trace.root_return && !neptune_init_trace.depth)
 {
  if(code!=0x000B || neptune_init_trace.root_rts) {neptune_init_error(INIT_BAD_PIPELINE,pc,code);return;}
  neptune_init_trace.root_rts=pc;neptune_init_record(z,INIT_ROOT_RTS,pc,0);return;
 }
 site=neptune_init_site(pc);
 if(!site) return;
 if(neptune_init_trace.branch_phase || neptune_init_trace.next_edge==UINT32_MAX)
 {neptune_init_error(INIT_BAD_PIPELINE,pc,0);return;}
 if(site==1 && code>>12==0xB)
 {
  int32_t disp=(int32_t)(code&0xFFF);if(disp&0x800) disp-=0x1000;
  target=pc+4+(uint32_t)(disp*2);
 }
 else if((site==1 && (code&0xF0FF)==0x400B) || (site==2 && (code&0xF0FF)==0x402B)) target=z->R[(code>>8)&15];
 else {neptune_init_error(INIT_BAD_PIPELINE,pc,code);return;}
 if(target&1) {neptune_init_error(INIT_BAD_ADDRESS,pc,target);return;}
 if(site==1 && neptune_init_trace.depth>=NEPTUNE_INIT_DEPTH) {neptune_init_error(INIT_BAD_DEPTH,pc,0);return;}
 edge=&neptune_init_trace.branch;edge->edge=++neptune_init_trace.next_edge;edge->pc=pc;
 edge->target=target;edge->returned=site==1?pc+4:z->PR;edge->sp=z->R[15];
 if(site==1) neptune_init_trace.calls[neptune_init_trace.depth++]=*edge;
 neptune_init_trace.branch_tail=site==2;neptune_init_trace.branch_phase=1;neptune_init_trace.branch_delay=0;
 neptune_init_record(z,site==1?INIT_CALL:INIT_TAIL,pc,edge);
}
static INLINE void neptune_init_step(const SH7095* z) {neptune_init_step_at(z,z->PC);}
static INLINE void neptune_init_fused_nop(const SH7095* z)
{
 if(!neptune_init_trace.active) return;
 if((z->Pipe_ID>>24)!=0xF5) {neptune_init_error(INIT_BAD_PIPELINE,z->PC,0);return;}
 if(neptune_init_trace.fused_nops==UINT32_MAX) {neptune_init_error(INIT_COUNTER,z->PC,0);return;}
 neptune_init_trace.fused_nops++;neptune_init_step_at(z,z->PC+2);
}
#endif
