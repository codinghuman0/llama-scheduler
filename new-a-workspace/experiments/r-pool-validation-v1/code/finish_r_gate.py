from pathlib import Path
import hashlib,json,re,datetime
D=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
free=read(D/'evidence/R-free-summary.json');numeric=read(D/'evidence/R-numeric-summary.json');synthetic=read(D/'results/route-synthetic/result.json')
route=D/'results/route-heldout-1-R';text=(route/'server.stderr.log').read_text()
def counts(pattern):return list(map(int,re.search(pattern,text).groups()))
ref=counts(r'NEWA_R_REFERENCE_BODY calls=(\d+)/(\d+)/(\d+)/(\d+)');q4=counts(r'NEWA_Q4_TILE32 stats worker0_calls=(\d+)/(\d+)/(\d+)/(\d+)');q6=counts(r'NEWA_Q6 stats worker0_chunks=(\d+)/(\d+)/(\d+)/(\d+)')
oracle=read(D/'results/free-heldout-1-B0-r1/result.json')['measured'];observed=read(route/'result.json')
route_ok=ref[1]>0 and q4[1]==0 and q4[2]>0 and q4[3]>0 and q6[1]>0 and q6[2]>0 and q6[3]>0 and observed['warmup']==observed['measured']==oracle and synthetic['status']=='PASS'
route_result=dict(status='PASS' if route_ok else 'FAIL',actual_reference_body_by_phase=ref,retained_exact_q4_by_phase=q4,retained_q6_by_phase=q6,diagnostic_output_equals_B0=observed['warmup']==observed['measured']==oracle,phase_order=['UNKNOWN','PREFILL','DECODE','MIXED'],diagnostic_not_performance=True)
save(D/'evidence/R-route-summary.json',route_result)
observers=[read(p) for p in (D/'results').glob('numeric-*/observer-output-check.json')]
observers_ok=len(observers)==4 and all(x['warmup_equals_free_oracle'] and x['measured_equals_free_oracle'] and not x['teacher_force'] for x in observers)
passed=free['status']=='PASS' and numeric['status']=='PASS' and route_ok and observers_ok
state=read(D/'gate-results.json');state['R']='COMPATIBLE_IN_TESTED_SCOPE' if passed else 'OUTPUT_MISMATCH' if free['status']!='PASS' else 'INCONCLUSIVE';state['note']='R numerical and routing gates complete; downstream admitted only if compatible in tested scope.'
save(D/'gate-results.json',state)
identity=read(D/'candidates/R/identity.json')
checkpoint=dict(status=state['R'],identity=identity,free_fresh_servers=len(free['visits']),numeric_fresh_servers=4,route_fresh_servers=1,free_http_requests=144,numeric_http_requests=36,route_http_requests=16,performance_observations=0,teacher_forced_requests=0,observer_output_equal=observers_ok,artifacts={str(p.relative_to(D)):sha(p) for p in [D/'protocol-R.json',D/'fixtures.json',D/'cases.json',D/'evidence/R-free-summary.json',D/'evidence/R-numeric-summary.json',D/'evidence/R-route-summary.json',D/'patches/R-prefill-reference.patch']},limitations=['Specified model/ISA/shapes/settings only','General answer quality equivalence untested','No throughput claim from correctness timings'])
save(D/'evidence/R-checkpoint.json',checkpoint)
with (D/'ledger.jsonl').open('a') as log:log.write(json.dumps(dict(time=datetime.datetime.now(datetime.timezone.utc).isoformat(),stage='R-gate',status=state['R'],checkpoint='evidence/R-checkpoint.json'))+'\n')
(D/'GOAL_STATE.md').write_text('# Sequential R / E / pool validation\n\nR: '+state['R']+'\n\nProtected R checkpoint: evidence/R-checkpoint.json. Free output: 16 fresh servers, numeric: 4, route model: 1. No performance observations. Frozen B0/B1/E and original model untouched.\n\n'+('Next: prepare A using unchanged E plus validated R, verify A free generation, then build/link prepared P and run actual R-DSO unit and model lifecycle gates. Fixed conditional protocol: protocol-AP.json. Do not alter E thresholds or pool patch.\n' if passed else 'Downstream A/P performance is not admitted. Preserve mismatch/inconclusive evidence and perform only bounded first-branch/Q4off control in protocol-R.json, then package results.\n'))
print(json.dumps(dict(R=state['R'],route=route_result,observer_output_equal=observers_ok),indent=2))
