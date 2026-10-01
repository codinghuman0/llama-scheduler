# M11 semantic llama-server phase integration

Status: PASS. The privileged semantic end-to-end checkpoint on the validated
`7.0.0-29-generic` laptop produced 8 begin events, 8 end events, 1 PREFILL
begin, 7 DECODE begins, zero diagnostic failure counters, inactive/UNKNOWN
final state, and nonzero PREFILL/DECODE `running` observations. The accepted
report is preserved locally under `results/m11/20261001-031853/`.

M11R makes this path reproducible through `scripts/bootstrap_ubuntu.sh` and
`scripts/validate_phase.sh`. The three-terminal procedure retained below is a
historical/debug path, not the normal release workflow. Its shared `/tmp` files
must not be treated as authoritative M11R evidence.

## Fixed revisions and environment

- Scheduler worktree: intentionally dirty before M11; it was not reset, cleaned,
  stashed, or committed.
- Semantic provider: `/home/codinghuman/projects/llama.cpp-semantic` at
  `5219055a578fd741e029e81fefef6f3a5695086d`; source worktree clean.
- Historical provider: `/home/codinghuman/projects/llama.cpp`; not modified.
- Kernel: `7.0.0-29-generic`.
- GCC: 13.3.0; Clang: 18.1.3; bpftool: 7.7.0 using libbpf 1.7.
- CMake: 3.28.3. `pkg-config` and `ninja` are not installed.

The semantic server was built out of tree under
`llama-scheduler/build/llama-semantic` with
`LLAMA_SCX_PHASE_TRACE=ON`, CPU-only backends, shared libraries,
`RelWithDebInfo`, tests/examples/app disabled, and the server enabled. No
model was downloaded and no inference was run. The server target provisioned
its web UI asset even though `LLAMA_BUILD_UI=OFF`; that is a build-system
behavior, not a model download or source-tree modification.

## Semantic phase audit

The semantic fork assigns explicit values in
`tools/server/server-context.cpp:70-79`:

| Phase | Value | Meaning |
| --- | ---: | --- |
| UNKNOWN | 0 | The submitted view cannot be classified safely. |
| PREFILL | 1 | Every classified token in the view is prompt-origin. |
| DECODE | 2 | Every classified token in the view is generated-origin. |
| MIXED | 3 | The view contains both prompt- and generated-origin tokens and no unknown tokens. |

Each `server_batch::token` stores a phase field, and both token and embedding
insertion preserve it (`tools/server/server-context.cpp:117-129,163-180`).
Prompt input is inserted as PREFILL at
`tools/server/server-context.cpp:3558-3583`. Sampled tokens and speculative
draft tokens are inserted as DECODE at
`tools/server/server-context.cpp:534-565`. SCX marker mode rejects
speculative decoding, multimodal input, embeddings, nonzero GPU layers, and
non-decoder-only models at
`tools/server/server-context.cpp:1105-1116,1262-1264`.

For every submitted or retried `batch_view`, classification counts token
origins only within `[off, off + batch_view.n_tokens)`
(`tools/server/server-context.cpp:3709-3732`):

- all prompt: PREFILL;
- all generated: DECODE;
- prompt plus generated and no unknown: MIXED;
- any unknown: UNKNOWN, even if known tokens are also present;
- MIXED is not a valid token origin and aborts if stored on an individual token.

The reduction is at `tools/server/server-context.cpp:3734-3743`. Marker mode
sets `classify_phase` through the nonzero run ID, so the old physical-batch
`n_tokens > 1` heuristic is not used for phase classification. Parallel slots
and continuous batching are handled more semantically for the target batch:
generated tokens from several slots remain DECODE, and prompt/generated
co-batching becomes MIXED. This claim is limited to the server target batch and
the fork's explicit SCX restrictions; internal maintenance, encoder,
multimodal, and speculative paths are not covered.

The source flow is:

```text
server batch insertion records token origin
    -> submitted/retried view counts origins
    -> UNKNOWN/PREFILL/DECODE/MIXED reduction
    -> 80-byte marker begin
    -> llama_decode() / CPU graph work
    -> synchronized marker end
```

## Marker ABI and timing

Decode markers are declared with C linkage in
`tools/server/server-scx.h:22-35`:

```c
void llama_scx_decode_begin_v1(const server_scx_event * event);
void llama_scx_decode_end_v1(const server_scx_event * event);
```

Both definitions are `noinline`, `used`, and default-visible. The sole
argument is a System V x86-64 pointer argument to an 80-byte event:

| Offset | Width | Field |
| ---: | ---: | --- |
| 0 | 8 | version |
| 8 | 8 | run_id |
| 16 | 8 | call_id |
| 24 | 8 | retry |
| 32 | 8 | phase |
| 40 | 8 | profile |
| 48 | 8 | n_prefill |
| 56 | 8 | n_decode |
| 64 | 8 | n_unknown |
| 72 | 8 | result (signed) |

The source has a size assertion at `tools/server/server-scx.h:8-20`.
Scheduler-side size and every offset are asserted in
`include/llama_phase.h`. Version is initialized to 1 and call/retry identity,
phase, profile, counts, and result are populated at
`tools/server/server-context.cpp:3755-3792`. The loader translates all four
source phase values explicitly; it does not rely on coincident enum values.

The scope constructor first calls `llama_synchronize()`, then begin
(`tools/server/server-scx.h:42-46`). It encloses the actual
`llama_decode()` or `llama_decode_with_options()` call
(`tools/server/server-context.cpp:3777-3788`). Finish synchronizes pending
work, writes the result, and calls end
(`tools/server/server-scx.h:50-58`; call site at
`tools/server/server-context.cpp:3790-3793`). The destructor emits an end
with result -1 if normal finish was skipped. This is a source-level ordering
guarantee, not a performance guarantee. The synchronization changes timing;
M11 makes no zero-overhead, performance-neutral, or production-readiness claim.

Worker markers are C functions because they are defined in a C translation
unit. Their signatures are `void ggml_scx_worker_begin_v1(void)` and
`void ggml_scx_worker_end_v1(void)`; both are noinline, used, and
default-visible at `ggml/src/ggml-cpu/ggml-cpu.c:3060-3072`. Begin occurs at
worker compute-thread entry at lines 3075-3078. End occurs at lines 3144-3148,
before the final graph barrier. They carry no event pointer, version, phase, or
identity fields.

Worker markers are audited but not attached in M11. Decode begin/end publish a
TGID state, all CPU worker threads share that TGID, and synchronized decode end
keeps the state active through graph completion. Worker attachment would add
complexity without improving the controlled one-process validation.

## Built ELF evidence

- Launcher:
  `build/llama-semantic/bin/llama-server`; ELF64 x86-64 PIE
  (`ET_DYN`), dynamically linked, unstripped. It does not itself define the
  marker symbols.
- Decode marker ELF:
  `build/llama-semantic/bin/libllama-server-impl.so`; ELF64 x86-64 shared
  object, unstripped. Dynamic global/default-visible symbols:
  `llama_scx_decode_begin_v1` at `0x178a00`, size 6, and
  `llama_scx_decode_end_v1` at `0x178a10`, size 7.
- Worker marker ELF:
  `build/llama-semantic/bin/libggml-cpu.so.0` (via
  `libggml-cpu.so`); ELF64 x86-64 shared object. Dynamic
  global/default-visible symbols: `ggml_scx_worker_begin_v1` at `0x192d0`,
  size 6, and `ggml_scx_worker_end_v1` at `0x192e0`, size 7.

The loader attaches by function name to the marker-bearing shared object, so
PIE/shared-object load addresses do not need to be calculated manually.

## Connection and filtering design

```text
semantic llama-server selected child
        |
        | C ABI marker(pointer to event)
        v
pid-specific decode begin/end uprobes
        |
        | validated scalar copy keyed by TGID
        v
bounded BPF phase_state map
        |
        | observation-only lookup
        v
existing sched_ext select/enqueue/running/stopping counters
```

The loader and struct_ops/tracing programs remain in one BPF object and share
maps directly. The provider does not open BPF maps, call `bpf()`, link libbpf,
send phase messages, or wait for per-phase ACKs.

The scheduler must be loaded before a child can enter `SCHED_EXT`, so the
launcher performs one control-plane registration:

1. the selected child enters `SCHED_EXT` and execs;
2. the launcher verifies the exec transition through `/proc/PID/exe`;
3. the launcher sends `REGISTER 1 PID` on an abstract
   `SOCK_SEQPACKET` registration socket;
4. the privileged loader validates peer UID, child UID, parent-child identity,
   and `SCHED_EXT` policy;
5. the loader sets a BPF target TGID and attaches both uprobes with that PID;
6. the loader ACKs once, after which phase traffic is entirely direct uprobe to
   BPF.

Only the loader is privileged. The launcher is the normal-user registration
peer, and the server retains that user's real/effective UID across `execve()`.
The PIDs used by this protocol are:

```text
launcher PID     = llama_scx_child parent process
server PID       = forked child after execve(llama-server)
registration PID = server PID sent in REGISTER 1 PID
target TGID      = registration PID used for both pid-specific uprobes
server PPID      = launcher PID
```

The loader authenticates the launcher's `SO_PEERCRED` UID against
`--phase-uid`, then requires the requested process to have that same UID, the
launcher as its parent, and `SCHED_EXT` as its scheduler policy. An abstract
Unix socket does not require the normal-user launcher to inherit root
privileges.

The registration socket is not the legacy phase socket. It transports no phase
or event payload. PID-specific attachment is the primary filter; the BPF
`phase_uprobe_config` TGID check is a second defense. The phase hash has 64
bounded entries instead of the historical single entry. Socket and uprobe
phase sources are mutually exclusive per loader run.

Begin copies the userspace event with `bpf_probe_read_user()`, validates
version 1, translates the phase, and publishes only scalar state. End rereads
the event and clears only when run ID, call ID, retry, and phase match the
currently active TGID state. A stale end cannot clear a newer begin. The final
record becomes inactive/UNKNOWN while retaining identity, counts, and result
for diagnostics.

Counters cover begin/end, all four begin phases, ABI failure, user-memory read
failure, unsupported phase, stale/mismatched end, map update failure, and
filtered events. Existing callback phase observations now include MIXED.

## Scheduling neutrality

M11 adds no phase branch to CPU selection, DSQ choice, dispatch order, slice,
weight, vtime, affinity, or migration policy. The existing policy body from
`llama_simple_select_cpu` onward still matches the recorded baseline after
removing the pre-existing `PHASE_OBSERVE` calls. Phase state is read only by
those observation calls. `SCX_OPS_SWITCH_PARTIAL` remains set. The manual
server command below also explicitly selects the semantic fork's
`legacy` compute-profile mode; only marker synchronization remains as
diagnostic timing overhead.

M10B files and the `/proc/stat` signal are not connected to BPF or M11.

## Build and unprivileged tests

```sh
cd /home/codinghuman/projects/llama-scheduler
make -j2
make check
cmake --build build/llama-semantic --target llama-server -j2
```

The C/BPF builds, legacy tests, and focused M11 tests pass without sudo.
Historically, loading struct_ops, attaching uprobes, verifier behavior, and
runtime marker delivery remained untested until the checkpoint below; that
checkpoint has since passed on the validated laptop.

## Historical three-terminal runtime checkpoint

Use three normal-user terminals. Run only the loader through `sudo`. Use no
other `llama-server` process and no old phase notifier.

### Preflight

Run as the normal user who will own the launcher and server:

```sh
cd /home/codinghuman/projects/llama-scheduler
USER_UID="$(id -u)"
USER_GID="$(id -g)"
if test "$USER_UID" -ne 0 &&
   test "$(git -C ../llama.cpp-semantic rev-parse HEAD)" = 5219055a578fd741e029e81fefef6f3a5695086d &&
   test -z "$(git -C ../llama.cpp-semantic status --short)" &&
   test -f /home/codinghuman/projects/model.gguf &&
   test -x build/llama-semantic/bin/llama-server &&
   test -f build/llama-semantic/bin/libllama-server-impl.so &&
   ! pgrep -a -x llama-server &&
   test "$(cat /sys/kernel/sched_ext/state)" = disabled; then
    printf 'operator_uid=%s operator_gid=%s\n' "$USER_UID" "$USER_GID"
    echo 'no existing llama-server process'
    echo 'sched_ext state: disabled'
    echo 'preflight=PASS'
else
    echo 'ERROR: M11 preflight failed; do not continue to Terminal A' >&2
    false
fi
```

Expected evidence is a nonzero operator UID, the fixed semantic revision, no
running `llama-server`, and disabled sched_ext state.

### Terminal A

Load the neutral scheduler as root, but authorize the invoking normal user's
real UID for the one-shot registration:

```sh
cd /home/codinghuman/projects/llama-scheduler
USER_UID="$(id -u)"
if ! test "$USER_UID" -ne 0; then
    echo 'ERROR: run Terminal A from the normal-user shell, not a root shell' >&2
    false
else
    mkdir -p results/m11
    run_dir="$PWD/results/m11/$(date -u +%Y%m%d-%H%M%S)"
    test ! -e "$run_dir" &&
    sudo ./build/bin/llama_scx_simple \
        -v \
        -o "$run_dir" \
        --phase-uprobe "$PWD/build/llama-semantic/bin/libllama-server-impl.so" \
        --phase-register-socket llama-m11-semantic \
        --phase-uid "$USER_UID" 2>&1 | tee /tmp/llama-m11-loader.log
fi
```

The shell expands `USER_UID` before `sudo`; only `llama_scx_simple` runs as
root. Expected output includes a registration listener for that nonzero UID,
then an attachment message naming the server TGID after Terminal B starts.

### Terminal B

Run this entire command as the normal user, without `sudo`. It launches one
CPU-only, one-slot server and does not enable the legacy phase socket:

```sh
cd /home/codinghuman/projects/llama-scheduler
if ! test "$(id -u)" -ne 0; then
    echo 'ERROR: run Terminal B as the normal user, without sudo' >&2
    false
else
    ./build/bin/llama_scx_child \
        --phase-register-socket llama-m11-semantic -- \
        "$PWD/build/llama-semantic/bin/llama-server" \
        -m /home/codinghuman/projects/model.gguf \
        -ngl 0 \
        -np 1 \
        --no-cont-batching \
        --spec-type none \
        --server-compute-profile-mode legacy \
        --scx-phase-run-id 11 \
        --no-warmup \
        --no-webui \
        --host 127.0.0.1 \
        --port 18080 2>&1 | tee /tmp/llama-m11-server.log
fi
```

Expected output includes `parent_pid`, `child_pid`, and
`phase_uprobe_registered_tgid`. The child PID and registered TGID must match;
the server then listens on `127.0.0.1:18080`.

### Terminal C

Wait for readiness, extract all four PID identities, validate privilege and
selected-child isolation, and only then send one request:

```sh
cd /home/codinghuman/projects/llama-scheduler
until curl -fsS http://127.0.0.1:18080/health; do
    sleep 1
done
shell_pid="$$"
expected_uid="$(id -u)"
validation_log=/tmp/llama-m11-validation.log
launcher_pid="$(sed -n 's/^parent_pid=\([0-9][0-9]*\).*/\1/p' /tmp/llama-m11-server.log | tail -1)"
server_pid="$(sed -n 's/.*child_pid=\([0-9][0-9]*\).*/\1/p' /tmp/llama-m11-server.log | tail -1)"
registration_pid="$(sed -n 's/^phase_uprobe_registered_tgid=\([0-9][0-9]*\).*/\1/p' /tmp/llama-m11-server.log | tail -1)"
target_tgid="$(sed -n 's/.*attached pid-specific decode markers to tgid=\([0-9][0-9]*\).*/\1/p' /tmp/llama-m11-loader.log | tail -1)"
test -n "$launcher_pid"
test -n "$server_pid"
test -n "$registration_pid"
test -n "$target_tgid"
if ! python3 - "$shell_pid" "$launcher_pid" "$server_pid" "$registration_pid" "$target_tgid" "$expected_uid" >"$validation_log" 2>&1 <<'PY'
import os
import sys

shell, launcher, server, registration, target, expected_uid = map(int, sys.argv[1:])

def process(pid):
    fields = {}
    with open(f"/proc/{pid}/status", encoding="utf-8") as status:
        for line in status:
            name, separator, value = line.partition(":")
            if separator:
                fields[name] = value.strip()
    return {
        "pid": pid,
        "name": fields["Name"],
        "ppid": int(fields["PPid"]),
        "uids": tuple(map(int, fields["Uid"].split())),
        "policy": os.sched_getscheduler(pid),
    }

def print_process(label, item):
    policy_name = {os.SCHED_OTHER: "SCHED_NORMAL", 7: "SCHED_EXT"}.get(
        item["policy"], f"policy-{item['policy']}")
    print(
        f"{label}: pid={item['pid']} ppid={item['ppid']} "
        f"uids={'/'.join(map(str, item['uids']))} policy={policy_name} "
        f"name={item['name']}")

assert expected_uid == os.getuid() and expected_uid != 0
items = {
    "validation_shell": process(shell),
    "launcher": process(launcher),
    "server": process(server),
}
items["launcher_parent"] = process(items["launcher"]["ppid"])
for label, item in items.items():
    print_process(label, item)
print(f"registration_pid={registration} target_tgid={target}")

for label in ("validation_shell", "launcher_parent", "launcher", "server"):
    assert all(uid == expected_uid for uid in items[label]["uids"]), (label, items[label])
assert items["validation_shell"]["policy"] == os.SCHED_OTHER
assert items["launcher_parent"]["policy"] == os.SCHED_OTHER
assert items["launcher"]["policy"] == os.SCHED_OTHER
assert items["server"]["policy"] == 7
assert items["server"]["ppid"] == launcher
assert registration == server
assert target == server

sched_ext_tasks = []
for process_entry in os.scandir("/proc"):
    if not process_entry.name.isdigit():
        continue
    tgid = int(process_entry.name)
    try:
        task_entries = list(os.scandir(f"/proc/{tgid}/task"))
    except FileNotFoundError:
        continue
    for task_entry in task_entries:
        tid = int(task_entry.name)
        try:
            if os.sched_getscheduler(tid) == 7:
                sched_ext_tasks.append((tgid, tid))
        except ProcessLookupError:
            pass
sched_ext_tasks.sort()
print(f"sched_ext_tasks={sched_ext_tasks}")
assert (server, server) in sched_ext_tasks, sched_ext_tasks
assert all(tgid == server for tgid, tid in sched_ext_tasks), sched_ext_tasks
print("privilege_and_isolation=PASS")
PY
then
    cat "$validation_log"
    echo 'ERROR: privilege or selected-child isolation validation failed' >&2
    false
else
    cat "$validation_log"
    curl -fsS http://127.0.0.1:18080/completion \
        -H 'Content-Type: application/json' \
        -d '{"prompt":"List three colors and briefly describe each one.","n_predict":8,"temperature":0,"cache_prompt":false}' \
        -o /tmp/llama-m11-completion.json &&
    python3 -m json.tool /tmp/llama-m11-completion.json
fi
```

Expected evidence is that the validation shell, Terminal B shell, launcher,
and server all have the same nonzero UID; both shells and the launcher are
`SCHED_NORMAL`; only the server is `SCHED_EXT`; the server PPID is the launcher
PID; and server PID, registration PID, and target TGID are identical. The
script enumerates every thread and fails if any `SCHED_EXT` task belongs to
a TGID other than the selected server. The final command prints the successful
completion response.

### Shutdown

1. In Terminal B, press Ctrl+C and wait for `llama_scx_child` to exit.
2. In Terminal C, verify that the selected server exited:

   ```sh
   if pgrep -a -x llama-server; then
       echo 'ERROR: llama-server is still running' >&2
       false
   else
       echo 'llama-server exited'
   fi
   ```

3. In Terminal A, press Ctrl+C and wait for the loader to write its report and
   exit. This disables the BPF target, destroys both uprobe links, and detaches
   the sched_ext struct_ops link.
4. In Terminal C, verify unload:

   ```sh
   final_scx_state="$(cat /sys/kernel/sched_ext/state)"
   printf 'final_sched_ext_state=%s\n' "$final_scx_state"
   test "$final_scx_state" = disabled
   ```

Do not use a broad process-killing command.

### Post-run validation

Inspect the newest report and enforce the semantic acceptance checks:

```sh
cd /home/codinghuman/projects/llama-scheduler
run_dir="$(ls -dt results/m11/* | head -1)"
test -f "$run_dir/summary.txt"
test -f "$run_dir/instrumentation.json"
printf 'run_dir=%s\n' "$run_dir"
sed -n '1,240p' "$run_dir/summary.txt"
python3 - "$run_dir/instrumentation.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as report:
    data = json.load(report)
uprobe = data["phase_uprobe"]
counters = uprobe["counters"]
observed = {entry["name"]: entry for entry in data["phase_observations"]}
print(json.dumps({"phase_uprobe": uprobe, "phase_observations": observed}, indent=2))
assert data["phase_control"]["enabled"] is False
assert uprobe["last_target_tgid"] > 0
assert counters["begin_prefill"] > 0
assert counters["begin_decode"] > 0
assert counters["begin_events"] == counters["end_events"]
assert counters["abi_failures"] == 0
assert counters["user_read_failures"] == 0
assert counters["unsupported_phases"] == 0
assert counters["stale_end_events"] == 0
assert counters["map_update_failures"] == 0
assert counters["filtered_events"] == 0
assert uprobe["state"]["active"] == 0
assert observed["PREFILL"]["running"] > 0
assert observed["DECODE"]["running"] > 0
print("semantic_acceptance=PASS")
PY
```

If `begin_mixed` or MIXED callback counts are nonzero, preserve and report
them; do not relabel them. For this manual debug path only, preserve
`/tmp/llama-m11-loader.log`,
`/tmp/llama-m11-server.log`, `/tmp/llama-m11-validation.log`,
`/tmp/llama-m11-completion.json`, the final sched_ext state, and both report
files. Do not combine them with another run. M11R avoids these shared paths and
places all authoritative evidence in one unique result directory.
