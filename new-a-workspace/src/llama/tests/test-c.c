#include "llama.h"

int main(void) {
    struct llama_decode_options options = llama_decode_default_options();
    enum llama_compute_profile profile = options.compute_profile;
    int32_t (*decode_with_options)(struct llama_context *, struct llama_batch, struct llama_decode_options) = llama_decode_with_options;

    (void) profile;
    (void) decode_with_options;
}
