# SPDX-License-Identifier: GPL-2.0
# Build only. Loading and runtime validation are separate operations.
CLANG ?= clang
CC ?= cc
BPFTOOL ?= bpftool

KERNEL_RELEASE ?= $(shell uname -r)
KERNEL_HEADERS ?= /lib/modules/$(KERNEL_RELEASE)/build
KERNEL_SCHED_UAPI := $(KERNEL_HEADERS)/include/uapi/linux/sched.h
VMLINUX_BTF ?= /sys/kernel/btf/vmlinux

BUILD_DIR := build
VMLINUX := $(BUILD_DIR)/include/vmlinux.h
BPF_OBJ := $(BUILD_DIR)/llama_scx.bpf.o
LOADER := $(BUILD_DIR)/bin/llama_scx
CHILD := $(BUILD_DIR)/bin/llama_scx_child

BPF_CFLAGS := -target bpf -D__TARGET_ARCH_x86 -O2 -g -Wall -Werror \
	-I$(BUILD_DIR)/include -Iinclude -I/usr/include/$(shell $(CC) -dumpmachine)
USER_CFLAGS := -O2 -g -Wall -Wextra -Werror -std=gnu11 -Iinclude
USER_LDLIBS := -lbpf -lelf -lz

.DEFAULT_GOAL := all
all: $(BPF_OBJ) $(LOADER) $(CHILD)

$(BUILD_DIR)/include $(BUILD_DIR)/bin:
	mkdir -p $@

$(VMLINUX): $(VMLINUX_BTF) | $(BUILD_DIR)/include
	$(BPFTOOL) btf dump file $< format c > $@.tmp
	mv $@.tmp $@

$(BPF_OBJ): llama_scx.bpf.c include/llama_scx_state.h $(VMLINUX)
	$(CLANG) $(BPF_CFLAGS) -c $< -o $@

$(LOADER): llama_scx.c include/llama_scx_state.h include/llama_sched_uapi.h $(BPF_OBJ) | validate-kernel-sched-uapi $(BUILD_DIR)/bin
	$(CC) $(USER_CFLAGS) -DBPF_OBJECT_PATH='"$(abspath $(BPF_OBJ))"' $< -o $@ $(USER_LDLIBS)

$(CHILD): llama_scx_child.c include/llama_sched_uapi.h | validate-kernel-sched-uapi $(BUILD_DIR)/bin
	$(CC) $(USER_CFLAGS) $< -o $@

validate-kernel-sched-uapi:
	@test -f "$(KERNEL_SCHED_UAPI)" || { \
		printf 'error: matching kernel UAPI header not found: %s\n' "$(KERNEL_SCHED_UAPI)" >&2; exit 1; \
	}
	@awk '$$1 == "#define" && $$2 == "SCHED_EXT" && $$3 == "7" { found = 1 } \
		END { if (!found) { printf "error: %s does not define SCHED_EXT as 7\n", ARGV[1] > "/dev/stderr"; exit 1 } }' "$(KERNEL_SCHED_UAPI)"

clean:
	rm -rf -- $(BUILD_DIR)

.PHONY: all clean validate-kernel-sched-uapi
