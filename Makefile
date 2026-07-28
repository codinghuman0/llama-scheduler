# SPDX-License-Identifier: GPL-2.0
# Build the non-privileged sched_ext baseline. Nothing here loads BPF.

CLANG ?= clang
CC ?= cc
BPFTOOL ?= bpftool

BUILD_DIR := build
INCLUDE_DIR := $(BUILD_DIR)/include
BPF_OBJ := $(BUILD_DIR)/llama_scx_simple.bpf.o
SCHED_BIN := $(BUILD_DIR)/bin/llama_scx_simple
WORKLOAD_BIN := $(BUILD_DIR)/bin/cpu_burn
VMLINUX_BTF ?= /sys/kernel/btf/vmlinux

ARCH := x86
BPF_CFLAGS := -target bpf -D__TARGET_ARCH_$(ARCH) -O2 -g -Wall -Werror \
	-Wno-missing-declarations \
	-I$(INCLUDE_DIR) -I/usr/include/$(shell $(CC) -dumpmachine)
USER_CFLAGS := -O2 -g -Wall -Wextra -Werror -std=gnu11 -I$(INCLUDE_DIR)
USER_LDLIBS := -lbpf -lelf -lz

.DEFAULT_GOAL := all

all: $(SCHED_BIN) $(WORKLOAD_BIN)

$(INCLUDE_DIR):
	mkdir -p $@

$(BUILD_DIR):
	mkdir -p $@

$(BUILD_DIR)/bin:
	mkdir -p $@

$(INCLUDE_DIR)/vmlinux.h: $(VMLINUX_BTF) | $(INCLUDE_DIR)
	$(BPFTOOL) btf dump file $< format c > $@

$(BPF_OBJ): src/llama_scx_simple.bpf.c $(INCLUDE_DIR)/vmlinux.h | $(BUILD_DIR)
	$(CLANG) $(BPF_CFLAGS) -c $< -o $@

$(SCHED_BIN): src/llama_scx_simple.c $(BPF_OBJ) | $(BUILD_DIR)/bin
	$(CC) $(USER_CFLAGS) $< -o $@ $(USER_LDLIBS)

$(WORKLOAD_BIN): tests/cpu_burn.c | $(BUILD_DIR)/bin
	$(CC) $(USER_CFLAGS) $< -o $@

check: all
	$(WORKLOAD_BIN) --seconds 1

clean:
	rm -rf $(BUILD_DIR)

.PHONY: all check clean
