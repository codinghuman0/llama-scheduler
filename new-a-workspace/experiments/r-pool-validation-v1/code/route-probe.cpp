#include <array>
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstdint>
#include <dlfcn.h>
#include <algorithm>
extern "C" void ggml_gemm_q4_K_8x8_q8_K(int, float *, size_t, const void *, const void *, int, int);
extern "C" void ggml_backend_cpu_newa_phase(uint32_t);
extern "C" uint32_t ggml_backend_cpu_newa_phase_current(void);
int main() {
    alignas(64) std::array<unsigned char,16384> weights{};
    alignas(64) std::array<unsigned char,16384> inputs{};
    std::array<float,256> output{};
    const int phases[]={0,1,1,2,2,2,2,3,3,3,3};
    const int rows[]={32,32,4,4,8,12,16,4,8,12,16};
    for (size_t i=0;i<sizeof(phases)/sizeof(phases[0]);++i) {
        ggml_backend_cpu_newa_phase(phases[i]);
        assert(ggml_backend_cpu_newa_phase_current()==uint32_t(phases[i]));
        std::fill(output.begin(),output.end(),1.0f);
        ggml_gemm_q4_K_8x8_q8_K(256,output.data(),8,weights.data(),inputs.data(),rows[i],8);
        for (int j=0;j<rows[i]*8;++j) assert(std::isfinite(output[j]) && output[j]==0.0f);
        std::printf("phase=%d nr=%d zero_buffer_output=PASS\n",phases[i],rows[i]);
    }
    std::puts("Route probe complete; counters, not zero buffers, prove branch selection.");
}
