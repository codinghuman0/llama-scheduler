#define _GNU_SOURCE
#include <assert.h>
#include <dirent.h>
#include <dlfcn.h>
#include <errno.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>

#include "ggml-cpu.h"

static unsigned fail_alloc_at;
static unsigned fail_thread_at;
static int (*real_alloc)(void **, size_t, size_t);
static int (*real_create)(pthread_t *, const pthread_attr_t *, void * (*)(void *), void *);

// The test executable alone intercepts the DSO calls. The runtime carries no test hooks.
int posix_memalign(void ** ptr, size_t align, size_t size) {
    if (fail_alloc_at && --fail_alloc_at == 0) {
        return ENOMEM;
    }
    return real_alloc(ptr, align, size);
}

int pthread_create(pthread_t * thread, const pthread_attr_t * attr,
                   void * (* start)(void *), void * arg) {
    if (fail_thread_at && --fail_thread_at == 0) {
        return EAGAIN;
    }
    return real_create(thread, attr, start, arg);
}

static unsigned tasks(void) {
    DIR * dir = opendir("/proc/self/task");
    assert(dir);
    unsigned count = 0;
    for (struct dirent * entry; (entry = readdir(dir)); ) {
        count += entry->d_name[0] != '.';
    }
    assert(closedir(dir) == 0);
    return count;
}

int main(void) {
    real_alloc = dlsym(RTLD_NEXT, "posix_memalign");
    real_create = dlsym(RTLD_NEXT, "pthread_create");
    assert(real_alloc && real_create);

    struct ggml_threadpool_params params = ggml_threadpool_params_default(3);
    params.paused = true;
    params.poll = 0;
    const unsigned initial_tasks = tasks();

    for (unsigned i = 1; i <= 2; i++) {
        fail_alloc_at = i;
        assert(!ggml_threadpool_new(&params));
        assert(!fail_alloc_at && tasks() == initial_tasks);
    }
    fail_thread_at = 2;
    assert(!ggml_threadpool_new(&params));
    assert(!fail_thread_at && tasks() == initial_tasks);

    struct ggml_threadpool * recovered = ggml_threadpool_new(&params);
    assert(recovered && tasks() == initial_tasks + 2);
    ggml_threadpool_free(recovered);
    assert(tasks() == initial_tasks);
    puts("Both allocation failures and second worker failure unwound; clean pool retry PASS");
    return 0;
}
