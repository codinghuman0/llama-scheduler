#define _GNU_SOURCE
/* SPDX-License-Identifier: GPL-2.0 */
/* Launch exactly one selected child under SCHED_EXT. */
#include <errno.h>
#include <fcntl.h>
#include <getopt.h>
#include <signal.h>
#include <sched.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

#include "llama_sched_uapi.h"

#define SCX_STATE_PATH "/sys/kernel/sched_ext/state"

static void usage(const char *program)
{
	fprintf(stderr,
		"Usage: %s [--dry-run --state-path FILE] -- command [args...]\n"
		"  --dry-run          fork and exec without changing the child policy\n"
		"  --state-path FILE  test-only state file; requires --dry-run\n"
		"  -h, --help         show this help\n",
		program);
}

static int scheduler_is_enabled(const char *path)
{
	char state[32] = {};
	int fd;
	ssize_t read_len;

	fd = open(path, O_RDONLY | O_CLOEXEC);
	if (fd < 0) {
		fprintf(stderr, "cannot read sched_ext state at %s: %s\n", path,
			strerror(errno));
		return -1;
	}
	read_len = read(fd, state, sizeof(state) - 1);
	if (read_len < 0) {
		fprintf(stderr, "cannot read sched_ext state at %s: %s\n", path,
			strerror(errno));
		close(fd);
		return -1;
	}
	close(fd);
	state[read_len] = '\0';
	if (read_len > 0 && state[read_len - 1] == '\n')
		state[--read_len] = '\0';
	if (strcmp(state, "enabled") == 0)
		return 1;
	fprintf(stderr, "sched_ext scheduler is not active (state: %s)\n", state);
	return 0;
}

static void child_exec(char *const command[], int gate_fd, bool dry_run)
{
	char release;

	if (read(gate_fd, &release, sizeof(release)) != sizeof(release))
		_exit(EXIT_FAILURE);
	close(gate_fd);
	if (!dry_run) {
		struct sched_attr attr = {
			.size = sizeof(attr),
			.sched_policy = SCHED_EXT,
		};

		if (syscall(SYS_sched_setattr, 0, &attr, 0)) {
			fprintf(stderr, "child %ld: cannot enter SCHED_EXT: %s\n",
				(long)getpid(), strerror(errno));
			_exit(126);
		}
	}
	execvp(command[0], command);
	fprintf(stderr, "child %ld: execvp(%s): %s\n", (long)getpid(),
		command[0], strerror(errno));
	_exit(127);
}

int main(int argc, char **argv)
{
	static const struct option options[] = {
		{ "dry-run", no_argument, NULL, 'n' },
		{ "state-path", required_argument, NULL, 's' },
		{ "help", no_argument, NULL, 'h' },
		{ NULL, 0, NULL, 0 },
	};
	const char *state_path = SCX_STATE_PATH;
	bool dry_run = false;
	bool custom_state_path = false;
	int gate[2];
	int parent_policy;
	int option;
	int state;
	pid_t child;
	int wait_status;
	char release = '1';

	while ((option = getopt_long(argc, argv, "ns:h", options, NULL)) != -1) {
		switch (option) {
		case 'n':
			dry_run = true;
			break;
		case 's':
			state_path = optarg;
			custom_state_path = true;
			break;
		default:
			usage(argv[0]);
			return option != 'h';
		}
	}
	if (optind == argc) {
		fprintf(stderr, "missing command after --\n");
		usage(argv[0]);
		return EXIT_FAILURE;
	}
	if (!dry_run && custom_state_path) {
		fprintf(stderr, "--state-path is allowed only with --dry-run\n");
		return EXIT_FAILURE;
	}
	state = scheduler_is_enabled(state_path);
	if (state != 1)
		return EXIT_FAILURE;
	parent_policy = sched_getscheduler(0);
	if (parent_policy < 0) {
		fprintf(stderr, "cannot read parent scheduling policy: %s\n",
			strerror(errno));
		return EXIT_FAILURE;
	}
	if (pipe2(gate, O_CLOEXEC)) {
		fprintf(stderr, "pipe2: %s\n", strerror(errno));
		return EXIT_FAILURE;
	}
	child = fork();
	if (child < 0) {
		fprintf(stderr, "fork: %s\n", strerror(errno));
		close(gate[0]);
		close(gate[1]);
		return EXIT_FAILURE;
	}
	if (child == 0) {
		close(gate[1]);
		child_exec(&argv[optind], gate[0], dry_run);
	}
	close(gate[0]);
	printf("parent_pid=%ld parent_policy=%d child_pid=%ld mode=%s\n",
	       (long)getpid(), parent_policy, (long)child,
	       dry_run ? "dry-run" : "sched_ext");
	fflush(stdout);
	if (write(gate[1], &release, sizeof(release)) != sizeof(release)) {
		fprintf(stderr, "cannot release child %ld: %s\n", (long)child,
			strerror(errno));
		close(gate[1]);
		kill(child, SIGKILL);
		waitpid(child, NULL, 0);
		return EXIT_FAILURE;
	}
	close(gate[1]);
	if (waitpid(child, &wait_status, 0) < 0) {
		fprintf(stderr, "waitpid: %s\n", strerror(errno));
		return EXIT_FAILURE;
	}
	if (sched_getscheduler(0) != parent_policy) {
		fprintf(stderr, "parent scheduling policy changed unexpectedly\n");
		return EXIT_FAILURE;
	}
	if (WIFEXITED(wait_status))
		return WEXITSTATUS(wait_status);
	if (WIFSIGNALED(wait_status))
		return 128 + WTERMSIG(wait_status);
	return EXIT_FAILURE;
}
