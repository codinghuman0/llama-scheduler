/* SPDX-License-Identifier: GPL-2.0 */
/*
 * Scheduler UAPI imported from the headers for the recorded running kernel.
 * Makefile supplies those headers before system include paths.
 */
#ifndef LLAMA_SCHED_UAPI_H
#define LLAMA_SCHED_UAPI_H

#include <linux/sched.h>
#include <linux/sched/types.h>

#ifndef SCHED_EXT
#error "The selected kernel UAPI headers do not define SCHED_EXT"
#endif

/* docs/environment.txt records SCHED_EXT as policy 7 for this target kernel. */
_Static_assert(SCHED_EXT == 7,
	       "The selected kernel UAPI does not match the recorded SCHED_EXT policy");

#endif /* LLAMA_SCHED_UAPI_H */
