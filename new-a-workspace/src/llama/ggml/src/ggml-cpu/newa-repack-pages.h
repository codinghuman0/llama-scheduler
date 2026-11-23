// SPDX-License-Identifier: MIT
#pragma once
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <cstdio>
#include <cerrno>
#if defined(__linux__)
#include <sys/mman.h>
#include <unistd.h>
#endif

static void newa_repack_pages(void * data, size_t size) {
    const char * mode = std::getenv("GGML_NEWA_REPACK_PAGES");
    if (!mode) mode = "off";
    GGML_ASSERT(std::strcmp(mode, "off") == 0 || std::strcmp(mode, "huge") == 0);
    if (size < 2 * 1024 * 1024) return;
#if defined(__linux__)
    const long page_size = sysconf(_SC_PAGESIZE);
    GGML_ASSERT(page_size > 0);
    const uintptr_t page = (uintptr_t) page_size;
    const uintptr_t begin = (uintptr_t) data;
    GGML_ASSERT(size <= UINTPTR_MAX - begin);
    const uintptr_t end = begin + size;
    const uintptr_t first = begin + (page - begin % page) % page;
    const uintptr_t last = end - end % page;
    GGML_ASSERT(last > first);
    int rc = 0, error = 0;
    if (std::strcmp(mode, "huge") == 0) {
        rc = madvise((void *) first, last - first, MADV_HUGEPAGE);
        if (rc != 0) error = errno;
    }
    std::fprintf(stderr, "NEWA_REPACK_PAGES mode=%s base=%llu size=%zu first=%llu length=%llu rc=%d errno=%d\n",
                 mode, (unsigned long long) begin, size, (unsigned long long) first,
                 (unsigned long long) (last - first), rc, error);
#else
    GGML_ASSERT(std::strcmp(mode, "off") == 0);
#endif
}
