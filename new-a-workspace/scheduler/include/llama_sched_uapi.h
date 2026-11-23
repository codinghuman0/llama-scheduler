/* SPDX-License-Identifier: GPL-2.0 */
/*
 * Use the system's exported userspace UAPI. Older linux-libc-dev packages may
 * predate sched_ext, so provide the policy value after Makefile validates it
 * against the selected matching kernel header.
 */
#ifndef LLAMA_SCHED_UAPI_H
#define LLAMA_SCHED_UAPI_H

#include <linux/sched.h>
#include <linux/sched/types.h>

#ifndef SCHED_EXT
#define SCHED_EXT 7
#endif

_Static_assert(SCHED_EXT == 7,
	       "The exported scheduler UAPI has an unexpected SCHED_EXT policy");

#endif /* LLAMA_SCHED_UAPI_H */
