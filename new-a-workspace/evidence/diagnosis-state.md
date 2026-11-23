# Output divergence diagnosis: LOCALIZED

진단·제한 재현·최초 분기 비교·component 격리·단일 요청 축소·bounded live operator 검증·별도 품질 진단·재현 스크립트 검증을 완료했다.

- 원인 범위: 기존 Q4 Prefill 경로. Q4off는 h1/h2 전체8출력과 singleton에서 B0를 복원하며 full 재활성화는 B1 차이를 복원한다.
- Q6 및 exact Decode Q4 off는 조사한 h1 logits를 바꾸지 않는다.
- 수치 차이의 모든 layer 전파/semantic equality는 미입증. 품질 상태 PARTIALLY_CHARACTERIZED_NOT_RESOLVED.
- E/B1 equality는 보존된 기존1,024응답 증거 PASS이며 이번에 E를 새 실행하지 않았다.
- 원시 재계산 PASS, 별도 새 빌드/실행 재현 PASS, 보호파일656/저장소6 상태 PASS. 모든 owned server 정리.
- CMake dependency cache625개(9.15MiB)만 승인 범위로 삭제. 모델·runtime·source·raw·archive는 보존.
- Archive 구성/CRC/member SHA 검증은 code/pack_review.py, 실제 크기와 SHA는 package-result.json 및 zip.sha256.
- 종료 사유: 이번 경로 격리 진단의 산출물 완성. 추가 성능 목표 또는 의미적 동등성 성공 선언이 아니다.
- 다음 작업 하나: next-step.md의 B0 누적 순서 호환 후보 검증.
- 재현: bash reproduce.sh replay-single /tmp/newa-diagnosis-single-fresh
- 재계산: bash reproduce.sh analyze /tmp/newa-diagnosis-analysis-fresh
