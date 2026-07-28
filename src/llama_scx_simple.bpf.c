/* SPDX-License-Identifier: GPL-2.0 */
/*
 * Renamed baseline derived from Linux v6.17 tools/sched_ext/scx_simple.bpf.c.
 * Scheduling behavior is preserved: shared-DSQ weighted virtual-time order by
 * default, FIFO when fifo_sched is set. SCX_OPS_SWITCH_PARTIAL is the only
 * policy change: non-SCHED_EXT tasks remain under Ubuntu fair scheduling.
 */
#define BPF_NO_KFUNC_PROTOTYPES
#include "vmlinux.h"
#include <bpf/bpf_core_read.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>

char LICENSE[] SEC("license") = "GPL";
const volatile bool fifo_sched;

#define SHARED_DSQ 0
#define EXIT_DUMP_LEN 32768

struct exit_record {
	s32 kind;
	s64 exit_code;
	char reason[128];
	char message[1024];
};

struct exit_record exit_record SEC(".data");
char exit_dump[EXIT_DUMP_LEN] SEC(".data");

struct {
	__uint(type, BPF_MAP_TYPE_PERCPU_ARRAY);
	__uint(key_size, sizeof(u32));
	__uint(value_size, sizeof(u64));
	__uint(max_entries, 2); /* [local, shared DSQ] */
} stats SEC(".maps");

static u64 vtime_now;

/* Kfunc signatures exported by the recorded 7.0 kernel BTF. */
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

static void stat_inc(u32 index)
{
	u64 *count = bpf_map_lookup_elem(&stats, &index);
	if (count)
		(*count)++;
}

s32 BPF_STRUCT_OPS(llama_simple_select_cpu, struct task_struct *p,
			   s32 prev_cpu, u64 wake_flags)
{
	bool is_idle = false;
	s32 cpu = scx_bpf_select_cpu_dfl(p, prev_cpu, wake_flags, &is_idle);

	if (is_idle) {
		stat_inc(0);
		scx_bpf_dsq_insert(p, SCX_DSQ_LOCAL, SCX_SLICE_DFL, 0);
	}
	return cpu;
}

void BPF_STRUCT_OPS(llama_simple_enqueue, struct task_struct *p,
			    u64 enq_flags)
{
	stat_inc(1);
	if (fifo_sched) {
		scx_bpf_dsq_insert(p, SHARED_DSQ, SCX_SLICE_DFL, enq_flags);
	} else {
		u64 vtime = p->scx.dsq_vtime;

		if (time_before(vtime, vtime_now - SCX_SLICE_DFL))
			vtime = vtime_now - SCX_SLICE_DFL;
		scx_bpf_dsq_insert_vtime(p, SHARED_DSQ, SCX_SLICE_DFL, vtime,
					 enq_flags);
	}
}

void BPF_STRUCT_OPS(llama_simple_dispatch, s32 cpu, struct task_struct *prev)
{
	scx_bpf_dsq_move_to_local(SHARED_DSQ);
}

void BPF_STRUCT_OPS(llama_simple_running, struct task_struct *p)
{
	if (!fifo_sched && time_before(vtime_now, p->scx.dsq_vtime))
		vtime_now = p->scx.dsq_vtime;
}

void BPF_STRUCT_OPS(llama_simple_stopping, struct task_struct *p, bool runnable)
{
	if (!fifo_sched)
		p->scx.dsq_vtime += (SCX_SLICE_DFL - p->scx.slice) * 100 /
			p->scx.weight;
}

void BPF_STRUCT_OPS(llama_simple_enable, struct task_struct *p)
{
	p->scx.dsq_vtime = vtime_now;
}

s32 BPF_STRUCT_OPS_SLEEPABLE(llama_simple_init)
{
	return scx_bpf_create_dsq(SHARED_DSQ, -1);
}

void BPF_STRUCT_OPS(llama_simple_exit, struct scx_exit_info *info)
{
	exit_record.kind = info->kind;
	exit_record.exit_code = info->exit_code;
	bpf_probe_read_kernel_str(exit_record.reason, sizeof(exit_record.reason),
				  info->reason);
	bpf_probe_read_kernel_str(exit_record.message, sizeof(exit_record.message),
				  info->msg);
	bpf_probe_read_kernel_str(exit_dump, sizeof(exit_dump), info->dump);
}

SEC(".struct_ops.link")
struct sched_ext_ops llama_simple_ops = {
	.select_cpu = (void *)llama_simple_select_cpu,
	.enqueue = (void *)llama_simple_enqueue,
	.dispatch = (void *)llama_simple_dispatch,
	.running = (void *)llama_simple_running,
	.stopping = (void *)llama_simple_stopping,
	.enable = (void *)llama_simple_enable,
	.init = (void *)llama_simple_init,
	.exit = (void *)llama_simple_exit,
	.flags = SCX_OPS_SWITCH_PARTIAL,
	.name = "llama_simple",
};
