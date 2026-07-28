/* SPDX-License-Identifier: GPL-2.0 */
/* Bounded CPU workload; it remains SCHED_NORMAL unless --ext is explicit. */
#include <errno.h>
#include <getopt.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>
#include <sched.h>

#include <linux/sched.h>

#ifndef SCHED_EXT
#define SCHED_EXT 7
#endif

struct sched_attr_local {
	uint32_t size;
	uint32_t sched_policy;
	uint64_t sched_flags;
	int32_t sched_nice;
	uint32_t sched_priority;
	uint64_t sched_runtime;
	uint64_t sched_deadline;
	uint64_t sched_period;
};

static volatile sig_atomic_t stop;

static void request_stop(int signal_number)
{
	(void)signal_number;
	stop = 1;
}

static void usage(const char *program)
{
	fprintf(stderr, "Usage: %s [--seconds N] [--ext]\n", program);
}

static double monotonic_seconds(void)
{
	struct timespec now;

	clock_gettime(CLOCK_MONOTONIC, &now);
	return (double)now.tv_sec + (double)now.tv_nsec / 1000000000.0;
}

int main(int argc, char **argv)
{
	static const struct option options[] = {
		{ "seconds", required_argument, NULL, 's' },
		{ "ext", no_argument, NULL, 'e' },
		{ "help", no_argument, NULL, 'h' },
		{ NULL, 0, NULL, 0 },
	};
	bool use_ext = false;
	unsigned long seconds = 1;
	uint64_t value = 0x9e3779b97f4a7c15ULL;
	int original_policy;
	int option;
	double deadline;

	while ((option = getopt_long(argc, argv, "s:eh", options, NULL)) != -1) {
		switch (option) {
		case 's':
			seconds = strtoul(optarg, NULL, 10);
			if (!seconds) {
				fprintf(stderr, "--seconds must be positive\n");
				return EXIT_FAILURE;
			}
			break;
		case 'e':
			use_ext = true;
			break;
		default:
			usage(argv[0]);
			return option != 'h';
		}
	}

	original_policy = sched_getscheduler(0);
	if (original_policy < 0) {
		perror("sched_getscheduler");
		return EXIT_FAILURE;
	}
	if (use_ext) {
		struct sched_attr_local attr = {
			.size = sizeof(attr),
			.sched_policy = SCHED_EXT,
		};

		if (syscall(SYS_sched_setattr, 0, &attr, 0)) {
			fprintf(stderr, "cannot enter SCHED_EXT: %s\n", strerror(errno));
			return EXIT_FAILURE;
		}
	}

	signal(SIGINT, request_stop);
	signal(SIGTERM, request_stop);
	deadline = monotonic_seconds() + (double)seconds;
	while (!stop && monotonic_seconds() < deadline) {
		value ^= value << 13;
		value ^= value >> 7;
		value ^= value << 17;
	}
	if (use_ext && sched_setscheduler(0, original_policy, NULL))
		fprintf(stderr, "warning: could not restore scheduling policy: %s\n",
			strerror(errno));
	printf("cpu_burn checksum=%llu original_policy=%d\n",
	       (unsigned long long)value, original_policy);
	return EXIT_SUCCESS;
}
