#include "llama.h"

#include "../src/llama-context.h"

int main() {
    const auto options = llama_decode_default_options();
    GGML_ASSERT(options.compute_profile == LLAMA_COMPUTE_PROFILE_AUTO);

    GGML_ASSERT(llama_compute_profile_resolve(LLAMA_COMPUTE_PROFILE_AUTO,       1) == LLAMA_COMPUTE_PROFILE_GENERATION);
    GGML_ASSERT(llama_compute_profile_resolve(LLAMA_COMPUTE_PROFILE_AUTO,       2) == LLAMA_COMPUTE_PROFILE_BATCH);
    GGML_ASSERT(llama_compute_profile_resolve(LLAMA_COMPUTE_PROFILE_GENERATION, 1) == LLAMA_COMPUTE_PROFILE_GENERATION);
    GGML_ASSERT(llama_compute_profile_resolve(LLAMA_COMPUTE_PROFILE_GENERATION, 8) == LLAMA_COMPUTE_PROFILE_GENERATION);
    GGML_ASSERT(llama_compute_profile_resolve(LLAMA_COMPUTE_PROFILE_BATCH,      1) == LLAMA_COMPUTE_PROFILE_BATCH);
    GGML_ASSERT(llama_compute_profile_resolve(LLAMA_COMPUTE_PROFILE_BATCH,      8) == LLAMA_COMPUTE_PROFILE_BATCH);

    llama_decode_options invalid_options = options;
    invalid_options.compute_profile = (llama_compute_profile) -1;

    GGML_ASSERT(!llama_compute_profile_is_valid(invalid_options.compute_profile));
    GGML_ASSERT(llama_decode_with_options(nullptr, {}, invalid_options) == -1);
}
