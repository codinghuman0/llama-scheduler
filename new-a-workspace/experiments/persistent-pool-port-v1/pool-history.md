# 기존 persistent pool 결과와 한계

`evidence/archive/new-a-performance/persistent-pool/linux-pilot-v1/`의 setup, hypothesis, raw 결과와 summary 및 기존 runner를 조사했다. 옛 실험은 **OpenMP baseline 대 native persistent pool** 비교였다. pool 수명 외에 backend도 달랐으며 threads6/6, HTTP2, poll0 조건이다. 현재 E의 threads5/6, HTTP8, OpenMP 유지 후보와 동일한 비교가 아니다.

완결된 measured 4 paired block의 기록상 평균 paired 변화는 Prefill +0.6922%, Decode +0.7465%, HTTP 시간 -0.6756%, CPU seconds -1.2190%다. HTTP 시간이 줄어든 pair는 2/4다. 원 기록 상태는 `COMPLETE_EXPLORATORY_NOT_SAFETY_APPROVED`다. 부호가 엇갈리고 backend가 섞인 이 결과를 현재 후보의 속도 향상으로 사용할 수 없다. CPU seconds 변화는 에너지 측정이 아니다.

현재 E에는 `GGML_NEWA_POOL=on` optional 경로가 남아 있으나 실제 채택 설정은 off이다. 이 옛 결과 이후 off를 채택한 명시적인 최종 의사결정 문서는 이번 조사 범위에서 찾지 못했다. **최종 off 선택 이유는 unknown**으로 남긴다. 단지 작은 과거 이득 때문에 영구 기각되었다고 추측하지 않는다.

다른 연구 기록에서도 OpenMP B1에는 libgomp가 관여하므로 native custom barrier만 조정하는 정책이 적용되지 않는다는 제약을 기록했다. `omp_pause_resource` 또는 native threadpool 정책과 이번 donor ownership 변경은 같은 기법이 아니다.

이번에 추가한 것은 같은 OpenMP DSO를 유지한 선택 이식 후보, 실제 ABI와 상태 재사용을 확인하는 모델 없는 검사, baseline 대기 gate다. 기존 optional 구현이나 공개 구현의 기여를 이번 결과에 다시 더하지 않는다. 새로운 모델 기반 처리량 결과는 없다.
