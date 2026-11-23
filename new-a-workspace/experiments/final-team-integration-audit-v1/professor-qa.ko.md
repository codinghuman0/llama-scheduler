# 교수님 예상 질문과 답변

1. **모든 팀원 코드를 합친 건가?**

   아닙니다. 공통 조상의 phase/profile 기반과 scheduler 실행 기반을 재사용하고 필요한 연결을 추가한 선택 통합입니다. P pool은 실제 이식·검증했지만 최종 A에 채택하지 않았습니다. 기능별로 계보, 채택, 실행, 성능 증거를 분리한 [34개 행의 표](integration-matrix.json)를 제시할 수 있습니다.

2. **최근 pool/v2도 최종 성능에 포함되었나?**

   포함되지 않았습니다. A server에는 donor pool owner가 없고 기존 optional pool도 off입니다. P에는 donor header/owner가 실제 링크돼 lifecycle 검증을 통과했지만 n4 pilot이 ambient −1.654649%, CPU25 +1.051134%로 엇갈렸습니다. v2 active/idle도 final에 없으며 현재는 scalar v1 last-emitted phase입니다. [정적 ELF](evidence/static-elf.json), [사용 계수](observed-usage.json).

3. **phase가 실제 worker 수를 바꾸었나?**

   런타임 정책은 semantic phase와 Prefill에서 얻은 경합 관측을 함께 사용해 profile을 선택했습니다. 각 캠페인의 CPU25 measured 구간에서 pressure의 적격 multi-token Decode 1,016 select 호출은 5-worker, fixed6은 6-worker를 선택했습니다. OpenMP team 보고도 연결됩니다. ambient에서는 둘 다6이었습니다. phase label 자체만의 고유 효과를 다른 controller와 비교한 것은 아닙니다. [사용 계수](observed-usage.json), [호출 경로](runtime-integration-map.md).

4. **커널 스케줄러가 없어도 빨라지는가?**

   그렇습니다. A_L/B0_L가 Linux만 사용한 직접 비교이며 ambient +16.20/+15.41%, CPU25 +32.39/+29.23%였습니다. 반면 A_S/A_L는 기존 양 조건에서 불확실했고, 재현에서는 ambient +0.745%, CPU25 −1.256%였습니다. 전체 gain을 커널 기여라고 설명하지 않습니다. [모든 CI](performance-attribution.md).

5. **스케줄러가 phase에 따라 CPU를 배치하나?**

   최종 observe 구성은 그렇지 않습니다. uprobe가 phase를 받고 Decode 조건의 attempt counter는 증가하지만, 이동 분기는 `NEW_A_IDLE_HANDOFF`가 빠진 빌드에서 실행되지 않습니다. placement는 topology idle tier와 shared weighted-vtime입니다. 모든 A_S raw에서 handoff moved0입니다. kernel→E feedback도 [정해진 소스 조사 범위](evidence/feedback-search.json)에서는 찾지 못했습니다.

6. **개선율 중 각 팀원·각 커널 몫은 얼마인가?**

   현재는 산정할 수 없습니다. E 선택은 fixed6 대비 CPU25에서 약11~12%로 분리했고 scheduler 구성 추가 효과도 분리했습니다. Q4/Q6/API/메모리 각각은 해당 기능만 바꾼 확증이 없어 NOT_ISOLATED입니다. F6/B0는 묶음 효과이고, 서로 다른 분모의 gain을 더할 수도 없습니다. Git author나 코드량은 개인 성능 기여율이 아닙니다.

7. **왜 같은 폴더·같은 파일 수를 통합률로 말하지 않나?**

   파일이 있어도 조건부 컴파일로 빠질 수 있고, 링크돼도 옵션이 off일 수 있으며, 실행돼도 빨라지지 않을 수 있습니다. 예를 들어 native barrier는 OpenMP final에서 비활성이고, P pool은 실행됐지만 채택하지 않았습니다. 그래서 출처·채택·실행·성능 네 축을 독립적으로 기록했습니다.

8. **하나의 commit으로 clean rebuild할 수 있는가? 이번에 입증했나?**

   이번 감사에서 입증하지 않았습니다. 보존된 base59, 여러 overlay, 기존 DSO와 최소 재빌드 기록을 조합한 frozen release입니다. source hash, compile/link 명령, ELF hash, 실제 loaded DSO의 연결은 확인했지만 단일 clean revision의 전체 재빌드는 수행하지 않았습니다. 현재 기본 run.sh도 final A를 가리키지 않습니다. [한계와 필요한 자료](missing-evidence.md).

9. **무엇이 재사용이고 무엇이 새로 한 일인가?**

   profile API/semantic origin은 공유 조상에서 재사용했고, Linux sched_ext/scx_simple도 공통 기반입니다. 이후 로컬 경량화, CPU phase bridge, E 선택 정책, 누적 Q4/Q6 경로, R 수치 호환성 복원, P 선택 이식·검증이 이어졌습니다. 이번 감사의 새 작업은 이 출처와 실행을 연결하고 기존 수치를 다시 계산해 설명한 것입니다. 새 코드를 성능 경로에 넣거나 새 실험을 돌린 것은 아닙니다. [계보 JSON](source-lineage.json), [commit별 hunk](evidence/commit-hunks.json).
