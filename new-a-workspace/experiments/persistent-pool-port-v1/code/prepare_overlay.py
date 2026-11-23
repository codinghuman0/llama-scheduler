from pathlib import Path
import difflib,hashlib,json,shutil
D=Path(__file__).resolve().parents[1];W=D.parents[1];S=W/'src/llama'
p=D/'overlay/tools/server';p.mkdir(parents=True,exist_ok=True)
header=(D/'donor/pool-header.txt').read_text();(p/'server-threadpool.h').write_text(header)
old=(S/'tools/server/server-context.cpp').read_text();new=old
new=new.replace('#include "server-scx.h"','#include "server-scx.h"\n#include "server-threadpool.h"',1)
new=new.replace('    common_init_result_ptr llama_init;','    server_threadpools newa_donor_pools;\n    common_init_result_ptr llama_init;',1)
new=new.replace('    void destroy() {\n        if (newa_pool)', '    void destroy() {\n        if (ctx_tgt && newa_donor_pools.normal) {\n            llama_synchronize(ctx_tgt);\n            llama_detach_threadpool(ctx_tgt);\n        }\n        if (newa_pool)',1)
new=new.replace('        llama_init.reset();\n\n        ctx_tgt = nullptr;', '        llama_init.reset();\n        newa_donor_pools.reset();\n\n        ctx_tgt = nullptr;',1)
anchor='''        const char * pool_mode = std::getenv("GGML_NEWA_POOL");
        if (pool_mode && std::strcmp(pool_mode, "off") != 0) {'''
replacement='''        const char * pool_mode = std::getenv("GGML_NEWA_POOL");
        if (pool_mode && std::strcmp(pool_mode, "donor") == 0) {
            const auto unrestricted = [](const common_cpu_params & cpu) {
                return !cpu.mask_valid && !cpu.strict_cpu && cpu.priority == GGML_SCHED_PRIO_NORMAL && cpu.poll == 50;
            };
            if (params_base.n_gpu_layers != 0 || !params_base.tensor_buft_overrides.empty() ||
                    has_mmproj || has_spec || scx_has_spec || params_base.embedding ||
                    llama_model_has_encoder(model_tgt) || !llama_model_has_decoder(model_tgt) ||
                    !unrestricted(params_base.cpuparams) || !unrestricted(params_base.cpuparams_batch) ||
                    params_base.cpuparams.n_threads != 5 || params_base.cpuparams_batch.n_threads != 6) {
                SRV_ERR("%s", "donor pool candidate requires CPU decoder, threads5/6, normal priority, poll50 and unrestricted roles\\n");
                return false;
            }
            auto * dev = ggml_backend_dev_by_type(GGML_BACKEND_DEVICE_TYPE_CPU);
            auto * reg = dev ? ggml_backend_dev_backend_reg(dev) : nullptr;
            if (!newa_donor_pools.init(reg, params_base.cpuparams, params_base.cpuparams_batch)) {
                return false;
            }
            llama_attach_threadpool(ctx_tgt, newa_donor_pools.normal, newa_donor_pools.batch);
        } else if (pool_mode && std::strcmp(pool_mode, "off") != 0) {'''
assert new.count(anchor)==1;new=new.replace(anchor,replacement)
assert new.count('newa_donor_pools.reset()')==1
(p/'server-context.cpp').write_text(new)
patch=''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/tools/server/server-context.cpp',tofile='b/tools/server/server-context.cpp'))
patch+=''.join(difflib.unified_diff([],header.splitlines(True),fromfile='/dev/null',tofile='b/tools/server/server-threadpool.h'))
(D/'method.patch').write_text(patch)
test=(D/'donor/pool-test.txt').read_text().replace('#include "../tools/server/server-threadpool.h"','#include "server-threadpool.h"').replace('#include "../ggml/src/ggml-backend-impl.h"','#include "ggml-backend-impl.h"')
# Forwarding cases retain mock-only priorities/masks; real graph runs use normal/unrestricted 5/6, poll50.
start=test.index('static void test_graph_reuse')
test=test[:start]+test[start:].replace('cpu.n_threads = 2;','cpu.n_threads = 5;').replace('cpu.poll = 0;','cpu.poll = 50;').replace('separate ? 3 : 2','separate ? 6 : 5')
test=test.replace('    test_parameters_and_failures();','    test_parameters_and_failures();\n    std::puts("PASS parameters, paused creation, capability failures, allocation failures, retry/reset");')
test=test.replace('    test_graph_reuse(dev, true);','    test_graph_reuse(dev, true);\n    std::puts("PASS shared/separate graphs, abort recovery, ownership cycles (OpenMP5/6, poll50)");')
(D/'tests/test-server-threadpool.cpp').write_text(test)
(D/'test-adaptation.patch').write_text(''.join(difflib.unified_diff((D/'donor/pool-test.txt').read_text().splitlines(True),test.splitlines(True),fromfile='donor/test-server-threadpool.cpp',tofile='local/test-server-threadpool.cpp')))
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
protected=['tools/server/newa-prefill-pressure.h','tools/server/server-scx.h','ggml/src/ggml-cpu/ggml-cpu.c','ggml/src/ggml-cpu/ggml-cpu.cpp','src/llama-context.cpp','common/sampling.cpp']
(D/'overlay-identity.json').write_text(json.dumps({'status':'PREPARED_MODEL_GATE_PENDING','base_server_sha256':sha(S/'tools/server/server-context.cpp'),'candidate_server_sha256':sha(p/'server-context.cpp'),'donor_header_sha256':sha(p/'server-threadpool.h'),'unchanged_components':{x:sha(S/x) for x in protected},'env_toggle':'GGML_NEWA_POOL=donor (off/on preserved)','build_parent':'Current E server source only for model-free review; not R and not admitted to model pilot. Rebase on approved R before model work.'},indent=2)+'\n')
print('Prepared minimal context overlay and unchanged donor pool owner; original source untouched.')
