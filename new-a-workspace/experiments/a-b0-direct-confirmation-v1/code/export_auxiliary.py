"""Format already frozen analysis outputs; does not change any estimator or gate."""
import math
from pathlib import Path
from common import *
s=read(D/'direct-comparison-summary.json');rows=[];loads=[]
for c in s['cells']:
 for arm in ['B0','A']:
  a=c['absolute'][arm];background=[p[arm]['background_cores'] for p in c['pairs'] if p[arm]['background_cores'] is not None]
  rows.append(f'| {c["campaign"]} | {c["condition"]} | {arm} | {a["wall_s"]:.6f} | {a["cpu_s"]:.6f} | {a["cpu_seconds_per_token"]:.9f} |')
  if background:loads.append(f'| {c["campaign"]} | {arm} | {min(background):.9f} | {max(background):.9f} |')
checked=0
for v in s['visits']:
 folder=D/v['raw']
 for role in ['warmup','measured']:
  for x in read(folder/f'{role}-http-raw.json'):
   t=x['timings']
   for prefix in ['prompt','predicted']:
    assert t[prefix+'_n']>0 and t[prefix+'_ms']>0
    assert math.isclose(t[prefix+'_per_second'],1000*t[prefix+'_n']/t[prefix+'_ms'],rel_tol=1e-10)
   checked+=1
src=W/'src/llama/tools/server/server-context.cpp';lines=src.read_text().splitlines()
definition=dict(status='RESPONSE_FORMULAS_VERIFIED',response_count=checked,source=str(src),source_sha256=sha(src),get_timings_lines=dict(start=595,text='\n'.join(lines[594:609])),generation_boundary_lines=dict(start=4025,text='\n'.join(lines[4024:4039])),scope='Existing server-reported per-slot response timings only; not exclusive graph CPU times or independently measured semantic phase windows',interpretation=['prompt_n = n_prompt_tokens_processed; prompt_ms = t_prompt_processing','predicted_n = n_decoded; predicted_ms = t_token_generation','A get_timings emits n*1000/ms; same response formula verified for every B0/A warmup and measured output','First decoded token sets t_start_generation and closes prompt timer; these slot intervals can overlap other slots','No aggregate tokens/s formed by summing these per-request rates; primary remains cohort HTTP throughput'])
save(D/'evidence/response-timing-definition.json',definition)
(D/'auxiliary-results.md').write_text('# 보조 지표\n\n사전 고정 분석 JSON에 이미 계산된 값의 표시다. 판정과 primary 분석은 변경하지 않았다. CPU seconds는 에너지 소비가 아니다.\n\n| 캠페인 | 조건 | arm | HTTP wall s | process CPU s | CPU s/token |\n|---|---|---|---:|---:|---:|\n'+'\n'.join(rows)+'\n\n실제 cpu25 소비 범위(각 arm 8 measured windows, core):\n\n| 캠페인 | arm | 최소 | 최대 |\n|---|---|---:|---:|\n'+'\n'.join(loads)+'\n\n기존 response timings는 slot별 prompt_n/prompt_ms와 predicted_n/predicted_ms의 비율이다. A 소스의 get_timings 및 첫 생성 token에서의 timer 전환을 확인했고, 양 arm의 모든 warmup/측정 응답 1,024개에서 해당 비율을 재계산했다. slot별 시간은 다른 slot과 겹칠 수 있으므로 phase 전체 처리량이나 exclusive CPU 실행시간으로 합산하지 않는다. 구체적인 source/hash/formula는 evidence/response-timing-definition.json에 있다. 이 값들은 성공 판정에 사용하지 않았다.\n')
(D/'OFFLINE_RECALCULATION.md').write_text('# 원시 수치의 별도 재계산\n\n검토 ZIP을 풀고 그 폴더에서 다음을 실행하면 모델이나 runtime 실행 없이 표의 paired gain과 층화 bootstrap CI를 다시 계산한다. Python 표준 라이브러리만 사용한다.\n\n```bash\npython3 -B code/recalculate.py --name confirmation-v1\n```\n\ncode/recalculate.py는 저장된 actual token 배열과 monotonic start/end에서 각 처리량을 다시 구하고, 별도의 산술 코드로 block gain/CI를 대조한다. 원본 workspace의 library inode/hash·환경까지 검사하는 전체 감사는 `./reproduce.sh analyze --name confirmation-v1`이다. 실제 추론 재현은 기존 통합 workspace와 model을 필요로 하며 `verify / smoke / full` 명령을 사용한다.\n')
print('Auxiliary response formulas verified:',checked)
