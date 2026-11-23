// SPDX-License-Identifier: MIT
// Define NEWA_Q6_NAME and NEWA_Q6_COLUMNS before including this file.
static __attribute__((noinline)) void NEWA_Q6_NAME(
        int n, float * GGML_RESTRICT out, const void * GGML_RESTRICT weights,
        const void * GGML_RESTRICT activations, size_t stride) {
    const block_q6_K * GGML_RESTRICT x = weights;
    const block_q8_K * y[NEWA_Q6_COLUMNS];
    __m256 acc[NEWA_Q6_COLUMNS];
    for (int c = 0; c < NEWA_Q6_COLUMNS; ++c) {
        y[c] = (const block_q8_K *) ((const char *) activations + c * stride);
        acc[c] = _mm256_setzero_ps();
    }
    const __m256i m3 = _mm256_set1_epi8(3);
    const __m256i m15 = _mm256_set1_epi8(15);
    for (int i = 0; i < n / QK_K; ++i) {
        const float xd = GGML_CPU_FP16_TO_FP32(x[i].d);
        const uint8_t * q4 = x[i].ql;
        const uint8_t * qh = x[i].qh;
        const __m128i scales = _mm_loadu_si128((const __m128i *) x[i].scales);
        const __m256i scales_16 = _mm256_cvtepi8_epi16(scales);
        __m256i sumi[NEWA_Q6_COLUMNS];
        for (int c = 0; c < NEWA_Q6_COLUMNS; ++c) sumi[c] = _mm256_setzero_si256();
        for (int j = 0; j < QK_K / 128; ++j) {
            const __m256i lo1 = _mm256_loadu_si256((const __m256i *) q4); q4 += 32;
            const __m256i lo2 = _mm256_loadu_si256((const __m256i *) q4); q4 += 32;
            const __m256i hi = _mm256_loadu_si256((const __m256i *) qh); qh += 32;
            const __m256i h0 = _mm256_slli_epi16(_mm256_and_si256(hi, m3), 4);
            const __m256i h1 = _mm256_slli_epi16(_mm256_and_si256(hi, _mm256_set1_epi8(12)), 2);
            const __m256i h2 = _mm256_and_si256(hi, _mm256_set1_epi8(48));
            const __m256i h3 = _mm256_srli_epi16(_mm256_and_si256(hi, _mm256_set1_epi8(-64)), 2);
            const __m256i w0 = _mm256_or_si256(_mm256_and_si256(lo1, m15), h0);
            const __m256i w1 = _mm256_or_si256(_mm256_and_si256(lo2, m15), h1);
            const __m256i w2 = _mm256_or_si256(_mm256_and_si256(_mm256_srli_epi16(lo1, 4), m15), h2);
            const __m256i w3 = _mm256_or_si256(_mm256_and_si256(_mm256_srli_epi16(lo2, 4), m15), h3);
            const __m256i s0 = _mm256_cvtepi8_epi16(_mm_shuffle_epi8(scales, newa_q6_scale_shuffle(j * 4)));
            const __m256i s1 = _mm256_cvtepi8_epi16(_mm_shuffle_epi8(scales, newa_q6_scale_shuffle(j * 4 + 1)));
            const __m256i s2 = _mm256_cvtepi8_epi16(_mm_shuffle_epi8(scales, newa_q6_scale_shuffle(j * 4 + 2)));
            const __m256i s3 = _mm256_cvtepi8_epi16(_mm_shuffle_epi8(scales, newa_q6_scale_shuffle(j * 4 + 3)));
            for (int c = 0; c < NEWA_Q6_COLUMNS; ++c) {
                const int8_t * q8 = y[c][i].qs + j * 128;
                __m256i p0 = _mm256_maddubs_epi16(w0, _mm256_loadu_si256((const __m256i *) q8));
                __m256i p1 = _mm256_maddubs_epi16(w1, _mm256_loadu_si256((const __m256i *) (q8 + 32)));
                __m256i p2 = _mm256_maddubs_epi16(w2, _mm256_loadu_si256((const __m256i *) (q8 + 64)));
                __m256i p3 = _mm256_maddubs_epi16(w3, _mm256_loadu_si256((const __m256i *) (q8 + 96)));
                p0 = _mm256_madd_epi16(s0, p0);
                p1 = _mm256_madd_epi16(s1, p1);
                p2 = _mm256_madd_epi16(s2, p2);
                p3 = _mm256_madd_epi16(s3, p3);
                sumi[c] = _mm256_add_epi32(sumi[c], _mm256_add_epi32(p0, p1));
                sumi[c] = _mm256_add_epi32(sumi[c], _mm256_add_epi32(p2, p3));
            }
        }
        for (int c = 0; c < NEWA_Q6_COLUMNS; ++c) {
            const __m256i sums = _mm256_loadu_si256((const __m256i *) y[c][i].bsums);
            const __m256i correction = _mm256_slli_epi32(_mm256_madd_epi16(sums, scales_16), 5);
            const __m256i total = _mm256_sub_epi32(sumi[c], correction);
            const float d = y[c][i].d * xd;
            acc[c] = _mm256_fmadd_ps(_mm256_broadcast_ss(&d), _mm256_cvtepi32_ps(total), acc[c]);
        }
    }
    for (int c = 0; c < NEWA_Q6_COLUMNS; ++c) out[c] = newa_q6_hsum(acc[c]);
}
