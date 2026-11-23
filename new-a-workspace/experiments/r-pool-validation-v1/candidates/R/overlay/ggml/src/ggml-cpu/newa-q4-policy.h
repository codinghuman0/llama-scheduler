// SPDX-License-Identifier: MIT
#pragma once
#include <atomic>
#include <cstdlib>
#include <cstdio>
#include <cstring>
#include <omp.h>
#include "newa-q4-tile32.h"
#include "newa-q4-decode-exact.h"

extern "C" uint32_t ggml_backend_cpu_newa_phase_current(void);
static std::atomic<uint64_t> newa_q4_calls[4];
static bool newa_q4_phase_batch;

static void newa_q4_report(void) {
    std::fprintf(stderr,"NEWA_Q4_TILE32 stats worker0_calls=%llu/%llu/%llu/%llu\n",
        (unsigned long long)newa_q4_calls[0].load(),(unsigned long long)newa_q4_calls[1].load(),
        (unsigned long long)newa_q4_calls[2].load(),(unsigned long long)newa_q4_calls[3].load());
}

static bool newa_q4_enabled(void) {
    static const bool enabled=[] {
        const char * mode=std::getenv("GGML_NEWA_Q4_TILE32");
        GGML_ASSERT(!mode || std::strcmp(mode,"off")==0 || std::strcmp(mode,"prefill")==0 || std::strcmp(mode,"phase_batch")==0);
        newa_q4_phase_batch=mode && std::strcmp(mode,"phase_batch")==0;
        const bool on=newa_q4_phase_batch || (mode && std::strcmp(mode,"prefill")==0);
        if (newa_q4_phase_batch) {
            std::fprintf(stderr,"NEWA_Q4_TILE32 mode=phase_batch prefill_reference=1 batch_tokens_min=4 batch_tokens_max=12 exact=1 prefill_only=0\n");
        } else {
            std::fprintf(stderr,"NEWA_Q4_TILE32 mode=%s tokens=32 prefill_only=1\n",on?"prefill":"off");
        }
        GGML_ASSERT(std::atexit(newa_q4_report)==0);
        return on;
    }();
    return enabled;
}

static bool newa_q4_try(int n,float * s,size_t bs,const void * vx,const void * vy,int nr,int nc) {
    if (!newa_q4_enabled()) return false;
    const uint32_t phase=ggml_backend_cpu_newa_phase_current();
    if (phase==1) {
        return false; // Keep semantic Prefill on the reference body.
    } else if (!newa_q4_phase_batch || (phase!=2 && phase!=3) || nr<4 || nr>=16) {
        return false;
    }
    if (phase==1) newa_q4_candidate(n,s,bs,vx,vy,nr,nc);
    else newa_q4_decode_exact(n,s,bs,vx,vy,nr,nc);
    if (omp_get_thread_num()==0) newa_q4_calls[phase].fetch_add(1,std::memory_order_relaxed);
    return true;
}
