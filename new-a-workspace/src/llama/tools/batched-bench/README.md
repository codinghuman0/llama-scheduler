# llama.cpp/example/batched-bench

Benchmark the batched decoding performance of `llama.cpp`

## Usage

There are 2 modes of operation:

- `prompt not shared` - each batch has a separate prompt of size `PP` (i.e. `N_KV = B*(PP + TG)`)
- `prompt is shared` - there is a common prompt of size `PP` used by all batches (i.e. `N_KV = PP + B*TG`)

```bash
./llama-batched-bench -m model.gguf -c 2048 -b 2048 -ub 512 -npp 128,256,512 -ntg 128,256 -npl 1,2,4,8,16,32 [-pps] --pp-compute-profile auto --tg-compute-profile auto

# LLaMA 7B, F16, N_KV_MAX = 16384 (8GB), prompt not shared
./llama-batched-bench -m ./models/llama-7b/ggml-model-f16.gguf -c 16384 -b 2048 -ub 512 -ngl 99

# LLaMA 7B, Q8_0, N_KV_MAX = 16384 (8GB), prompt is shared
./llama-batched-bench -m ./models/llama-7b/ggml-model-q8_0.gguf -c 16384 -b 2048 -ub 512 -ngl 99 -pps

# custom set of batches
./llama-batched-bench -m ./models/llama-7b/ggml-model-q8_0.gguf -c 2048 -b 512 -ub 512 -ngl 999 -npp 128,256,512 -ntg 128,256 -npl 1,2,4,8,16,32
```

### Compute profiles

- `--pp-compute-profile {auto,generation,batch}` selects the resource profile for measured prompt processing. The default is `auto`.
- `--tg-compute-profile {auto,generation,batch}` selects the resource profile for measured text generation. The default is `auto`.

`auto` preserves the original llama.cpp behavior. The `generation` profile forces `n_threads` and the normal threadpool, while the `batch` profile forces `n_threads_batch` and the batch threadpool. These names select resource profiles; they do not describe or detect the semantic contents of a batch. The benchmark does not detect workload phases. The user explicitly assigns one profile to measured PP and one to measured TG.

The selected PP or TG profile is passed to every corresponding `llama_decode_with_options()` call. One selected profile applies to all physical ubatches produced by each call.

```bash
# Existing behavior
./llama-batched-bench \
    -m model.gguf \
    -c 2048 \
    -b 2048 \
    -ub 512 \
    -npp 1024 \
    -ntg 128 \
    -npl 1,2,4,8 \
    --pp-compute-profile auto \
    --tg-compute-profile auto

# Explicit PP/TG resource profiles
./llama-batched-bench \
    -m model.gguf \
    -c 2048 \
    -b 2048 \
    -ub 512 \
    -npp 1024 \
    -ntg 128 \
    -npl 1,2,4,8 \
    --pp-compute-profile batch \
    --tg-compute-profile generation
```

## Sample results

- `PP` - prompt tokens per batch
- `TG` - generated tokens per batch
- `B` - number of batches
- `N_KV` - required KV cache size
- `T_PP` - prompt processing time (i.e. time to first token)
- `S_PP` - prompt processing speed (`(B*PP)/T_PP` or `PP/T_PP`)
- `T_TG` - time to generate all batches
- `S_TG` - text generation speed (`(B*TG)/T_TG`)
- `T` - total time
- `S` - total speed (i.e. all tokens / total time)
- `PP_PROFILE` - requested compute profile for measured prompt processing
- `TG_PROFILE` - requested compute profile for measured text generation

|    PP |     TG |    B |   N_KV |   T_PP s | S_PP t/s |   T_TG s | S_TG t/s |      T s |    S t/s | PP_PROFILE | TG_PROFILE |
|-------|--------|------|--------|----------|----------|----------|----------|----------|----------|------------|------------|
|   128 |    128 |    1 |    256 |    0.108 |  1186.64 |    3.079 |    41.57 |    3.187 |    80.32 | auto       | auto       |
|   128 |    128 |    2 |    512 |    0.198 |  1295.19 |    5.029 |    50.90 |    5.227 |    97.95 | auto       | auto       |
|   128 |    128 |    4 |   1024 |    0.373 |  1373.96 |    6.878 |    74.44 |    7.251 |   141.23 | auto       | auto       |
|   128 |    128 |    8 |   2048 |    0.751 |  1363.27 |    7.344 |   139.43 |    8.095 |   252.99 | auto       | auto       |
|   128 |    128 |   16 |   4096 |    1.570 |  1304.68 |    8.455 |   242.23 |   10.024 |   408.60 | auto       | auto       |
|   128 |    128 |   32 |   8192 |    3.408 |  1201.73 |    8.801 |   465.40 |   12.209 |   670.96 | auto       | auto       |
|   128 |    256 |    1 |    384 |    0.107 |  1196.70 |    6.329 |    40.45 |    6.436 |    59.67 | auto       | auto       |
|   128 |    256 |    2 |    768 |    0.194 |  1317.45 |   10.239 |    50.00 |   10.433 |    73.61 | auto       | auto       |
|   128 |    256 |    4 |   1536 |    0.366 |  1399.03 |   13.960 |    73.35 |   14.326 |   107.22 | auto       | auto       |
|   128 |    256 |    8 |   3072 |    0.751 |  1363.92 |   15.110 |   135.54 |   15.861 |   193.69 | auto       | auto       |
|   128 |    256 |   16 |   6144 |    1.569 |  1304.93 |   18.073 |   226.64 |   19.642 |   312.80 | auto       | auto       |
|   128 |    256 |   32 |  12288 |    3.409 |  1201.35 |   19.223 |   426.15 |   22.633 |   542.93 | auto       | auto       |

### JSONL output

Pass `--output-format jsonl` to output JSONL instead of Markdown, á la

```json lines
{"n_kv_max": 2048, "n_batch": 2048, "n_ubatch": 512, "flash_attn": 0, "is_pp_shared": 0, "n_gpu_layers": 99, "n_threads": 8, "n_threads_batch": 8, "pp": 128, "tg": 128, "pl": 1, "n_kv": 256, "t_pp": 0.233810, "speed_pp": 547.453064, "t_tg": 3.503684, "speed_tg": 36.532974, "t": 3.737494, "speed": 68.495094, "pp_compute_profile": "auto", "tg_compute_profile": "auto"}
{"n_kv_max": 2048, "n_batch": 2048, "n_ubatch": 512, "flash_attn": 0, "is_pp_shared": 0, "n_gpu_layers": 99, "n_threads": 8, "n_threads_batch": 8, "pp": 128, "tg": 128, "pl": 2, "n_kv": 512, "t_pp": 0.422602, "speed_pp": 605.770935, "t_tg": 11.106112, "speed_tg": 23.050371, "t": 11.528713, "speed": 44.410854, "pp_compute_profile": "auto", "tg_compute_profile": "auto"}
```
