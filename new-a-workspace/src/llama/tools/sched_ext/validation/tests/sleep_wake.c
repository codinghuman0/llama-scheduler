/* SPDX-License-Identifier: GPL-2.0 */
/* Finite sleeping/waking workload; it never changes scheduling policy. */
#include <errno.h>
#include <getopt.h>
#include <signal.h>
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
	fprintf(stderr, "Usage: %s [--seconds N] [--interval-ms N]\n", program);
}

static double monotonic_seconds(void)
{
	struct timespec now;

	clock_gettime(CLOCK_MONOTONIC, &now);
	return (double)now.tv_sec + (double)now.tv_nsec / 1000000000.0;
}

static int parse_positive(const char *value, unsigned long *out)
{
	char *end = NULL;
	unsigned long parsed;

	errno = 0;
	parsed = strtoul(value, &end, 10);
	if (errno || !value[0] || *end || !parsed)
		return -1;
	*out = parsed;
	return 0;
}

int main(int argc, char **argv)
{
	static const struct option options[] = {
		{ "seconds", required_argument, NULL, 's' },
		{ "interval-ms", required_argument, NULL, 'i' },
		{ "help", no_argument, NULL, 'h' },
		{ NULL, 0, NULL, 0 },
	};
	unsigned long seconds = 1;
	unsigned long interval_ms = 100;
	unsigned long iterations = 0;
	int option;
	double deadline;

	while ((option = getopt_long(argc, argv, "s:i:h", options, NULL)) != -1) {
		switch (option) {
		case 's':
			if (parse_positive(optarg, &seconds)) {
				fprintf(stderr, "--seconds must be positive\n");
				return EXIT_FAILURE;
			}
			break;
		case 'i':
			if (parse_positive(optarg, &interval_ms) || interval_ms > 60000) {
				fprintf(stderr, "--interval-ms must be between 1 and 60000\n");
				return EXIT_FAILURE;
			}
			break;
		default:
			usage(argv[0]);
			return option != 'h';
		}
	}

	signal(SIGINT, request_stop);
	signal(SIGTERM, request_stop);
	deadline = monotonic_seconds() + (double)seconds;
	while (!stop && monotonic_seconds() < deadline) {
		struct timespec delay = {
			.tv_sec = (time_t)(interval_ms / 1000),
			.tv_nsec = (long)(interval_ms % 1000) * 1000000L,
		};

		while (!stop && nanosleep(&delay, &delay) && errno == EINTR)
			;
		if (stop)
			break;
		iterations++;
		printf("progress workload=sleep_wake iterations=%lu elapsed_seconds=%.3f\n",
		       iterations, (double)seconds - (deadline - monotonic_seconds()));
		fflush(stdout);
	}
	printf("result workload=sleep_wake iterations=%lu stopped=%d\n", iterations,
	       stop ? 1 : 0);
	return stop ? EXIT_FAILURE : EXIT_SUCCESS;
}
