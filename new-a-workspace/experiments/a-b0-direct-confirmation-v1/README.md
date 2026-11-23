# A/B0 직접 비교

결과: direct-comparison-summary.md/json. 사전 명세: protocol.json, order.json, seal.json. 원본 runtime 변경 patch 없음. 실제 실행에는 기존 통합 workspace와 original model이 필요하다. 검토 ZIP은 실행용 전체 복제본이 아니다.

일반 계정에서 ./reproduce.sh verify, ./reproduce.sh analyze --name confirmation-v1, ./reproduce.sh smoke --name NEW, ./reproduce.sh full --name NEW. sudo 불필요.
