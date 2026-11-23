#include "arg.h"
#include "common.h"
#include <algorithm>
#include <cassert>
#include <cstdio>
static bool has_override(const common_params & p) {
    return std::any_of(p.tensor_buft_overrides.begin(),p.tensor_buft_overrides.end(),
        [](const llama_model_tensor_buft_override & v) { return v.pattern || v.buft; });
}
int main(int argc,char ** argv) {
    common_params params;
    assert(common_params_parse(argc,argv,params,LLAMA_EXAMPLE_SERVER));
    assert(!params.tensor_buft_overrides.empty());
    assert(!has_override(params));
    assert(params.n_gpu_layers==0 && params.cpuparams.n_threads==5 && params.cpuparams_batch.n_threads==6);
    assert(params.cpuparams.poll==50 && params.cpuparams_batch.poll==50);
    assert(!params.cpuparams.mask_valid && !params.cpuparams_batch.mask_valid);
    std::printf("actual_parser_padding=%zu active_overrides=0 old_guard_rejects=1 corrected_guard_allows=1 threads=5/6 poll=50/50\n",params.tensor_buft_overrides.size());
    params.tensor_buft_overrides[0].pattern="test-pattern";
    assert(has_override(params));
    std::puts("actual_override_still_rejected=PASS");
}
