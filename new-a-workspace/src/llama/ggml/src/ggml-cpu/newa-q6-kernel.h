// SPDX-License-Identifier: MIT
// AVX2 operations adapted from ggml; see LICENSE in this directory.
#pragma once
#include "quants.h"
#include "ggml-cpu-impl.h"
#include "simd-mappings.h"

#if !defined(__AVX2__) || !defined(__FMA__)
#error This experimental kernel requires AVX2 and FMA
#endif

static inline __m128i newa_q6_scale_shuffle(int i) {
    static const uint8_t masks[128] = {
         0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1,
         2, 2, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3,
         4, 4, 4, 4, 4, 4, 4, 4, 5, 5, 5, 5, 5, 5, 5, 5,
         6, 6, 6, 6, 6, 6, 6, 6, 7, 7, 7, 7, 7, 7, 7, 7,
         8, 8, 8, 8, 8, 8, 8, 8, 9, 9, 9, 9, 9, 9, 9, 9,
        10,10,10,10,10,10,10,10,11,11,11,11,11,11,11,11,
        12,12,12,12,12,12,12,12,13,13,13,13,13,13,13,13,
        14,14,14,14,14,14,14,14,15,15,15,15,15,15,15,15
    };
    return _mm_loadu_si128((const __m128i *) masks + i);
}

static inline float newa_q6_hsum(const __m256 value) {
    __m128 sum = _mm256_extractf128_ps(value, 1);
    sum = _mm_add_ps(sum, _mm256_castps256_ps128(value));
    sum = _mm_add_ps(sum, _mm_movehl_ps(sum, sum));
    sum = _mm_add_ss(sum, _mm_movehdup_ps(sum));
    return _mm_cvtss_f32(sum);
}
