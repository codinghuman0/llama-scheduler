# Claim-evidence matrix

| 주장 | 현재 증거 | 범위 | 미검증/제한 |
|---|---|---|---|
| 전체 A_S/B0 효과 재현 | campaign-comparison.json states.overall_system=REPLICATED_SCOPED_SYSTEM_GAIN; 캠페인별2조건 gate | 원본+새 기여 실행2회, 같은 장비 | 외부 재현·새 workload 일반화 아님 |
| E의 fixed6 대비 CPU25 선택 효과 | E_SELECTION_REPLICATED_CPU25; 각 캠페인 CI와 실제 선택 차이 | 센서/guard를 유지한 eligible multi-token Decode 선택 | fixed5 또는 모든 static 정책 우월성 아님 |
| E ambient | 각 캠페인 E_ambient와 실제 선택 count | 동일 선택이면 미소 시간차를 적응 이득으로 주장하지 않음 | 효과0/동등성 증명 아님 |
| S 추가 효과 | 캠페인·조건별 A_S/A_L sign/CI; 실제 kernel admission | 동일 userspace에 observe/FULL 추가 | inconclusive는 무오버헤드 증명이 아님; fixed6_S 없음 |
| semantic phase 활용 | sources/newa-prefill-pressure.h, frozen runtime identity, raw epochs | E가 phase를 사용하고 A/F6 모두 전달 유지 | label 자체의 다른 controller 대비 고유 가치 미분리 |
| phase-dependent kernel placement | sources/handoff.bpf.c, compile.log, moved=0 | observe는 관측만 함 | 새로운 phase-aware dispatch 개선을 입증하지 않음 |
| 출력 호환 | 모든 새 warmup/측정 raw tokens vs frozen B0 oracle; 기존 R checkpoint 별도 | declared fixtures의 자유 생성 | 새 logits 전수검사0, 일반 품질 증명 아님 |
| 실제 CPU/DSO/model 적용 | runtime.json, worker snapshots, loaded alias inode/hash, model hash, scheduler evidence | 고정6 CPU envelope, 해당 kernel/BTF | dynamic-affinity 역사적 실패 미해결 |
| 부담 동일성 | CPU10 .0125/.05 generator 실제 counters .22-.28 core | 고정0.25-core 간섭 | 전체CPU25%/quota25% 아님 |
| 원본 보존 | protected-before/after; original ZIP SHA; harness-isolation proof | 기존 workspace 전체 content/mode | 기존 원본 결과를 새 판정으로 덮어쓰지 않음 |
| 완결성 재계산 | 64 visits/128 cohorts/10 contrasts 요구; 누락 negative test | 원시 수치 별도 구현, 모델 불필요 | 계측의 모든 잠재적 오류나 원인 분리 증명 아님 |
| 캠페인 간 baseline 변동 | 모든 arm 절대값·cohort/order/environment table | 관측된 변화 | CAUSE_UNDETERMINED; 사후 outlier 제거 없음 |
| 최종 실행 역할 | frozen-release-map.json, exact cases, reproduce.sh | A_L 기본, A_S 평가; 지원 범위 제출 기준점 | production-ready 아님; 자동 Git push/tag 변경 없음 |
