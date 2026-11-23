# R / E / persistent pool 검증 패키지

최종 결과와 범위: [integration-summary.md](integration-summary.md). 상태: [gate-results.json](gate-results.json). 모델 가중치는 포함하지 않는다.

일반 계정으로 `./reproduce.sh verify`, 작은 실제 모델 재현은 `./reproduce.sh smoke`, 별도 고정 8-pair pilot은 `./reproduce.sh pilot --campaign NAME`. sudo/BPF는 사용하지 않는다. 새 실험 이름을 사용하며 기존 raw를 덮어쓰지 않는다.

기존 source/runtime/model/archive와 prepared pool port는 보존했다. 초기 P guard 실패와 observer 실패도 raw와 ledger에 남겨 두었다.
