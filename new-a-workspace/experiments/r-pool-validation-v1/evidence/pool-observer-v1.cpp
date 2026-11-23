#include "ggml-cpu.h"
#include <cstdio>
#include <cstdlib>
#include <dlfcn.h>
#include <mutex>
#include <cstdint>
static std::mutex trace_mutex;
static uint64_t serial=0;
template<class T> T next(const char * name) {
    void * value=dlsym(RTLD_NEXT,name);
    if (!value) { std::fprintf(stderr,"POOL_OBSERVER missing %s\n",name); std::abort(); }
    return reinterpret_cast<T>(value);
}
static void emit(const char * event,void * pool,int requested,int actual,int status,int poll=-1,int priority=-1,int paused=-1,int masked=-1) {
    std::lock_guard<std::mutex> lock(trace_mutex);
    const char * output=std::getenv("NEWA_POOL_DIAG_OUTPUT");
    const char * role_path=std::getenv("NEWA_POOL_DIAG_ROLE");
    if (!output || !role_path) std::abort();
    char role[64]="startup";
    if (FILE * f=std::fopen(role_path,"r")) { if (std::fscanf(f,"%63s",role)!=1) role[0]=0; std::fclose(f); }
    FILE * f=std::fopen(output,"a"); if (!f) std::abort();
    std::fprintf(f,"{\"serial\":%llu,\"event\":\"%s\",\"role\":\"%s\",\"pool\":\"%p\",\"requested_threads\":%d,\"pool_threads\":%d,\"status\":%d,\"poll\":%d,\"priority\":%d,\"paused\":%d,\"masked\":%d}\n",(unsigned long long)++serial,event,role,pool,requested,actual,status,poll,priority,paused,masked);
    std::fclose(f);
}
extern "C" struct ggml_threadpool * ggml_threadpool_new(struct ggml_threadpool_params * p) {
    auto * result=next<decltype(&ggml_threadpool_new)>("ggml_threadpool_new")(p);
    int masked=0; for (bool cpu:p->cpumask) masked+=cpu;
    emit("new_api",result,p->n_threads,p->n_threads,result?0:-1,p->poll,p->prio,p->paused,masked);
    return result;
}
extern "C" void ggml_threadpool_free(struct ggml_threadpool * p) {
    emit("free",p,-1,-1,0);
    next<decltype(&ggml_threadpool_free)>("ggml_threadpool_free")(p);
}
extern "C" enum ggml_status ggml_graph_compute(struct ggml_cgraph * graph,struct ggml_cplan * plan) {
    auto * pool=plan->threadpool;
    int actual=pool?next<decltype(&ggml_threadpool_get_n_threads)>("ggml_threadpool_get_n_threads")(pool):0;
    emit("graph_begin",pool,plan->n_threads,actual,0);
    auto result=next<decltype(&ggml_graph_compute)>("ggml_graph_compute")(graph,plan);
    emit("graph_end",pool,plan->n_threads,actual,int(result));
    return result;
}
