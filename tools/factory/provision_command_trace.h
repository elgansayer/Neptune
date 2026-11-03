/* SPDX-License-Identifier: GPL-2.0-or-later
 * Bounded value-only command/device observations for the matched SH-2 core.
 */
#ifndef NEPTUNE_COMMAND_TRACE_H
#define NEPTUNE_COMMAND_TRACE_H
#include <stdint.h>
#include <string.h>
#if defined(__GNUC__)
#define NEPTUNE_COMMAND_EXPORT __attribute__((visibility("default")))
#else
#define NEPTUNE_COMMAND_EXPORT
#endif
enum { NEPTUNE_COMMAND_ABI=1, NEPTUNE_COMMAND_CAPACITY=128,
       NEPTUNE_COMMAND_STEPS=4194304, NEPTUNE_COMMAND_FRAMES=120,
       NEPTUNE_COMMAND_WITNESS=424 };
enum { COMMAND_ROOT=1, COMMAND_DEVICE_READ=2, COMMAND_DEVICE_WRITE=3,
       COMMAND_SERVICE=4, COMMAND_ROOT_RTS=5, COMMAND_ROOT_DELAY=6,
       COMMAND_ROOT_RETURN=7,COMMAND_SOURCE_CALL=8,COMMAND_SOURCE_DELAY=9 };
enum { COMMAND_BAD_FRAME=1, COMMAND_BAD_PIPELINE=2, COMMAND_BAD_ADDRESS=3,
       COMMAND_BUDGET=4, COMMAND_OVERFLOW=5, COMMAND_SOURCE_CHANGED=6,
       COMMAND_COUNTER=7, COMMAND_UNFINISHED=8 };
typedef struct {
 uint32_t sequence,kind,profile,frame,pc,opcode,pipe_op,steps,transfer_address,transfer_value;
 int32_t timestamp;
 uint32_t r[16],sr,gbr,vbr,mach,macl,pr,stack_address,stack[12];
 uint32_t command_address,response_address,command_valid,response_valid,command[2],response[2];
} NeptuneCommandRecord;
typedef struct {
 uint32_t abi,record_bytes,capacity,count,dropped,errors,active,pending,completed,
  profile,frame_known,frame,step_limit,steps,master_hooks,frame_limit,witness_words,
  source_checks,last_error,last_pc,last_address,root_rts,root_delay,transfer_count;
} NeptuneCommandStatus;
static struct {
 NeptuneCommandRecord records[NEPTUNE_COMMAND_CAPACITY];
 uint16_t expected[NEPTUNE_COMMAND_WITNESS],mismatch[NEPTUNE_COMMAND_WITNESS];
 uint32_t count,dropped,errors,active,pending,completed,profile,frame_known,frame,
  steps,master_hooks,source_checks,last_error,last_pc,last_address,mismatch_known,
  entry_frame,root_return,root_sp,root_r14,root_rts,root_delay,transfer_count,
  current_pc,current_opcode,command_address,response_address,source_call,source_delay,source_pc,source_target,source_return;
} neptune_command_trace;
static void neptune_command_error(uint32_t e,uint32_t pc,uint32_t a)
{ neptune_command_trace.errors++;neptune_command_trace.last_error=e;neptune_command_trace.last_pc=pc;neptune_command_trace.last_address=a;neptune_command_trace.active=0; }
static uint32_t neptune_command_source(void)
{
 static const uint32_t starts[5]={0x06095904,0x060A4FAC,0x060AE676,0x060AE908,0x060AEA30};
 static const uint32_t counts[5]={256,118,23,23,4}; uint32_t n=0,ok=1;
 if(!WorkRAMH)return 0;
 for(uint32_t b=0;b<5;b++) for(uint32_t i=0;i<counts[b];i++) {
  uint16_t v=WorkRAMH[((starts[b]-0x06000000)>>1)+i];
  if(v!=neptune_command_trace.expected[n])ok=0;n++;
 }
 if(ok){neptune_command_trace.source_checks++;return 1;}
 if(!neptune_command_trace.mismatch_known) {
  n=0;for(uint32_t b=0;b<5;b++)for(uint32_t i=0;i<counts[b];i++)neptune_command_trace.mismatch[n++]=WorkRAMH[((starts[b]-0x06000000)>>1)+i];
  neptune_command_trace.mismatch_known=1;
 }
 return 0;
}
static uint32_t neptune_command_ram(uint32_t a,uint32_t n)
{ return WorkRAMH&&!(a&3)&&n&&a>=0x06000000&&n<=0x100000&&a<=0x06100000-n; }
static uint32_t neptune_command_word(uint32_t a)
{ return ((uint32_t)WorkRAMH[(a-0x06000000)>>1]<<16)|WorkRAMH[((a-0x06000000)>>1)+1]; }
static uint32_t neptune_command_record(const SH7095* z,uint32_t kind,uint32_t pc,uint32_t a,uint32_t v)
{
 if(neptune_command_trace.count>=NEPTUNE_COMMAND_CAPACITY){neptune_command_trace.dropped++;neptune_command_error(COMMAND_OVERFLOW,pc,0);return 0;}
 if(!neptune_command_source()){neptune_command_error(COMMAND_SOURCE_CHANGED,pc,0);return 0;}
 if((z->R[15]&3)||z->R[15]<0x06000000||z->R[15]>0x06100000){neptune_command_error(COMMAND_BAD_ADDRESS,pc,z->R[15]);return 0;}
 NeptuneCommandRecord* r=&neptune_command_trace.records[neptune_command_trace.count];memset(r,0,sizeof(*r));
 r->sequence=neptune_command_trace.count;r->kind=kind;r->profile=neptune_command_trace.profile;
 r->frame=neptune_command_trace.frame;r->pc=pc;r->opcode=z->Pipe_ID&0xFFFF;r->pipe_op=z->Pipe_ID>>24;
 if(kind==COMMAND_DEVICE_READ||kind==COMMAND_DEVICE_WRITE){r->pc=neptune_command_trace.current_pc;r->opcode=neptune_command_trace.current_opcode;}
 r->steps=neptune_command_trace.steps;r->timestamp=z->timestamp;r->transfer_address=a;r->transfer_value=v;
 memcpy(r->r,z->R,sizeof(r->r));r->sr=z->SR;r->gbr=z->GBR;r->vbr=z->VBR;r->mach=z->MACH;r->macl=z->MACL;r->pr=z->PR;
 r->stack_address=z->R[15]>=0x06000030?z->R[15]-48:0x06000000;
 if(r->stack_address>0x060FFF80)r->stack_address=0x060FFF80;
 for(uint32_t i=0;i<12;i++)r->stack[i]=neptune_command_word(r->stack_address+4*i);
 if(pc==0x060A4FAC){neptune_command_trace.command_address=z->R[5];if(neptune_command_ram(z->R[5],8))neptune_command_trace.command_address=z->R[5];}
 if(pc==0x06095992){neptune_command_trace.command_address=z->R[5];neptune_command_trace.response_address=z->R[6];}
 r->command_address=neptune_command_trace.command_address;r->response_address=neptune_command_trace.response_address;
 r->command_valid=neptune_command_ram(r->command_address,8);r->response_valid=neptune_command_ram(r->response_address,8);
 if(r->command_valid){r->command[0]=neptune_command_word(r->command_address);r->command[1]=neptune_command_word(r->command_address+4);}
 if(r->response_valid){r->response[0]=neptune_command_word(r->response_address);r->response[1]=neptune_command_word(r->response_address+4);}
 neptune_command_trace.count++;return 1;
}
NEPTUNE_COMMAND_EXPORT uint32_t neptune_command_begin(uint32_t profile,const uint16_t* w,uint32_t n)
{ if(profile<1||profile>2||!w||n!=NEPTUNE_COMMAND_WITNESS||neptune_command_trace.active||setting_sh2_jit)return 0;
 memset(&neptune_command_trace,0,sizeof(neptune_command_trace));neptune_command_trace.profile=profile;memcpy(neptune_command_trace.expected,w,sizeof(neptune_command_trace.expected));neptune_command_trace.active=1;return 1; }
NEPTUNE_COMMAND_EXPORT uint32_t neptune_command_frame(uint32_t f)
{ if(!neptune_command_trace.active)return 1;if((neptune_command_trace.frame_known&&(neptune_command_trace.frame==UINT32_MAX||f!=neptune_command_trace.frame+1))||(neptune_command_trace.pending&&f-neptune_command_trace.entry_frame>=NEPTUNE_COMMAND_FRAMES)){neptune_command_error(COMMAND_BAD_FRAME,0,f);return 0;}neptune_command_trace.frame_known=1;neptune_command_trace.frame=f;return 1; }
NEPTUNE_COMMAND_EXPORT void neptune_command_stop(void){neptune_command_trace.active=0;}
NEPTUNE_COMMAND_EXPORT uint32_t neptune_command_status(NeptuneCommandStatus* o,uint32_t n)
{ if(!o||n!=sizeof(*o))return 0;memset(o,0,sizeof(*o));o->abi=NEPTUNE_COMMAND_ABI;o->record_bytes=sizeof(NeptuneCommandRecord);o->capacity=NEPTUNE_COMMAND_CAPACITY;o->count=neptune_command_trace.count;o->dropped=neptune_command_trace.dropped;o->errors=neptune_command_trace.errors;o->active=neptune_command_trace.active;o->pending=neptune_command_trace.pending;o->completed=neptune_command_trace.completed;o->profile=neptune_command_trace.profile;o->frame_known=neptune_command_trace.frame_known;o->frame=neptune_command_trace.frame;o->step_limit=NEPTUNE_COMMAND_STEPS;o->steps=neptune_command_trace.steps;o->master_hooks=neptune_command_trace.master_hooks;o->frame_limit=NEPTUNE_COMMAND_FRAMES;o->witness_words=NEPTUNE_COMMAND_WITNESS;o->source_checks=neptune_command_trace.source_checks;o->last_error=neptune_command_trace.last_error;o->last_pc=neptune_command_trace.last_pc;o->last_address=neptune_command_trace.last_address;o->root_rts=neptune_command_trace.root_rts;o->root_delay=neptune_command_trace.root_delay;o->transfer_count=neptune_command_trace.transfer_count;return 1; }
NEPTUNE_COMMAND_EXPORT uint32_t neptune_command_records(NeptuneCommandRecord* o,uint32_t n)
{ if(!o||n<neptune_command_trace.count||n>NEPTUNE_COMMAND_CAPACITY)return UINT32_MAX;memcpy(o,neptune_command_trace.records,neptune_command_trace.count*sizeof(*o));return neptune_command_trace.count; }
NEPTUNE_COMMAND_EXPORT uint32_t neptune_command_witness(uint16_t* o,uint32_t n,uint32_t m)
{ if(!o||n!=NEPTUNE_COMMAND_WITNESS||m>2||(m==1&&!neptune_command_trace.mismatch_known))return UINT32_MAX;
 if(m==2){if(neptune_command_source())memcpy(o,neptune_command_trace.expected,sizeof(neptune_command_trace.expected));else memcpy(o,neptune_command_trace.mismatch,sizeof(neptune_command_trace.mismatch));}
 else memcpy(o,m?neptune_command_trace.mismatch:neptune_command_trace.expected,sizeof(neptune_command_trace.expected));
 return NEPTUNE_COMMAND_WITNESS; }
static INLINE void neptune_command_step_at(const SH7095* z,uint32_t pipeline_pc)
{
 uint32_t pc=pipeline_pc,op=z->Pipe_ID>>24,code=z->Pipe_ID&0xFFFF;
 if(!neptune_command_trace.active)return;
 if(!neptune_command_trace.frame_known||setting_sh2_jit){neptune_command_error(COMMAND_BAD_FRAME,pc,0);return;}
 if(neptune_command_trace.master_hooks==UINT32_MAX){neptune_command_error(COMMAND_COUNTER,pc,0);return;}neptune_command_trace.master_hooks++;
 if(neptune_command_trace.pending&&++neptune_command_trace.steps>NEPTUNE_COMMAND_STEPS){neptune_command_error(COMMAND_BUDGET,pc,0);return;}
 if(op==0xFF)return;
 if(op&0x80){
  if(neptune_command_trace.source_call&&!neptune_command_trace.source_delay&&pipeline_pc==neptune_command_trace.source_target+2){
   neptune_command_record(z,COMMAND_SOURCE_DELAY,neptune_command_trace.source_pc+2,0,0);neptune_command_trace.source_delay=1;
  }
  if(neptune_command_trace.pending&&neptune_command_trace.root_rts&&!neptune_command_trace.root_delay&&code==0x0009){
   neptune_command_record(z,COMMAND_ROOT_DELAY,0x060A4FBC,0,0);neptune_command_trace.root_delay=1;
  }
  return;
 }
 pc-=4;neptune_command_trace.current_pc=pc;neptune_command_trace.current_opcode=code;
 uint32_t callpc=neptune_command_trace.profile==1?0x060AE694:0x060AE92A;
 if(!neptune_command_trace.pending&&pc==callpc){
  if((code&0xF0FF)!=0x400B||z->R[(code>>8)&15]!=0x060A4FAC){neptune_command_error(COMMAND_BAD_PIPELINE,pc,code);return;}
  neptune_command_trace.source_call=1;neptune_command_trace.source_delay=0;neptune_command_trace.source_pc=pc;
  neptune_command_trace.source_target=z->R[(code>>8)&15];neptune_command_trace.source_return=pc+4;
  neptune_command_record(z,COMMAND_SOURCE_CALL,pc,0,0);return;
 }
 if(!neptune_command_trace.pending){uint32_t entry=0x060A4FAC; if(pc==entry&&neptune_command_trace.source_call&&neptune_command_trace.source_delay&&neptune_command_trace.source_target==entry&&z->PR==neptune_command_trace.source_return&&neptune_command_source()){neptune_command_trace.pending=1;neptune_command_trace.steps=1;neptune_command_trace.entry_frame=neptune_command_trace.frame;neptune_command_trace.root_return=neptune_command_trace.profile==1?0x060AE698:0x060AE92E;neptune_command_trace.root_sp=z->R[15];neptune_command_trace.root_r14=z->R[14];neptune_command_record(z,COMMAND_ROOT,pc,0,0);}return;}
 if(pc==0x06095992){neptune_command_record(z,COMMAND_SERVICE,pc,0,0);return;}
 if(pc==0x060959CA||pc==0x060959AE||pc==0x060959C8||pc==0x06095A82){neptune_command_record(z,COMMAND_SERVICE,pc,0,0);return;}
 if(pc==0x060A4FBA&&code==0x000B&&!neptune_command_trace.root_rts){neptune_command_trace.root_rts=pc;neptune_command_record(z,COMMAND_ROOT_RTS,pc,0,0);return;}
 if(pc==neptune_command_trace.root_return&&neptune_command_trace.root_rts&&neptune_command_trace.root_delay&&z->R[15]==neptune_command_trace.root_sp&&z->R[14]==neptune_command_trace.root_r14&&z->PR==neptune_command_trace.root_return){neptune_command_record(z,COMMAND_ROOT_RETURN,pc,0,0);neptune_command_trace.pending=0;neptune_command_trace.completed=1;neptune_command_trace.active=0;}
}
static INLINE void neptune_command_step(const SH7095* z){neptune_command_step_at(z,z->PC);}
static INLINE void neptune_command_fused_nop(const SH7095* z){if(neptune_command_trace.active)neptune_command_step_at(z,z->PC+2);}
static INLINE void neptune_command_read(const SH7095* z,uint32_t a,uint16_t v)
{ if(!neptune_command_trace.active||a!=0x25890008&&a!=0x2589000C&&a!=0x25890018&&a!=0x2589001C&&a!=0x25890020&&a!=0x25890024)return;if(neptune_command_trace.transfer_count==UINT32_MAX){neptune_command_error(COMMAND_COUNTER,z->PC,a);return;}neptune_command_trace.transfer_count++;neptune_command_record(z,COMMAND_DEVICE_READ,neptune_command_trace.current_pc,a,v); }
static INLINE void neptune_command_write(const SH7095* z,uint32_t a,uint16_t v)
{ if(!neptune_command_trace.active||a!=0x25890008&&a!=0x2589000C&&a!=0x25890018&&a!=0x2589001C&&a!=0x25890020&&a!=0x25890024)return;if(neptune_command_trace.transfer_count==UINT32_MAX){neptune_command_error(COMMAND_COUNTER,z->PC,a);return;}neptune_command_trace.transfer_count++;neptune_command_record(z,COMMAND_DEVICE_WRITE,neptune_command_trace.current_pc,a,v); }
#endif
