# 2차 통합 계획과 검증 순서

1. 원본 workspace와 배포 main를 보존하고 현재 donor refs를 sources.lock.json에 고정한다. 공통 조상과 신규 이식을 구분한다.
2. R 수치 정책을 단일 src 트리에 반영한다. CPU bridge와 marker를 분리한다. 이미 검증한 persistent pool의 owner·padding·종료 순서를 연결한다.
3. 동등한 AVX2 소스에서 OpenMP와 native를 별도 clean build한다. 프로젝트 DSO 전부를 각 build에서 만들고 code hash와 실제 mapping을 확인한다.
4. 일반 Linux에서 두 resource 구성과 pool/transport를 조합한다. 실제 모델 equality, 취소, 예외 후 재요청, sleep/resume 및 정리를 확인한다. R 사용을 runtime 로그로 검증한다.
5. donor topology/guard를 도입하고 FULL/Lite와 별도 v2 수신기를 빌드한다. receiver 실패 단위 검사 및 수동 loader checkpoint를 거친다. 커널 실행 가능 여부는 별개로 남긴다.
6. atomic fixture와 serving adapter를 같은 binary/DSO gate로 실행한다. mixed overlap, TTFT와 token-gap을 관측한다. 작은 comparative plan은 고정 반복만 실행한다.
7. Intel용 명령·schema·결과수집과 검토 ZIP 및 manifest를 작성한다. 해당 Intel 하드웨어와 승인된 커널 실행에만 native PASS를 부여한다.

현재 AMD에서 성능 반등 여부는 통합 gate가 아니다. 기본 선택은 unified-conservative이며 연구 구성은 별도로 옵션을 제공한다. 구성·정확성·안전·실기 및 성능은 각각 기록한다.
