/* SPDX-License-Identifier: GPL-2.0 */
#define _GNU_SOURCE
#include <cpuid.h>
#include <errno.h>
#include <sched.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "new_a.h"

_Static_assert(CPU_SETSIZE == NEW_A_MAX_CPUS, "CPU mask bounds must match");

struct cpu_record {
	unsigned int cpu, family, model, stepping, core_type, native_model;
	bool hybrid, amd_leaf26, amd_heterogeneous;
	char vendor[13];
};

static int inspect_cpu(struct cpu_record *r)
{
	unsigned int a, b, c, d, maximum, extended;

	maximum = __get_cpuid_max(0, NULL);
	if (maximum < 1)
		return -1;
	__cpuid_count(0, 0, a, b, c, d);
	memcpy(r->vendor, &b, 4);
	memcpy(r->vendor + 4, &d, 4);
	memcpy(r->vendor + 8, &c, 4);
	r->vendor[12] = 0;
	__cpuid_count(1, 0, a, b, c, d);
	r->family = (a >> 8) & 15;
	r->model = (a >> 4) & 15;
	r->stepping = a & 15;
	if (r->family == 6 || r->family == 15)
		r->model |= ((a >> 16) & 15) << 4;
	if (r->family == 15)
		r->family += (a >> 20) & 255;
	if (!strcmp(r->vendor, "GenuineIntel")) {
		if (maximum >= 7) {
			__cpuid_count(7, 0, a, b, c, d);
			r->hybrid = !!(d & (1U << 15));
		}
		if (r->hybrid) {
			if (maximum < 0x1a)
				return -1;
			__cpuid_count(0x1a, 0, a, b, c, d);
			r->core_type = a >> 24;
		}
	} else if (!strcmp(r->vendor, "AuthenticAMD")) {
		extended = __get_cpuid_max(0x80000000, NULL);
		if (extended >= 0x80000026) {
			bool core_seen = false, terminated = false;

			r->amd_leaf26 = true;
			for (unsigned int sub = 0; sub < 32; sub++) {
				unsigned int level;

				__cpuid_count(0x80000026, sub, a, b, c, d);
				level = (c >> 8) & 255;
				if (!level) {
					terminated = true;
					break;
				}
				r->amd_heterogeneous |= !!(a & (1U << 30));
				if (level == 1) {
					if (core_seen)
						return -1;
					core_seen = true;
					r->core_type = b >> 28;
					r->native_model = (b >> 24) & 15;
				}
			}
			if (!core_seen || !terminated)
				return -1;
		}
	} else {
		return -1;
	}
	return 0;
}

int main(int argc, char **argv)
{
	struct cpu_record rows[NEW_A_MAX_CPUS] = {};
	cpu_set_t original, one, seen, restored;
	int result = 1;

	if (argc == 2 && !strcmp(argv[1], "--help")) {
		puts("사용법: cpu-probe CPU_ID [...]; 하위 프로세스의 Affinity만 일시 변경하고 복원합니다.");
		return 0;
	}
	if (argc < 2 || argc > NEW_A_MAX_CPUS + 1 ||
	    sched_getaffinity(0, sizeof(original), &original))
		return 1;
	CPU_ZERO(&seen);
	for (int i = 1; i < argc; i++) {
		char *end;
		unsigned long cpu;

		errno = 0;
		cpu = strtoul(argv[i], &end, 10);
		if (errno || end == argv[i] || *end || cpu >= NEW_A_MAX_CPUS ||
		    !CPU_ISSET(cpu, &original) || CPU_ISSET(cpu, &seen))
			goto out;
		CPU_SET(cpu, &seen);
		CPU_ZERO(&one);
		CPU_SET(cpu, &one);
		if (sched_setaffinity(0, sizeof(one), &one) || sched_getcpu() != (int)cpu)
			goto out;
		rows[i - 1].cpu = cpu;
		if (inspect_cpu(&rows[i - 1]))
			goto out;
	}
	result = 0;
out:
	if (sched_setaffinity(0, sizeof(original), &original) ||
	    sched_getaffinity(0, sizeof(restored), &restored) ||
	    !CPU_EQUAL(&original, &restored))
		result = 1;
	if (result) {
		fputs("CPUID 또는 CPU 집합 검증 실패. 설정을 생성하지 않습니다.\n", stderr);
		return result;
	}
	printf("{\"schema\":1,\"max_cpus\":%d,\"affinity_restored\":true,\"cpus\":[", NEW_A_MAX_CPUS);
	for (int i = 0; i < argc - 1; i++) {
		struct cpu_record *r = &rows[i];

		printf("%s{\"cpu\":%u,\"vendor\":\"%s\",\"family\":%u,\"model\":%u,\"stepping\":%u,"
		       "\"hybrid\":%s,\"core_type\":%u,\"native_model\":%u,\"amd_leaf26\":%s,\"amd_heterogeneous\":%s}",
		       i ? "," : "", r->cpu, r->vendor, r->family, r->model, r->stepping,
		       r->hybrid ? "true" : "false", r->core_type, r->native_model,
		       r->amd_leaf26 ? "true" : "false", r->amd_heterogeneous ? "true" : "false");
	}
	puts("]}");
	return 0;
}
