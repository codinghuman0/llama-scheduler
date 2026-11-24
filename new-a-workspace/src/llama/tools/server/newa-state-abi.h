#pragma once

// Wire layout adapted from hsju2021/llama.cpp-fork's server-scx.h (MIT).
// Compiler types let BPF include this without userspace libc headers.
struct server_scx_state_v2 {
    __UINT32_TYPE__ version;
    __UINT32_TYPE__ phase;
    __UINT32_TYPE__ active;
    __UINT32_TYPE__ reserved;
    __UINT64_TYPE__ run_id;
    __UINT64_TYPE__ sequence;
};

#ifdef __cplusplus
#define NEWA_ABI_ASSERT static_assert
#else
#define NEWA_ABI_ASSERT _Static_assert
#endif
NEWA_ABI_ASSERT(sizeof(struct server_scx_state_v2) == 32, "SCX state ABI v2 size");
NEWA_ABI_ASSERT(__builtin_offsetof(struct server_scx_state_v2, version) == 0, "version offset");
NEWA_ABI_ASSERT(__builtin_offsetof(struct server_scx_state_v2, phase) == 4, "phase offset");
NEWA_ABI_ASSERT(__builtin_offsetof(struct server_scx_state_v2, active) == 8, "active offset");
NEWA_ABI_ASSERT(__builtin_offsetof(struct server_scx_state_v2, reserved) == 12, "reserved offset");
NEWA_ABI_ASSERT(__builtin_offsetof(struct server_scx_state_v2, run_id) == 16, "run_id offset");
NEWA_ABI_ASSERT(__builtin_offsetof(struct server_scx_state_v2, sequence) == 24, "sequence offset");
#undef NEWA_ABI_ASSERT
