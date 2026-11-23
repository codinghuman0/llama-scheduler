# 원시 수치의 별도 재계산

검토 ZIP을 풀고 그 폴더에서 다음을 실행하면 모델이나 runtime 실행 없이 표의 paired gain과 층화 bootstrap CI를 다시 계산한다. Python 표준 라이브러리만 사용한다.

```bash
python3 -B code/recalculate.py --name confirmation-v1
```

code/recalculate.py는 저장된 actual token 배열과 monotonic start/end에서 각 처리량을 다시 구하고, 별도의 산술 코드로 block gain/CI를 대조한다. 원본 workspace의 library inode/hash·환경까지 검사하는 전체 감사는 `./reproduce.sh analyze --name confirmation-v1`이다. 실제 추론 재현은 기존 통합 workspace와 model을 필요로 하며 `verify / smoke / full` 명령을 사용한다.
