# 단일 폴더 정리 완료

상태: COMPLETE. 일반 계정으로 수행했으며 모델 추론·BPF load·새 성능 실험은 실행하지 않았다.

- 실제 파일시스템 가용 공간 증가: 320,626,688 bytes (305.8 MiB).
- 현재 가용 공간: 3.15 GiB.
- 과거 증빙 압축본: 848.2 MiB ZIP에서 541.1 MiB TAR.XZ로 축소.
- 내부 전체 할당 공간: 약 1.69 GiB. 이 중 모델을 제외한 소스·runtime·기록은 약 669.0 MiB.
- 모델은 원본과 내부 models/model.gguf가 같은 inode를 공유하므로 모델 데이터 추가 할당은 0 bytes. 원본 내용은 불변이다. 복사·이동 후 내부 모델 경로만으로 사용할 수 있다.

## 삭제와 보존

재생성 가능한 compiler object/Python bytecode 32개 경로(16개 고유 blob), 모델 없는 테스트 실행 파일 11개, 검증 후 대체된 legacy.zip을 제거했다. 삭제 목록과 hash는 removed-build-cache.json, test-executable-cleanup-plan.json, deletion-result.json에 있다. BPF object는 일반 compiler 중간 파일과 구분해 보존했다.

Git 이력, 소스, 실제 출력·성능 원시 결과, 실패 증빙, 검증된 B0/B1/NEW_A 실행 파일과 DSO는 보존했다. 새 압축본의 35,174개 고유 blob 및 121,955개 파일 경로가 기존 SHA256과 일치한다. 압축 컨테이너 hash 변경은 archive-verification.json에 명시했다. 오래된 원본 기록의 hash나 경로 문자열을 새 값으로 덮어쓰지 않았다.

## 외부 경로 의존성 제거

run.sh의 기본 모델은 models/model.gguf로 변경했다. 모델은 symlink가 아닌 일반 hardlink이며 원본 경로 삭제 여부와 관계없이 내부 경로로 접근할 수 있다. 같은 inode의 내용 변경은 양쪽에 반영되므로 모델 파일은 읽기 전용으로 취급한다. 원본 소스 ../llama.cpp는 현재 package 실행/빌드에 사용하지 않는다.

현재 진입점 run.sh/build.sh/tools는 자신의 폴더 위치를 기준으로 경로를 계산한다. 역사 로그·일회성 intake script의 옛 절대 경로는 실행 증빙으로 남는다. 압축본 조회는 tools/archive.py가 새 TAR.XZ를 순차 탐색한다. compiler/CMake/glibc/OpenMP 등 시스템 의존성까지 제거하거나 정적으로 패키징한 것은 아니다.

## 검사

- package 3,087개 파일 hash/권한 및 모델 hash PASS.
- 원본 소스·모델 3,265개 파일 hash와 mtime 불변 확인.
- 다른 경로에 만든 임시 폴더에서 기본 모델 경로가 그 폴더 내부로 해석됨: PASS.
- 이동된 B0/B1/NEW_A --help, 프로젝트 DSO의 이동 폴더 내부 로드: PASS.
- 이동된 통합 소스의 CMake configure: PASS. 전체 재컴파일/모델 출력 검증은 NOT_RUN.
- 압축본 파일 추출 후 원본 SHA256 일치: PASS.
- 임시 relocation/build 디렉터리 정리 완료. measurement lock inode 800700 유지. 관련 없는 프로세스 종료 없음.

재확인:

```bash
cd /home/codinghuman/projects/new-a-workspace
python3 -B tools/verify.py --archive
bash run.sh --describe
```

기존 pool 연구 상태는 WAITING_NUMERICAL_BASELINE이다. 이번 저장 공간 정리가 수치 호환성 검증이나 성능 개선을 의미하지 않는다.
