/* SPDX-License-Identifier: MIT */
#ifndef GGML_NEWA_BARRIER_H
#define GGML_NEWA_BARRIER_H

#include "newa-phase-policy.h"
#include <errno.h>
#include <limits.h>
#include <linux/futex.h>
#include <stdbool.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdlib.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

#define NEWA_BARRIER_MAX_THREADS 64
#define NEWA_BARRIER_SPINS 4096
#define NEWA_HINT_INTERVAL_NS UINT64_C(10000000)

enum newa_barrier_mode { NEWA_BARRIER_SPIN, NEWA_BARRIER_PARK, NEWA_BARRIER_HINT };

struct newa_barrier_worker {
    _Alignas(64) atomic_int arrived;
    atomic_uint tid;
};

struct newa_barrier_state {
    enum newa_barrier_mode mode;
    int n_threads;
    enum newa_phase_policy phase_policy;
    uint32_t phases_seen;
    _Alignas(64) atomic_ullong phase_waits[4];
    _Alignas(64) atomic_int sleepers;
    atomic_int hint_generation;
    atomic_uint_fast64_t last_hint_ns;
    atomic_ullong wait_calls;
    atomic_ullong wake_calls;
    atomic_ullong hints;
    atomic_ullong interrupted;
    atomic_ullong already_changed;
    struct newa_barrier_worker workers[NEWA_BARRIER_MAX_THREADS];
};

_Static_assert(sizeof(atomic_int)==4 && ATOMIC_INT_LOCK_FREE==2, "futex requires a lock-free 32-bit atomic");

void ggml_newa_barrier_wait_v1(uint32_t generation, uint64_t hint_ns, const uint32_t * tids, uint32_t count);

static inline void newa_barrier_init(struct newa_barrier_state * state, enum newa_barrier_mode mode, int n_threads) {
    if (n_threads<1 || (mode==NEWA_BARRIER_HINT && n_threads>NEWA_BARRIER_MAX_THREADS)) abort();
    state->mode=mode;
    state->n_threads=n_threads;
    state->phase_policy=NEWA_PHASE_ALL;
    state->phases_seen=0;
    for (int i=0;i<4;i++) atomic_init(&state->phase_waits[i],0);
    atomic_init(&state->sleepers,0);
    atomic_init(&state->hint_generation,-1);
    atomic_init(&state->last_hint_ns,0);
    atomic_init(&state->wait_calls,0);
    atomic_init(&state->wake_calls,0);
    atomic_init(&state->hints,0);
    atomic_init(&state->interrupted,0);
    atomic_init(&state->already_changed,0);
    for (int i=0;i<NEWA_BARRIER_MAX_THREADS;i++) {
        atomic_init(&state->workers[i].arrived,-1);
        atomic_init(&state->workers[i].tid,0);
    }
}

static inline void newa_barrier_register(struct newa_barrier_state * state, int worker, uint32_t tid) {
    if (state->mode==NEWA_BARRIER_HINT) {
        if (worker<0 || worker>=state->n_threads || !tid) abort();
        atomic_store_explicit(&state->workers[worker].tid,tid,memory_order_release);
    }
}

static inline void newa_barrier_arrive(struct newa_barrier_state * state, int worker, int generation) {
    if (state->mode==NEWA_BARRIER_HINT) {
        if (worker<0 || worker>=state->n_threads) abort();
        atomic_store_explicit(&state->workers[worker].arrived,generation,memory_order_release);
    }
}

static inline void newa_barrier_hint(struct newa_barrier_state * state, atomic_int * generation, int observed, int n_threads) {
    if (state->mode!=NEWA_BARRIER_HINT) return;
    if (n_threads<1 || n_threads>state->n_threads) abort();
    int previous=atomic_load_explicit(&state->hint_generation,memory_order_relaxed);
    uint32_t advance=(uint32_t)observed-(uint32_t)previous;
    if (!advance || advance>=UINT32_C(0x80000000) || atomic_load_explicit(generation,memory_order_seq_cst)!=observed ||
        !atomic_compare_exchange_strong_explicit(&state->hint_generation,&previous,observed,
                                                memory_order_relaxed,memory_order_relaxed)) return;
    struct timespec time;
    if (clock_gettime(CLOCK_MONOTONIC,&time)!=0) abort();
    uint64_t now=(uint64_t)time.tv_sec*UINT64_C(1000000000)+(uint64_t)time.tv_nsec;
    uint64_t last=atomic_load_explicit(&state->last_hint_ns,memory_order_relaxed);
    if (now<last || now-last<NEWA_HINT_INTERVAL_NS) return;
    uint32_t missing[NEWA_BARRIER_MAX_THREADS];
    uint32_t count=0;
    for (int i=0;i<n_threads;i++) {
        if (atomic_load_explicit(&state->workers[i].arrived,memory_order_acquire)!=observed) {
            uint32_t tid=atomic_load_explicit(&state->workers[i].tid,memory_order_acquire);
            if (tid) missing[count++]=tid;
        }
    }
    if (!count || atomic_load_explicit(generation,memory_order_seq_cst)!=observed) return;
    if (!atomic_compare_exchange_strong_explicit(&state->last_hint_ns,&last,now,memory_order_relaxed,memory_order_relaxed)) return;
    atomic_fetch_add_explicit(&state->hints,1,memory_order_relaxed);
    ggml_newa_barrier_wait_v1((uint32_t)observed,now,missing,count);
}

static inline void newa_barrier_relax(void) {
#if defined(__x86_64__) || defined(__i386__)
    __asm__ volatile("pause" ::: "memory");
#elif defined(__aarch64__)
    __asm__ volatile("yield" ::: "memory");
#else
    atomic_signal_fence(memory_order_seq_cst);
#endif
}

static inline void newa_barrier_wait_budget(struct newa_barrier_state * state, atomic_int * generation, int observed, int n_threads, unsigned int spins, uint32_t phase) {
    if (!spins || phase>3) abort();
    for (unsigned int i=0;i<spins;i++) {
        if (atomic_load_explicit(generation,memory_order_relaxed)!=observed) return;
        newa_barrier_relax();
    }
    if (atomic_load_explicit(generation,memory_order_relaxed)!=observed) return;
    newa_barrier_hint(state,generation,observed,n_threads);
    // Publish before rechecking the generation so the final arriver cannot miss a sleeper.
    atomic_fetch_add_explicit(&state->sleepers,1,memory_order_seq_cst);
    while (atomic_load_explicit(generation,memory_order_seq_cst)==observed) {
        atomic_fetch_add_explicit(&state->wait_calls,1,memory_order_relaxed);
        atomic_fetch_add_explicit(&state->phase_waits[phase],1,memory_order_relaxed);
        int result=(int)syscall(SYS_futex,(int *)generation,FUTEX_WAIT_PRIVATE,observed,NULL,NULL,0);
        if (result==-1) {
            int error=errno;
            if (error==EINTR) atomic_fetch_add_explicit(&state->interrupted,1,memory_order_relaxed);
            else if (error==EAGAIN) atomic_fetch_add_explicit(&state->already_changed,1,memory_order_relaxed);
            else abort();
        }
    }
    atomic_fetch_sub_explicit(&state->sleepers,1,memory_order_seq_cst);
}

static inline void newa_barrier_wait(struct newa_barrier_state * state, atomic_int * generation, int observed, int n_threads) {
    newa_barrier_wait_budget(state,generation,observed,n_threads,NEWA_BARRIER_SPINS,0);
}

static inline void newa_barrier_release(struct newa_barrier_state * state, atomic_int * generation) {
    // The caller advances generation with seq_cst before checking sleepers.
    if (atomic_load_explicit(&state->sleepers,memory_order_seq_cst)>0) {
        atomic_fetch_add_explicit(&state->wake_calls,1,memory_order_relaxed);
        if (syscall(SYS_futex,(int *)generation,FUTEX_WAKE_PRIVATE,INT_MAX,NULL,NULL,0)<0) abort();
    }
}

#endif
