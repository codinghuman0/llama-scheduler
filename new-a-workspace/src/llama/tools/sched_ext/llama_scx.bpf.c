/* SPDX-License-Identifier: GPL-2.0 */
/*
 * Derived from Linux v6.17 tools/sched_ext/scx_simple.bpf.c.
 * Keep its weighted-vtime scheduling; phase is input only.
 *
 * Copyright (c) 2022 Meta Platforms, Inc. and affiliates.
 * Copyright (c) 2022 Tejun Heo <tj@kernel.org>
 * Copyright (c) 2022 David Vernet <dvernet@meta.com>
 */
#define BPF_NO_KFUNC_PROTOTYPES
#define LLAMA_SCX_BPF
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wmissing-declarations"
#include "vmlinux.h"
#pragma clang diagnostic pop
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>
#include "llama_scx_state.h"

char _license[] SEC("license") = "GPL";

/* Explicit section placement keeps this zero-initialized ABI out of .bss. */
volatile struct llama_scx_control_state control_state SEC(".data") = {};
static u64 vtime_now;

#define SHARED_DSQ 0

/* Direct-object compatibility definitions reused from the golden scheduler. */
s32 scx_bpf_create_dsq(u64 dsq_id, s32 node) __ksym;
s32 scx_bpf_select_cpu_dfl(struct task_struct *p, s32 prev_cpu,
			   u64 wake_flags, bool *is_idle) __ksym;
void scx_bpf_dsq_insert(struct task_struct *p, u64 dsq_id, u64 slice,
			u64 enq_flags) __ksym;
void scx_bpf_dsq_insert_vtime(struct task_struct *p, u64 dsq_id, u64 slice,
				      u64 vtime, u64 enq_flags) __ksym;
bool scx_bpf_dsq_move_to_local(u64 dsq_id) __ksym;

#define BPF_STRUCT_OPS(name, args...) \
	SEC("struct_ops/" #name) BPF_PROG(name, ##args)
#define BPF_STRUCT_OPS_SLEEPABLE(name, args...) \
	SEC("struct_ops.s/" #name) BPF_PROG(name, ##args)

static __always_inline bool time_before(u64 a, u64 b)
{
	return (s64)(a - b) < 0;
}

s32 BPF_STRUCT_OPS(llama_select_cpu, struct task_struct *p, s32 prev_cpu, u64 wake_flags)
{
	bool is_idle = false;
	s32 cpu;

	cpu = scx_bpf_select_cpu_dfl(p, prev_cpu, wake_flags, &is_idle);
	if (is_idle)
		scx_bpf_dsq_insert(p, SCX_DSQ_LOCAL, SCX_SLICE_DFL, 0);

	return cpu;
}

void BPF_STRUCT_OPS(llama_enqueue, struct task_struct *p, u64 enq_flags)
{
	u64 vtime = p->scx.dsq_vtime;

	/* Limit the budget that an idling task can accumulate to one slice. */
	if (time_before(vtime, vtime_now - SCX_SLICE_DFL))
		vtime = vtime_now - SCX_SLICE_DFL;

	scx_bpf_dsq_insert_vtime(p, SHARED_DSQ, SCX_SLICE_DFL, vtime, enq_flags);
}

void BPF_STRUCT_OPS(llama_dispatch, s32 cpu, struct task_struct *prev)
{
	scx_bpf_dsq_move_to_local(SHARED_DSQ);
}

void BPF_STRUCT_OPS(llama_running, struct task_struct *p)
{
	/* Keep the upstream concurrent, intentionally racy vtime advancement. */
	if (time_before(vtime_now, p->scx.dsq_vtime))
		vtime_now = p->scx.dsq_vtime;
}

void BPF_STRUCT_OPS(llama_stopping, struct task_struct *p, bool runnable)
{
	/* Charge the consumed slice inversely by weight, including upstream yield behavior. */
	p->scx.dsq_vtime += (SCX_SLICE_DFL - p->scx.slice) * 100 / p->scx.weight;
}

void BPF_STRUCT_OPS(llama_enable, struct task_struct *p)
{
	p->scx.dsq_vtime = vtime_now;
}

s32 BPF_STRUCT_OPS_SLEEPABLE(llama_init)
{
	return scx_bpf_create_dsq(SHARED_DSQ, -1);
}

void BPF_STRUCT_OPS(llama_exit, struct scx_exit_info *ei)
{
	control_state.exit_kind = ei->kind;
}

SEC("uprobe")
int BPF_UPROBE(llama_phase, __u32 phase)
{
	__u32 tgid = bpf_get_current_pid_tgid() >> 32;

	if (tgid != control_state.selected_tgid)
		return 0;
	if (phase > LLAMA_SCX_PHASE_MIXED)
		return 0;
	control_state.current_phase = phase;
	return 0;
}

SEC(".struct_ops.link")
struct sched_ext_ops llama_ops = {
	.select_cpu = (void *)llama_select_cpu,
	.enqueue = (void *)llama_enqueue,
	.dispatch = (void *)llama_dispatch,
	.running = (void *)llama_running,
	.stopping = (void *)llama_stopping,
	.enable = (void *)llama_enable,
	.init = (void *)llama_init,
	.exit = (void *)llama_exit,
	.flags = SCX_OPS_SWITCH_PARTIAL,
	.name = "llama_scx",
};
