/* SPDX-License-Identifier: MIT */
#ifndef NEWA_PHASE_POLICY_H
#define NEWA_PHASE_POLICY_H
#include <stdint.h>

enum newa_phase_policy { NEWA_PHASE_ALL, NEWA_PHASE_PREFILL, NEWA_PHASE_BUDGET };

static inline unsigned int newa_phase_spins(enum newa_phase_policy policy, uint32_t phase) {
    if (policy == NEWA_PHASE_ALL) return 4096;
    if (phase == 1) return 4096;
    if (policy == NEWA_PHASE_BUDGET && phase == 2) return 65536;
    return 0;
}
#endif
