# 다음 단계 하나

별도 CODEX_Q4_PREFILL_REFERENCE_COMPATIBILITY_GOAL.txt 작업에서 **R 수치 호환 baseline을 먼저 검증·동결한다**. source revision/overlay, compiler 옵션, 실제 loaded DSOs, 모델 hash 및 동일 두 cohort·singleton의 자유 생성 token 검증 증빙이 필요하다. 기존 B1/E 또는 teacher-forced 진단만으로 이 gate를 대체하지 않는다.

현재 패키지에서는 확인 명령만 제공한다:

```bash
bash experiments/persistent-pool-port-v1/reproduce.sh admission
```

이 명령은 WAITING_NUMERICAL_BASELINE과 종료 코드 3을 반환하며 모델 실행 경로를 열지 않는다. R이 준비되면 그 동결 identity 위에 pool-only patch를 검토·재적용하고 본 protocol의 기능 gate부터 수행해야 한다. 이 review package 자체를 이미 모델 검증된 실행본으로 취급하지 않는다.
