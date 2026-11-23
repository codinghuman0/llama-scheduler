# 최종 통합·팀원 코드 기여 감사

상태: **FUNCTIONAL_INTEGRATION_MAPPED / PARTIAL_PROVENANCE**. 성능 판정과 별개인 출처·채택·실행 감사다. 보존된 두 component campaign의 system gain과 CPU25 E 선택 효과를 재계산했으며 새 모델 실행은0회다.

먼저 [통합 요약](integration-summary.ko.md), 발표에는 [교수님 설명](professor-brief.ko.md)과 [예상 질문](professor-qa.ko.md)을 읽으면 된다.

| 자료 | 내용 |
|---|---|
| [통합 표](integration-matrix.md) · [CSV](integration-matrix.csv) · [JSON](integration-matrix.json) | 34개 기능의 출처/채택/실행/성능 네 축, source/hash/근거/금지 주장 |
| [source-lineage.json](source-lineage.json) | 정확한 donor pins, 공유 조상, local overlay, 작은 commit/overlay patch |
| [통합 경로](runtime-integration-map.md) | A_L/A_S 텍스트·Mermaid, 화살표15개의 file:line/hash 연결 |
| [observed-usage.json](observed-usage.json) | 144 기존 visits의 정책 계수, warmup/functional/measured, scheduler/pool/route 단위 |
| [성능 기여](performance-attribution.md) | 20 component 비교와 P/A 두 pilot 조건의 절대값/CI/해석 |
| [누락 증거](missing-evidence.md) | UNKNOWN, 미분리 효과, build/status 시점과 현재 entrypoint 차이 |
| [audit-checks.json](audit-checks.json) | 입력·소스 anchor·수치·보호 검증 결과와 요구사항 대응 |
| [manifest.json](manifest.json) | 검토 ZIP 멤버의 SHA256/크기와 제외 범위 |
| [review.zip](review.zip) · [SHA256](review.zip.sha256) | 모델/runtime/full history/이전 ZIP 없는 작은 검토 패키지 |

## 모델 없이 재계산

ZIP을 푼 디렉터리 또는 이 audit 디렉터리에서 다음만 실행한다. 표의20 component 비교와2 pool 조건을 다시 계산하며 파일을 수정하지 않는다.

```bash
python3 -B code/recalculate_packaged.py
```

timestamp와 실제 token-count를 검증해 만든 작은 발췌가 포함된다. 모든 원시 응답·token 배열은 기존 workspace에 보존했다. 원본 raw까지의 검사는 `evidence/performance-recalculation.json`, 입력 hash는 `evidence/usage-inputs.json`/`additional-inputs.json`에 있다. ZIP의 발췌 계산과 원본 전체 raw 재검사를 같은 것으로 주장하지 않는다.

`collect_usage.py`, `collect_static.py`, `enrich_evidence.py` 등은 원래 workspace 자료를 읽고 이 audit 디렉터리만 갱신한 감사 도구다. 전체 archive index와 선택 Git 파일 snapshot은 로컬 조사용으로 남겼고 ZIP에서는 뺐다. 따라서 archive 조사 보조도구 전체를 ZIP만으로 실행할 수 있다고 주장하지 않는다. 제출물 재계산 진입점은 위 명령이다. 기존 실험 reproduce.sh/runtime 명령은 이 감사의 실행 지시가 아니다.

## 구분할 사항

- A_L은 연구상 기본 성능 역할이다. 현재 workspace `run.sh`의 pre-R NEW_A 경로를 변경했다는 뜻이 아니다.
- F6_L은 적격 multi-token Decode만 fixed6이다. phase·sensor·guard·연산 경로는 유지한다.
- E_runtime과 kernel scheduler의 NEW_A(E) FULL은 다른 기능이다.
- phase_seen은 bitmap, E 계수는 select 호출, Q4는 worker0 함수 호출, Q6는 worker0 chunk, pool은 graph 계수다.
- manifest는 ZIP 자신의 hash를 포함하지 않는다. ZIP hash와 패키징 후 검증은 별도 `review.zip.sha256`/`package-verification.json`이다.

기존 source/model/runtime/raw/report를 변경·삭제하지 않았다. 보호 전후는 `evidence/protected-before.json.gz`와 `evidence/protection-after.json`이다. 새 benchmark/build/project unit-test/BPF load/sudo/Git mutation은 없다. ZIP에도 ELF나 모델은 없다. 이번 문서와 감사용 분석 코드는 Codex가 작성했다.
