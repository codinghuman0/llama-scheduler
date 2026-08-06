/* SPDX-License-Identifier: GPL-2.0 */
/* Bounded CPU workload; it never changes scheduling policy. */
#include <getopt.h>
#include <sched.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

static volatile sig_atomic_t stop;

static void request_stop(int signal_number)
{
	(void)signal_number;
	stop = 1;
}

static void usage(const char *program)
{
	fprintf(stderr, "Usage: %s [--seconds N]\n", program);
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
		{ "help", no_argument, NULL, 'h' },
		{ NULL, 0, NULL, 0 },
	};
	unsigned long seconds = 1;
	uint64_t value = 0x9e3779b97f4a7c15ULL;
	int original_policy;
	int option;
	double deadline;

	while ((option = getopt_long(argc, argv, "s:h", options, NULL)) != -1) {
		switch (option) {
		case 's':
			seconds = strtoul(optarg, NULL, 10);
			if (!seconds) {
				fprintf(stderr, "--seconds must be positive\n");
				return EXIT_FAILURE;
			}
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
	signal(SIGINT, request_stop);
	signal(SIGTERM, request_stop);
	deadline = monotonic_seconds() + (double)seconds;
	while (!stop && monotonic_seconds() < deadline) {
		value ^= value << 13;
		value ^= value >> 7;
		value ^= value << 17;
	}
	printf("cpu_burn checksum=%llu original_policy=%d\n",
	       (unsigned long long)value, original_policy);
	return EXIT_SUCCESS;
}
