#include "llama.h"
#include "llama-batch.h"
#include "json.hpp"
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <dlfcn.h>
#include <fstream>
#include <map>
#include <numeric>
#include <random>
#include <sstream>
#include <string>
#include <vector>
#include "sampler-layout.h"
using json = nlohmann::ordered_json;
struct common_sampler;
template<class F> static F next(const char * name) {
    void * p = dlsym(RTLD_NEXT, name);
    if (!p) { std::fprintf(stderr, "DIAG missing symbol %s\n", name); std::abort(); }
    return reinterpret_cast<F>(p);
}
static json cfg;
static std::string outdir, role_path;
static std::ofstream events;
static int call_id = 0, semantic_phase = -1;
static bool active = false;
static thread_local int nesting = 0;
static thread_local bool trace_sampler = false;
static thread_local int sample_req = -1, sample_gen = -1;
static std::vector<std::vector<int>> prompts, forced;
static std::map<int,std::vector<int>> history;
static std::map<int,int> request_of_seq;
struct input_row { int token, pos, seq, output; };
static std::vector<input_row> batch_rows;
static bool enabled() {
    if (outdir.empty()) {
        const char * path = std::getenv("NEWA_DIAG_CONFIG");
        if (!path) return false;
        std::ifstream f(path); f >> cfg;
        outdir = cfg.at("output"); role_path = cfg.at("role_file");
        prompts = cfg.at("prompts").get<std::vector<std::vector<int>>>();
        forced = cfg.at("forced_tokens").get<std::vector<std::vector<int>>>();
        events.open(outdir + "/events.jsonl", std::ios::out | std::ios::app);
        if (!events) std::abort();
    }
    std::ifstream role(role_path); std::string value; role >> value;
    active = value == "measured";
    return active;
}
static void emit(json j) { j["call"] = call_id; events << j.dump() << '\n'; events.flush(); }
static int identify(int seq) {
    const auto & h = history.at(seq); int found = -1;
    for (size_t i = 0; i < prompts.size(); ++i) {
        const auto & p = prompts[i]; const size_t n = std::min(p.size(),h.size());
        if (n && std::equal(h.begin(),h.begin()+n,p.begin())) {
            if (found != -1) return -1;
            found = int(i);
        }
    }
    return found;
}
static json kv(llama_context * ctx) {
    auto mem = next<decltype(&llama_get_memory)>("llama_get_memory")(ctx); json rows=json::array();
    for (int s=0; s<8; ++s) rows.push_back({{"seq",s},{"min",next<decltype(&llama_memory_seq_pos_min)>("llama_memory_seq_pos_min")(mem,s)},{"max",next<decltype(&llama_memory_seq_pos_max)>("llama_memory_seq_pos_max")(mem,s)}});
    return rows;
}
static void before_decode(llama_context * ctx, const llama_batch & b, int profile) {
    if (!enabled()) return;
    ++call_id; batch_rows.clear(); json tokens=json::array();
    if (!b.token || !b.pos || !b.seq_id || !b.n_seq_id) std::abort();
    for (int i=0;i<b.n_tokens;++i) {
        if (b.n_seq_id[i]!=1) std::abort();
        int s=b.seq_id[i][0],pos=b.pos[i]; auto & h=history[s];
        if (pos==0) { h.clear();request_of_seq.erase(s); }
        if (pos<0 || size_t(pos)>h.size()) std::abort();
        if (size_t(pos)==h.size()) h.push_back(b.token[i]); else h[pos]=b.token[i];
        int req=identify(s); if(req>=0) request_of_seq[s]=req;
        int output=b.logits ? b.logits[i] : i==b.n_tokens-1;
        batch_rows.push_back({b.token[i],pos,s,output});
        tokens.push_back({{"token",b.token[i]},{"pos",pos},{"seq",s},{"output",output},{"request",req}});
    }
    if(call_id<=cfg.value("max_trace_calls",16)) emit({{"event","decode_begin"},{"tokens",tokens},{"semantic_marker_phase",semantic_phase},{"requested_profile",profile},{"kv_before",kv(ctx)},{"logical_token_history",history}});
}
extern "C" int32_t llama_decode(llama_context * ctx, llama_batch b) {
    bool outer=nesting++==0; if(outer)before_decode(ctx,b,-1);
    int ret=next<decltype(&llama_decode)>("llama_decode")(ctx,b);
    --nesting;if(outer&&active&&call_id<=cfg.value("max_trace_calls",16))emit({{"event","decode_end"},{"return",ret},{"kv_after",kv(ctx)}});return ret;
}
#ifdef DIAG_B1
extern "C" int32_t llama_decode_with_options(llama_context * ctx,llama_batch b,llama_decode_options options) {
    bool outer=nesting++==0;if(outer)before_decode(ctx,b,options.compute_profile);
    int ret=next<decltype(&llama_decode_with_options)>("llama_decode_with_options")(ctx,b,options);
    --nesting;if(outer&&active&&call_id<=cfg.value("max_trace_calls",16))emit({{"event","decode_end"},{"return",ret},{"kv_after",kv(ctx)}});return ret;
}
extern "C" void llama_scx_phase_v1(uint32_t p) {
    next<void(*)(uint32_t)>("llama_scx_phase_v1")(p);semantic_phase=int(p);
    if(enabled()&&call_id<=cfg.value("max_trace_calls",16))emit({{"event","marker_after_original_call"},{"phase",p}});
}
#endif
static void ubatch_record(const llama_ubatch & b,int profile) {
    if(!active||call_id>cfg.value("max_trace_calls",16))return;
    json rows=json::array();
    for(uint32_t i=0;i<b.n_tokens;++i) {
        json ids=json::array();for(int j=0;j<b.n_seq_id[i];++j)ids.push_back(b.seq_id[i][j]);
        rows.push_back({{"token",b.token?json(b.token[i]):json(nullptr)},{"pos",b.pos[i]},{"seq",ids},{"output",b.output[i]}});
    }
    emit({{"event","physical_ubatch"},{"equal_seqs",b.equal_seqs()},{"n_tokens",b.n_tokens},{"n_seq_tokens",b.n_seq_tokens},{"n_seqs",b.n_seqs},{"n_pos",b.n_pos},{"tokens",rows},{"profile",profile}});
}
#ifdef DIAG_B1
#define UBATCH_SYMBOL "_ZN13llama_context14process_ubatchERK12llama_ubatch14llm_graph_typeP22llama_memory_context_iR11ggml_status21llama_compute_profile"
extern "C" void * diag_ubatch(void *,const llama_ubatch &,int,void *,ggml_status &,llama_compute_profile) asm(UBATCH_SYMBOL);
extern "C" void * diag_ubatch(void * self,const llama_ubatch & b,int gt,void * mem,ggml_status & status,llama_compute_profile profile) { ubatch_record(b,profile);return next<decltype(&diag_ubatch)>(UBATCH_SYMBOL)(self,b,gt,mem,status,profile); }
#define GRAPH_SYMBOL "_ZN13llama_context13graph_computeEP11ggml_cgraph21llama_compute_profilej"
extern "C" ggml_status diag_graph(llama_context *,ggml_cgraph *,llama_compute_profile,uint32_t) asm(GRAPH_SYMBOL);
extern "C" ggml_status diag_graph(llama_context * ctx,ggml_cgraph * graph,llama_compute_profile p,uint32_t n) {
    bool batched=p==LLAMA_COMPUTE_PROFILE_BATCH||(p==LLAMA_COMPUTE_PROFILE_AUTO&&n>1);
#else
#define UBATCH_SYMBOL "_ZN13llama_context14process_ubatchERK12llama_ubatch14llm_graph_typeP22llama_memory_context_iR11ggml_status"
extern "C" void * diag_ubatch(void *,const llama_ubatch &,int,void *,ggml_status &) asm(UBATCH_SYMBOL);
extern "C" void * diag_ubatch(void * self,const llama_ubatch & b,int gt,void * mem,ggml_status & status) {ubatch_record(b,-1);return next<decltype(&diag_ubatch)>(UBATCH_SYMBOL)(self,b,gt,mem,status);}
#define GRAPH_SYMBOL "_ZN13llama_context13graph_computeEP11ggml_cgraphb"
extern "C" ggml_status diag_graph(llama_context *,ggml_cgraph *,bool) asm(GRAPH_SYMBOL);
extern "C" ggml_status diag_graph(llama_context * ctx,ggml_cgraph * graph,bool batched) {
#endif
    if(active&&call_id<=cfg.value("max_trace_calls",16)) {
        int threads=batched?next<decltype(&llama_n_threads_batch)>("llama_n_threads_batch")(ctx):next<decltype(&llama_n_threads)>("llama_n_threads")(ctx);
        emit({{"event","graph_profile"},{"batch_profile",batched},{"threads_requested",threads}});
    }
#ifdef DIAG_B1
    return next<decltype(&diag_graph)>(GRAPH_SYMBOL)(ctx,graph,p,n);
#else
    return next<decltype(&diag_graph)>(GRAPH_SYMBOL)(ctx,graph,batched);
#endif
}
static json top(const llama_token_data_array * data) {
    std::vector<size_t> ids(data->size);std::iota(ids.begin(),ids.end(),0);
    const size_t count=std::min<size_t>(10,ids.size());
    std::partial_sort(ids.begin(),ids.begin()+count,ids.end(),[&](size_t a,size_t b){return data->data[a].logit>data->data[b].logit;});
    json rows=json::array();for(size_t i=0;i<count;++i) { const auto & x=data->data[ids[i]];rows.push_back({{"token",x.id},{"logit",std::isfinite(x.logit)?json(x.logit):json(nullptr)},{"prob",std::isfinite(x.p)?json(x.p):json(nullptr)}}); }return rows;
}
extern "C" void llama_sampler_apply(llama_sampler * smpl,llama_token_data_array * data) {
    if(!trace_sampler||!smpl){next<decltype(&llama_sampler_apply)>("llama_sampler_apply")(smpl,data);return;}
    std::string name=next<decltype(&llama_sampler_name)>("llama_sampler_name")(smpl);json row={{"event","processor"},{"request",sample_req},{"generation",sample_gen},{"name",name},{"count_before",data->size},{"top_before",top(data)}};
    if(name=="dist") {auto * ctx=static_cast<llama_sampler_dist *>(smpl->ctx);std::ostringstream state;state<<ctx->rng;row["rng_before"]=state.str();row["seed"]=ctx->seed;row["seed_current"]=ctx->seed_cur;}
    next<decltype(&llama_sampler_apply)>("llama_sampler_apply")(smpl,data);
    row["count_after"]=data->size;row["top_after"]=top(data);row["selected_index"]=data->selected;
    if(data->selected>=0&&size_t(data->selected)<data->size)row["selected_token"]=data->data[data->selected].id;
    if(name=="dist"){auto * ctx=static_cast<llama_sampler_dist *>(smpl->ctx);std::ostringstream state;state<<ctx->rng;row["rng_after"]=state.str();}
    emit(row);
}
llama_token common_sampler_sample(common_sampler * smpl,llama_context * ctx,int idx,bool grammar_first) {
    auto original=next<decltype(&common_sampler_sample)>("_Z21common_sampler_sampleP14common_samplerP13llama_contextib");
    if(!enabled())return original(smpl,ctx,idx,grammar_first);
    if(idx<0||size_t(idx)>=batch_rows.size())std::abort();
    const auto & b=batch_rows[idx];auto it=request_of_seq.find(b.seq);if(it==request_of_seq.end())std::abort();
    const int req=it->second,gen=b.pos-int(prompts[req].size())+1;
    if(gen<0||size_t(gen)>=forced[req].size())std::abort();
    bool target=req==cfg.value("target_request",3)&&gen<=cfg.value("max_logit_generation",3);
    json row={{"event","sample"},{"request",req},{"generation",gen},{"seq",b.seq},{"pos",b.pos},{"batch_index",idx},{"semantic_marker_phase",semantic_phase},{"grammar_first",grammar_first}};
    if(target) {
        const float * logits=next<decltype(&llama_get_logits_ith)>("llama_get_logits_ith")(ctx,idx);
        const llama_model * model=next<decltype(&llama_get_model)>("llama_get_model")(ctx);
        const llama_vocab * vocab=next<decltype(&llama_model_get_vocab)>("llama_model_get_vocab")(model);
        int n=next<decltype(&llama_vocab_n_tokens)>("llama_vocab_n_tokens")(vocab);std::vector<llama_token_data> candidates(n);int finite=0;
        for(int i=0;i<n;++i){candidates[i]={i,logits[i],0};finite+=std::isfinite(logits[i]);}
        llama_token_data_array view={candidates.data(),candidates.size(),-1,false};row["raw_top"]=top(&view);row["finite_count"]=finite;row["vocab_size"]=n;
        std::string name="logits-request-"+std::to_string(req)+"-generation-"+std::to_string(gen)+".f32";std::ofstream file(outdir+"/"+name,std::ios::binary);file.write(reinterpret_cast<const char *>(logits),n*sizeof(float));row["raw_logits_file"]=name;
    }
    sample_req=req;sample_gen=gen;trace_sampler=target;
    llama_token chosen=original(smpl,ctx,idx,grammar_first);trace_sampler=false;
    llama_token returned=cfg.value("teacher_force",false)?forced[req][gen]:chosen;
    row["sampler_token"]=chosen;row["returned_token"]=returned;row["teacher_force"]=cfg.value("teacher_force",false);
    if(call_id<=cfg.value("max_trace_calls",16))emit(row);
    return returned;
}
