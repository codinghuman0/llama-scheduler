// SPDX-License-Identifier: MIT
#ifndef NEWA_Q6_POLICY_H
#define NEWA_Q6_POLICY_H
#if !defined(__gnu_linux__)
#error This implementation requires Linux
#endif
#include <pthread.h>
#include "newa-q6-kernel.h"
#define NEWA_Q6_NAME newa_q6_batch4
#define NEWA_Q6_COLUMNS 4
#include "newa-q6-kernel.inc"
#undef NEWA_Q6_NAME
#undef NEWA_Q6_COLUMNS

static bool newa_q6_enabled;
static bool newa_q6_phase_batch;
static pthread_once_t newa_q6_once = PTHREAD_ONCE_INIT;
static atomic_uint_fast64_t newa_q6_chunks[4];

static void newa_q6_report(void) {
    fprintf(stderr, "NEWA_Q6 stats worker0_chunks=%" PRIuFAST64 "/%" PRIuFAST64 "/%" PRIuFAST64 "/%" PRIuFAST64 "\n",
            atomic_load(&newa_q6_chunks[0]), atomic_load(&newa_q6_chunks[1]),
            atomic_load(&newa_q6_chunks[2]), atomic_load(&newa_q6_chunks[3]));
}

static void newa_q6_init(void) {
    const char * mode = getenv("GGML_NEWA_Q6_BATCH");
    GGML_ASSERT(!mode || strcmp(mode, "off") == 0 || strcmp(mode, "prefill") == 0 || strcmp(mode, "phase_batch") == 0);
    newa_q6_phase_batch = mode && strcmp(mode, "phase_batch") == 0;
    newa_q6_enabled = newa_q6_phase_batch || (mode && strcmp(mode, "prefill") == 0);
    fprintf(stderr, "NEWA_Q6 mode=%s columns=4 prefill_only=%d\n", newa_q6_phase_batch ? "phase_batch" : (newa_q6_enabled ? "prefill" : "off"), !newa_q6_phase_batch);
    GGML_ASSERT(atexit(newa_q6_report) == 0);
}

static void newa_q6_configure(void) {
    GGML_ASSERT(pthread_once(&newa_q6_once, newa_q6_init) == 0);
}

static inline bool newa_q6_phase_allowed(unsigned phase) {
    return newa_q6_enabled && (phase == 1 || (newa_q6_phase_batch && (phase == 2 || phase == 3)));
}

static void newa_q6_record(unsigned phase) {
    GGML_ASSERT(newa_q6_phase_allowed(phase));
    atomic_fetch_add_explicit(&newa_q6_chunks[phase], 1, memory_order_relaxed);
}
#endif
