#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
[[ $(id -u) != 0 ]] || { echo 'Run as ordinary user.' >&2; exit 2; }
exec 9<"$root/state/.measurement.lock"
flock -n 9
[[ $(cat /sys/kernel/sched_ext/state) == disabled ]] || exit 2
build_dir="$root/build"
[[ ! -e "$build_dir" ]] || { echo 'build/ exists; use a fresh directory after reviewing its contents.' >&2; exit 2; }
cmake -S "$root/src/llama" -B "$build_dir" -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=ON -DGGML_NATIVE=ON -DGGML_OPENMP=ON -DGGML_CUDA=OFF -DGGML_VULKAN=OFF -DGGML_HIP=OFF -DGGML_SYCL=OFF -DGGML_METAL=OFF -DGGML_RPC=OFF -DLLAMA_SCX_PHASE_HINT=ON -DLLAMA_SCX_PHASE_TRACE=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_UI=OFF -DLLAMA_USE_PREBUILT_UI=OFF -DLLAMA_CURL=OFF
cmake --build "$build_dir" --target llama-server -j "${BUILD_JOBS:-2}"
echo "New build: $build_dir/bin (frozen runtime/ remains untouched; validate outputs before benchmarking)."
