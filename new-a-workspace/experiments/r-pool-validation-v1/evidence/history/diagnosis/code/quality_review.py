from pathlib import Path
import json
D=Path(__file__).resolve().parents[1];Q=D/'quality-v2';summary=json.loads((Q/'summary.json').read_text());assert summary['status']=='COMPLETE'
notes={
('B0','Q0-raw','h1-a'):'건조 주 예시를 달라는 지시를 되풀이하며 물 배분 계획 없음.',
('B0','Q0-raw','h1-h'):'원래 없는 virtual sensor/물리 센서 없이 재구성 조건을 만들고 반복.',
('B1','Q0-raw','h1-a'):'원래 질문의 예시·동일배분 문제 지시를 반복; 계획 없음.',
('B1','Q0-raw','h1-h'):'원래 없는 virtual sensor/연결되지 않은 센서 위치 추론 조건을 만들고 반복.',
('B0','Q1-template','h1-a'):'문제에 맞는 reasoning 시작; 일주일에 한 번 물주기 가정, 구체적 보장/예시 전에 중단.',
('B0','Q1-template','h1-h'):'요구사항을 맞게 다시 정리하지만 실질 설계 전에 중단.',
('B1','Q1-template','h1-a'):'reasoning 시작; 주1회/격일 간 흔들리며 구체적 수급 계획 전 중단.',
('B1','Q1-template','h1-h'):'요구사항 정리 후 소음 센서를 ultrasonic sensor로 추정하기 시작.',
('B0','Q3-length','h1-a'):'일정·하한 수위를 논의하나 낮은 탱크 수위일 때 물을 주자는 모순, 건조 주 완성 예시 없음.',
('B0','Q3-length','h1-h'):'median/window/calibration/placement/missing/time을 언급하지만 실제 트럭 소음 spike를 센서 갱신 부정확 문제로 단정; 전후 비교 미완결.',
('B1','Q3-length','h1-a'):'측정·누락·추정/보장을 논의하고60L 예시를 시작하나 수급 계획을 완성하지 못함.',
('B1','Q3-length','h1-h'):'소음 센서를 초음파 거리 센서로 잘못 해석하고 거리 calibration을 제안; peak 보존 등 관련 제안도 있으나 미완결.',
('B0','Q4-temperature','h1-a'):'주간 순환 배정을 제시하다가 alternate-day 방식으로 다시 흔들림; 건조 주 수급 계산 미완성.',
('B0','Q4-temperature','h1-h'):'spike/평균/일자 비교와 calibration을 언급; 센서가 가까우면 트럭 경로를 놓친다는 근거 없는 설명, 시간대 논의 중 중단.',
('B1','Q4-temperature','h1-a'):'plot별 사용량·누락·추정/보장을 논의하지만 구체적 건조 주 배분을 끝내지 못함.',
('B1','Q4-temperature','h1-h'):'spike 보존, 동기화, calibration, missing bias, 전후 비교와 한계 등 실질 제안이 있으나 완료된 최종 답변 없음.'}
rows=[];settings=[];adj=[]
for row in summary['rows']:
 key=(row['arm'],row['condition'],row['prompt']);v=json.loads((Q/key[0]/(key[1]+'-'+key[2]+'-response.json')).read_text());p=json.loads((Q/key[0]/(key[1]+'-'+key[2]+'-request.json')).read_text())
 for f in ['seed','n_predict','ignore_eos']:assert v['generation_settings'][f]==p[f]
 assert abs(v['generation_settings']['temperature']-p['temperature'])<1e-6
 assert v['timings']['cache_n']==0 and v['stop_type']=='limit' and '</think>' not in v['content']
 note=notes.get(key)
 if key[1]=='Q2-eos':
  ref=json.loads((Q/key[0]/('Q1-template-'+key[2]+'-response.json')).read_text());assert v['tokens']==ref['tokens'];note=notes[(key[0],'Q1-template',key[2])]+' EOS 설정만 바꾸면 동일한 출력.'
 rows.append(dict(arm=key[0],condition=key[1],prompt=key[2],complete_task_answer=False,manual_observation=note,repetition_flag=row['repetition_flag']))
 settings.append(dict(arm=key[0],condition=key[1],prompt=key[2],effective_settings_match=True,cache_n=0))
for arm in ['B0','B1']:
 for prompt in ['h1-a','h1-h']:
  get=lambda c:json.loads((Q/arm/(c+'-'+prompt+'-response.json')).read_text())['tokens']
  eq=get('Q2-eos')==get('Q1-template');prefix=get('Q2-eos')==get('Q3-length')[:128];assert eq and prefix
  adj.append(dict(arm=arm,prompt=prompt,eos_only_exact_equal=eq,longer_first128_equal=prefix))
result=dict(status='PARTIALLY_CHARACTERIZED_NOT_RESOLVED',rubric='quality-v2/protocol.json predeclared',reviewer='assistant qualitative reading; not blind or independent human evaluation',rows=rows,effective_settings=settings,adjacent_comparisons=adj,limitations=['two prompts and one seed only','no semantic equivalence score','all20 ended at length limit','512-token cap not proven sufficient for this reasoning model','template effect scoped to response format and repetition, not global quality resolution'])
(Q/'review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
text='''# 별도 품질 형식 진단\n\n**상태: PARTIALLY_CHARACTERIZED_NOT_RESOLVED.** 두 질문에서 template 적용은 짧은 구간의 반복을 줄였지만, 답변의 완결성과 일반적인 품질을 해결하지 못했다. B0/B1 수치 분기의 원인과 별개다.\n\n로컬 GGUF metadata의 이름은 Deepseek-R1-Distill-Qwen-1.5B, architecture는 qwen2이며, user/assistant 및 thinking delimiter를 포함한 chat template가 있다. 이름은 이 파일의 metadata이며 가중치 변환 provenance 전체를 독립 인증했다는 뜻은 아니다. 기존 workload는 BOS+raw prompt continuation으로 user/assistant 구분을 사용하지 않았다. `/apply-template` 결과에는 BOS가 없어서 `/tokenize(add_special=True,parse_special=True)`로 정확히 한 개의 BOS151646을 넣었다. 양쪽 runtime의 각 조건별 input token 배열이 같다.\n\n공식 모델 안내는 temperature0.5–0.7(0.6 권장), thinking prefix 등을 제안한다. 이는 별도 진단 선택의 근거이며 로컬 품질 문제의 원인을 단독으로 증명하지 않는다. [공식 모델 카드](https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B), [공식 사용 안내](https://github.com/deepseek-ai/DeepSeek-R1/blob/main/README.md).\n\n`quality-v2/protocol.json`에 실행 전에 정한 두 prompt(h1-a garden/h1-h noise),20 responses, seed424242와 rubric을 고정했다. 원래8요청 성능 결과에 섞지 않는 singleton 진단이다. Q0 raw128/ignoreEOS/temp0, Q1 template만 변경, Q2 EOS존중만 변경, Q3 출력한도512만 변경, Q4 temperature0.6만 변경이다. 요청간 cache는0이며 실효 generation_settings도 확인했다.\n\n| Runtime | 조건 | Garden 반복6gram 비율 | Noise 반복6gram 비율 | 출력 tokens(각각) |\n|---|---|---:|---:|---:|\n'''
for arm in ['B0','B1']:
 for condition in ['Q0-raw','Q1-template','Q2-eos','Q3-length','Q4-temperature']:
  a,b=[r for r in summary['rows'] if r['arm']==arm and r['condition']==condition]
  text+=f"| {arm} | {condition} | {a['repeated_6gram_window_fraction']*100:.2f}% | {b['repeated_6gram_window_fraction']*100:.2f}% | {a['tokens']} |\n"
text+='''\n비율은 generated-token 6gram window 중 첫 등장 이후의 window 비율이다. 판정 flag는 같은6gram이3회 이상 나타나는지이며, 이 수치가 낮아도 의미 반복·오류가 없다는 뜻은 아니다.\n\n- **Template:** 두 runtime/두 질문의128-token 구간 모두 중복6gram 비율이0%로 줄었다. 문답 형식은 개선됐으나128 tokens 안에 요구된 작업을 완료하지 않았다.\n- **EOS:** Q1/Q2의4쌍은 token이 정확히 같다. 이번 한도 내 종료를 EOS 무시만으로 설명할 수 없다.\n- **출력 길이:** Q3의 첫128개는 Q2와 같다.512 tokens에서는 더 많은 제안을 냈지만 전부 다시 limit에 도달했다. 충분한 길이가 확보됐다고 말할 수 없다.\n- **Temperature:**0.6에서도4개 모두 limit 종료이며 일반적인 해결책으로 확인되지 않았다. seed 하나뿐이므로 확률적 품질 향상률을 추정하지 않는다.\n\n20개 모두 stop_type=limit이며 generated content에 closing `</think>`가 없다. EOS/limit boolean 필드는 이 API 응답에 없으므로 summary의 null을 false로 바꾸지 않고 실제 stop_type을 사용했다. 최종 answer로 완결된 상태가 아니다. 실질적 제안이 전혀 없다는 뜻은 아니며, 작업완료 여부와 부분 도움을 구분한다.\n\n수동 확인의 구체적 제한: B0 garden512는 낮은 수위에서 물을 주자는 모순을 내며, B1 noise512는 소음 센서를 초음파 거리 센서로 잘못 해석한다. temperature0.6의 B1 noise에는 동기화·calibration·missing bias 등 유용한 항목도 있지만 완결된 비교 방법/결과가 아니다. 모든 응답별 검토는 `quality-v2/review.json`에 있다. 두 prompt와 단일 seed의 assistant 정성 검토이며 blind human 평가나 일반 semantic-quality equivalence 검증이 아니다.\n\n첫 시도 `quality/`는 BOS를 빠뜨린 harness 오류로7개 완료 후8번째 요청 중 중단했다. 로그·부분 결과·오류 당시 runner를 보존했으며 최종20응답과 합치지 않았다. 사용자 데이터나 불리한 결과를 제거하지 않았다.\n'''
(D/'quality-report.md').write_text(text)
print(json.dumps(dict(status=result['status'],responses=20,all_limit=True,eos_only_pairs_equal=4)))
