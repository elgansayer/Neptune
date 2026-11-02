/* Synthetic libretro ABI fixture, Apache-2.0. No Saturn implementation/data. */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
typedef bool (*environment_t)(unsigned, void *);
static environment_t env;
static void (*video)(const void *, unsigned, unsigned, size_t);
static size_t (*audio)(const int16_t *, size_t);
static void (*audio_single)(int16_t, int16_t);
static int16_t (*input)(unsigned, unsigned, unsigned, unsigned);
static unsigned frame, mode;
struct variable { const char *key, *value; };
struct geometry { unsigned bw,bh,mw,mh; float aspect; };
struct av { struct geometry geometry; double fps, rate; };
void fixture_mode(unsigned value) { mode=value; }
unsigned retro_api_version(void) { return 1; }
void retro_set_environment(environment_t value) {
    env=value;
    struct variable options[]={{"fixture_option","Fixture; off|on"},{0,0}};
    env(16, options);
}
void retro_set_video_refresh(void (*value)(const void *,unsigned,unsigned,size_t)) { video=value; }
void retro_set_audio_sample(void (*value)(int16_t,int16_t)) { audio_single=value; }
void retro_set_audio_sample_batch(size_t (*value)(const int16_t *,size_t)) { audio=value; }
void retro_set_input_poll(void (*value)(void)) { (void)value; }
void retro_set_input_state(int16_t (*value)(unsigned,unsigned,unsigned,unsigned)) { input=value; }
void retro_init(void) { frame=0; }
void retro_deinit(void) {}
bool retro_load_game(const void *info) {
    (void)info;
    unsigned pixel=1; env(10,&pixel);
    struct variable option={"fixture_option",0}; env(15,&option);
    if (mode==14) audio_single(-1,1);
    return mode!=1;
}
void retro_unload_game(void) { if (mode==15) audio_single(-1,1); }
void retro_set_controller_port_device(unsigned port,unsigned device) { (void)port;(void)device; }
void retro_get_system_av_info(struct av *out) {
    *out=(struct av){{2,1,2,1,2.0f},59.5,44100.0};
    if (mode==16) out->rate=44100.5;
}
void retro_run(void) {
    int16_t a=input(0,1,0,256), b=input(1,1,0,256);
    uint32_t pixels[]={frame+(unsigned)a,frame+(unsigned)b};
    int16_t samples[]={a,b};
    if (mode!=2) video(pixels,2,1,8);
    if (mode==7) {
        audio_single(-32768,32767); audio_single(-1,1);
    } else if (mode==8) {
        int16_t mixed[]={1,-1,2,-2,3,-3};
        audio_single(-32768,32767);
        audio(mixed,frame%3+1);
        audio_single(5,-5);
    } else if (mode==9) {
        static int16_t large[65536*2];
        audio(large,65536); audio(samples,1);
    } else if (mode==10) {
        audio(0,1);
    } else if (mode==11) {
        struct av changed={{2,1,2,1,2.0f},59.5,48000.0};
        env(32,&changed); audio(samples,1);
    } else if (mode==12) {
        /* Deliberately no samples: a whole retained capture must fail. */
    } else if (mode==13 && frame%2) {
        audio(0,0);
    } else {
        audio(samples,1);
    }
    if (mode==3) {
        struct { void (*log)(int,const char *,...); } logger={0};
        if (env(27,&logger)) logger.log(3,"synthetic failure %u",frame);
    }
    if (mode==4) env(7,0);
    frame++;
}
size_t retro_serialize_size(void) { return sizeof(frame); }
bool retro_serialize(void *data,size_t size) {
    if (mode==5 || size!=sizeof(frame)) return false;
    memcpy(data,&frame,size); return true;
}
bool retro_unserialize(const void *data,size_t size) {
    if (mode==6 || size!=sizeof(frame)) return false;
    memcpy(&frame,data,size); return true;
}
