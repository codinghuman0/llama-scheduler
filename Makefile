# SPDX-License-Identifier: GPL-2.0
# Build the non-privileged sched_ext baseline. Nothing here loads BPF.

CLANG ?= clang
CC ?= cc
BPFTOOL ?= bpftool

KERNEL_RELEASE ?= $(shell uname -r)
KERNEL_HEADERS ?= /lib/modules/$(KERNEL_RELEASE)/build
KERNEL_SCHED_UAPI := $(KERNEL_HEADERS)/include/uapi/linux/sched.h

BUILD_DIR := build
INCLUDE_DIR := $(BUILD_DIR)/include
BPF_OBJ := $(BUILD_DIR)/llama_scx_simple.bpf.o
SCHED_BIN := $(BUILD_DIR)/bin/llama_scx_simple
WORKLOAD_BIN := $(BUILD_DIR)/bin/cpu_burn
SLEEP_WAKE_BIN := $(BUILD_DIR)/bin/sleep_wake
CHILD_BIN := $(BUILD_DIR)/bin/llama_scx_child
VMLINUX_BTF ?= /sys/kernel/btf/vmlinux

ARCH := x86
BPF_CFLAGS := -target bpf -D__TARGET_ARCH_$(ARCH) -O2 -g -Wall -Werror \
	-Wno-missing-declarations \
	-I$(INCLUDE_DIR) -Iinclude -I/usr/include/$(shell $(CC) -dumpmachine)
USER_CFLAGS := -O2 -g -Wall -Wextra -Werror -std=gnu11 -Iinclude
USER_LDLIBS := -lbpf -lelf -lz

.DEFAULT_GOAL := all

all: $(SCHED_BIN) $(WORKLOAD_BIN) $(SLEEP_WAKE_BIN) $(CHILD_BIN)

$(INCLUDE_DIR):
	mkdir -p $@

$(BUILD_DIR):
	mkdir -p $@

$(BUILD_DIR)/bin:
	mkdir -p $@

$(INCLUDE_DIR)/vmlinux.h: $(VMLINUX_BTF) | $(INCLUDE_DIR)
	$(BPFTOOL) btf dump file $< format c > $@

$(BPF_OBJ): src/llama_scx_simple.bpf.c include/llama_instrumentation.h include/llama_phase.h $(INCLUDE_DIR)/vmlinux.h | $(BUILD_DIR)
	$(CLANG) $(BPF_CFLAGS) -c $< -o $@

$(SCHED_BIN): src/llama_scx_simple.c include/llama_instrumentation.h include/llama_phase.h include/llama_sched_uapi.h $(BPF_OBJ) | $(BUILD_DIR)/bin
	$(CC) $(USER_CFLAGS) $< -o $@ $(USER_LDLIBS)

$(WORKLOAD_BIN): tests/cpu_burn.c include/llama_sched_uapi.h | validate-kernel-sched-uapi $(BUILD_DIR)/bin
	$(CC) $(USER_CFLAGS) $< -o $@

$(SLEEP_WAKE_BIN): tests/sleep_wake.c | $(BUILD_DIR)/bin
	$(CC) $(USER_CFLAGS) $< -o $@

$(CHILD_BIN): src/llama_scx_child.c include/llama_sched_uapi.h | validate-kernel-sched-uapi $(BUILD_DIR)/bin
	$(CC) $(USER_CFLAGS) $< -o $@

check: all check-scx-api check-sched-uapi
	$(WORKLOAD_BIN) --seconds 1
	$(SLEEP_WAKE_BIN) --seconds 1 --interval-ms 100
	sh tests/test_scx_child.sh $(CHILD_BIN) $(WORKLOAD_BIN)
	python3 tests/test_validation.py $(CHILD_BIN) $(WORKLOAD_BIN) $(SLEEP_WAKE_BIN)
	python3 tests/test_instrumentation.py
	python3 tests/test_m11.py
	python3 tests/test_m11r.py

check-scx-api:
	@awk '$$1 == "bool" && $$2 ~ /^scx_bpf_dsq_insert\(/ { exit 1 } $$1 == "void" && $$2 ~ /^scx_bpf_dsq_insert\(/ { found = 1 } END { exit found ? 0 : 1 }' src/llama_scx_simple.bpf.c
	@! rg -n '__scx_bpf_dsq_insert_vtime' src/llama_scx_simple.bpf.c

validate-kernel-sched-uapi:
	@test -f "$(KERNEL_SCHED_UAPI)" || { \
		printf 'error: selected kernel UAPI header not found: %s\n' "$(KERNEL_SCHED_UAPI)" >&2; \
		exit 1; \
	}
	@awk '$$1 == "#define" && $$2 == "SCHED_EXT" && $$3 == "7" { found = 1 } \
		END { if (!found) { printf "error: %s does not define SCHED_EXT as policy 7\n", ARGV[1] > "/dev/stderr"; exit 1 } }' \
		"$(KERNEL_SCHED_UAPI)"

check-sched-uapi: validate-kernel-sched-uapi
	@printf '%s\n' '#include "llama_sched_uapi.h"' 'int main(void) { return 0; }' | $(CC) $(USER_CFLAGS) -x c -fsyntax-only -

clean:
	rm -rf $(BUILD_DIR)

.PHONY: all check check-scx-api check-sched-uapi validate-kernel-sched-uapi clean
