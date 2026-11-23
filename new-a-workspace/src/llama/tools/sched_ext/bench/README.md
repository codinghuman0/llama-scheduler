# Portable Base benchmark

Use [clean_room_setup.sh](clean_room_setup.sh) as the primary clone-to-working-system command. Linux x86_64 sched_ext/BTF/BPF and matching kernel headers are required; Ubuntu dependency installation is automated. The model defaults to the sibling `../model.gguf`; setup accepts `MODEL=/path/model.gguf` and verifies the exact identity in [BENCHMARK_PROTOCOL.md](../BENCHMARK_PROTOCOL.md). It builds Base and neutral scheduler, runs correctness smoke and writes ignored `benchmark-results/host-profile.json`. No performance campaign runs in setup.

The profile freezes the invoking non-root repository owner, model, kernel/boot/BTF, detector topology, CPU allocation, available machine capabilities and host-built scheduler hashes. One logical CPU per usable physical core is selected, the last representative is housekeeping and all remaining representatives are server CPUs. Compute/batch threads equal the server CPU count; HTTP threads are two. An isolated benchmark requires at least two physical cores. No core class is silently removed. Frequency/turbo/power settings are recorded and must stay fixed, never automatically modified. Missing optional interfaces are recorded as absent. Missing CPU package temperature means bounded idle/load readiness only and an explicit reduced thermal observability report.

Check an existing profile without changing it:

```sh
python3 -B tools/sched_ext/bench/host_profile.py --check
```

After a reboot, model relocation, hardware/environment change or intentional neutral rebuild, generate a new profile before a new campaign:

```sh
make -B -C tools/sched_ext -j2
python3 -B tools/sched_ext/bench/host_profile.py --refresh
# Optional: --model /path/model.gguf
```

Refresh is refused for a prepared/active campaign. Every run copies the profile and records its exact SHA256; every later phase checks the frozen profile and artifact hashes, including the loader's embedded BPF path. A moved repository must rebuild the scheduler and regenerate the profile. `MODEL` on a phase entrypoint must agree with the profile; an override cannot silently select another file.

Close Firefox, all Codex UI/CLI sessions and unnecessary applications before Phase A and keep them closed until Phase D finishes. Use one terminal or TTY as the normal repository owner; do not prefix phase scripts with sudo. Run each command only after the preceding one succeeds:

```sh
./tools/sched_ext/bench/step10_phase_a_prepare.sh
./tools/sched_ext/bench/step10_phase_b_arm.sh
./tools/sched_ext/bench/step10_phase_c_campaign.sh
./tools/sched_ext/bench/step10_phase_d_finalize.sh
```

All entrypoints support `--help` and read-only `--dry-run`. Python loads the profile and sets its own affinity on execution; shell wrappers have no CPU constants. Phase A verifies the clean current `lightweight-base`, exact immutable tags and implementation identity; it builds A/B/C sequentially from frozen revisions using common Release/native/OpenMP flags and at most two compile jobs. Versions, dependencies, hashes, caches and commands are saved. D reuses exact C bytes. Existing development builds are not benchmark artifacts. Failed preparation evidence is preserved; no unrelated tree is removed.

`--reuse-artifacts` on Phase A validates and hardlinks previous closed/unused A/B/C bundles instead of rebuilding. It never reuses samples. Reuse requires the same recorded toolchain, allocation, scheduler and measurement identities. Only a closed campaign or an unused PREPARED campaign with no arming/raw request/completion evidence can be superseded; retain its directory. Do not reuse historical host-specific manifests with the portable runner.

Phase A can stop only identity-verified leftover managed Codex daemons owned by the frozen profile UID after UI/CLI sessions close. Every phase rejects detected interactive/build/benchmark activity. Separate `--check-ready` and `--stop-codex-daemons` modes do not execute a phase or issue requests. Do not invoke daemon shutdown from inside Codex.

Phase B revalidates artifacts/profile and arms a narrow root helper with one sudo interaction on housekeeping. The helper authenticates SO_PEERCRED against the frozen invoking UID and a campaign token. It accepts only fixed HELLO/CHECK/START/STOP/FINISH/ABORT operations and blocks on IPC/signals/pidfds; no continuous observer runs. Phase B does not activate sched_ext.

Phase C is the only measurement phase: 40 rotating ABCD visits, two excluded warm-ups and one measurement per fresh server, ten measured samples per config. The server and every TID use the server set. D's launcher inherits that set for registration, then only the idle launcher moves to housekeeping after ACK. Runner/client/helper/loader remain normal Linux policy on housekeeping. Checkpoints and bounded readiness occur outside the timed request. Natural selected-target teardown is required. Failure aborts without replacement samples and preserves evidence. Phase C must print `CAMPAIGN_COMPLETE` before Phase D.

Phase D validates saved order, all responses, identities, affinity/policy, readiness and cleanup, then computes the unchanged metrics, quartiles/MAD, paired-block analysis, 10,000 bootstrap draws with seed 20261006, slowdown definitions and decision gates. It issues no request. Firefox/Codex may reopen after Phase D finishes.

Results live under ignored `benchmark-results/step10/<UTC-run-id>/`; `.active-run` identifies the directory. Share that entire directory, including frozen host profile/protocol, manifests, bundles/build provenance, raw visits, readiness/cleanup evidence, CSVs, summary and `final-report.md`. Failed/incomplete directories are never overwritten. Never edit manifests to bypass a gate. Follow [Season 2](../SEASON2_EXPERIMENT_PROTOCOL.md) for subsequent policy experiments; the Base runner intentionally rejects policy-modified implementation.

Validation without performance measurement:

```sh
python3 -B tools/sched_ext/bench/test_campaign.py
python3 -B tools/sched_ext/bench/test_host_profile.py
./tools/sched_ext/bench/step10_phase_a_prepare.sh --dry-run
./tools/sched_ext/bench/step10_phase_b_arm.sh --dry-run
./tools/sched_ext/bench/step10_phase_c_campaign.sh --dry-run
./tools/sched_ext/bench/step10_phase_d_finalize.sh --dry-run
# Existing dependency/build environment, without apt or correctness requests:
INSTALL_DEPS=0 RUN_SMOKE=0 ./tools/sched_ext/bench/clean_room_setup.sh
```

The last command checks the same preflight/build/profile integration without reinstalling packages or running smoke; its marker is `CLEAN_ROOM_BUILD_PROFILE_RESULT=PASS (runtime smoke skipped)`. It is not a substitute for a new teammate's full setup smoke. Synthetic tests never activate sched_ext or send completion requests.
