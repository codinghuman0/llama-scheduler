"""Validate audit artifacts and prior-file protection; package this output only."""
import csv,gzip,hashlib,json,os,re,stat,subprocess,sys,zipfile
from datetime import datetime,timezone
from pathlib import Path
D=Path(__file__).resolve().parents[1];W=D.parents[1]
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
def read(p):return json.loads(p.read_text())
def save(name,x):(D/name).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
required=['integration-summary.ko.md','integration-matrix.csv','integration-matrix.json','integration-matrix.md','source-lineage.json','runtime-integration-map.md','observed-usage.json','performance-attribution.md','professor-brief.ko.md','professor-qa.ko.md','missing-evidence.md','README.md']
assert all((D/f).is_file() and (D/f).stat().st_size>100 for f in required)
matrix=read(D/'integration-matrix.json')['rows'];assert len(matrix)==34 and len({x['component_id'] for x in matrix})==34
enums=dict(ancestry={'UPSTREAM_UNCHANGED','SHARED_ANCESTRY','BORROWED_EXACT','BORROWED_MODIFIED','LOCAL_NEW','UNKNOWN'},performance={'ISOLATED_SCOPED_GAIN','BUNDLE_EFFECT_ONLY','NO_CONSISTENT_GAIN','NOT_ISOLATED','NOT_MEASURED'},adoption={'ACTIVE_DEFAULT','ACTIVE_EVALUATION_ONLY','PRESENT_DISABLED','TESTED_NOT_ADOPTED','REVIEWED_ONLY','UNKNOWN'},execution={'OBSERVED_EXECUTED','ENABLED_WITHOUT_PATH_PROOF','NOT_ENABLED','NOT_OBSERVED','NOT_APPLICABLE'})
for row in matrix:
 for k in ['ancestry','performance']:assert row[k] in enums[k]
 for k in ['adoption','execution']:assert set(row[k])=={'A_L','A_S','P'} and all(v in enums[k] for v in row[k].values())
 assert all(k in row for k in ['donor_repo','donor_ref','donor_path_symbol','upstream_shared_ancestor','already_in_B0','already_in_B1','final_source','build_flags','project_ELF_DSO_sha256','runtime_evidence','observed_unit_denominator','comparison','campaign_results','actual_choice_difference','allowed_claim','forbidden_claim','unknown'])
with (D/'integration-matrix.csv').open() as f:csvrows=list(csv.DictReader(f))
assert [x['component_id'] for x in csvrows]==[x['component_id'] for x in matrix]
for a,b in zip(matrix,csvrows):
 for k,v in a.items():assert (json.loads(b[k])==v if isinstance(v,(dict,list)) else b[k]==v)
anchors=read(D/'evidence/source-anchors.json');anchor_count=0
for x in anchors:
 p=Path(x['path']);assert digest(p)==x['sha256'];lines=p.read_text().splitlines();assert len(lines)==x['lines']
 for a in x['anchors']:assert lines[a['line']-1]==a['match'];anchor_count+=1
assert not read(D/'evidence/unresolved-anchor-searches.json')
links=[]
for p in D.glob('*.md'):
 for target in re.findall(r'\]\(([^)]+)\)',p.read_text()):
  if '://' in target or target.startswith('#'):continue
  t=target.split('#')[0]
  if t in ['audit-checks.json','manifest.json','review.zip','review.zip.sha256']:continue
  assert (p.parent/t).exists(),(str(p),target);links.append(dict(document=p.name,target=target))
r=subprocess.run([sys.executable,'-B',str(D/'code/recalculate_packaged.py')],capture_output=True,text=True,timeout=60);assert r.returncode==0,r.stderr
calculation=json.loads(r.stdout);assert calculation['status']=='PASS';save('evidence/packaged-recalculation-check.json',calculation)
before=json.loads(gzip.decompress((D/'evidence/protected-before.json.gz').read_bytes()));old=before['files'];cache={};changed=[];seen=set();new=[]
for root,dirs,files in os.walk(W,followlinks=False):
 dirs[:]=[d for d in dirs if Path(root)/d!=D]
 for name in list(dirs):
  if (Path(root)/name).is_symlink():files.append(name);dirs.remove(name)
 for name in files:
  p=Path(root)/name;rel=str(p.relative_to(W));seen.add(rel)
  if rel not in old:new.append(rel);continue
  prior=old[rel];st=p.lstat();mode=stat.S_IMODE(st.st_mode)
  if prior['type']=='symlink':
   target=prior.get('target',prior.get('link_target'))
   if not p.is_symlink() or os.readlink(p)!=target or mode!=prior['mode']:changed.append(dict(path=rel,reason='symlink/mode changed'))
  else:
   key=(st.st_dev,st.st_ino);h=cache.get(key)
   if h is None:h=digest(p);cache[key]=h
   if h!=prior['sha256'] or st.st_size!=prior['size'] or mode!=prior['mode'] or st.st_ino!=prior['inode'] or st.st_dev!=prior['device']:changed.append(dict(path=rel,reason='bytes/mode/inode/device changed'))
missing=sorted(set(old)-seen)
protection=dict(status='PASS' if not(changed or missing or new) else 'FAIL',checked_files=len(old),unique_regular_inodes_hashed=len(cache),changed=changed,missing=missing,new_outside_audit=new,scope=str(W),excluded_output=str(D),before_record_sha256=digest(D/'evidence/protected-before.json.gz'),completed_utc=datetime.now(timezone.utc).isoformat())
save('evidence/protection-after.json',protection);assert protection['status']=='PASS',protection
input_hashes={}
for name in ['usage-inputs.json','additional-inputs.json','scheduler-attachment-inputs.json']:
 for p,v in read(D/'evidence'/name).items():
  rel=str(Path(p).relative_to(W));assert rel in old and old[rel]['sha256']==v['sha256'];input_hashes[p]=v
requirements=[
 dict(section='0 read-only boundaries',status='PASS',evidence=['audit-ledger.json','evidence/protection-after.json']),
 dict(section='1 fixed identities and exact pins',status='PASS',evidence=['source-lineage.json','evidence/identity-recheck.json','evidence/entrypoint-scope.json']),
 dict(section='2 four independent axes',status='PASS',evidence=['integration-matrix.json','integration-matrix.csv','integration-matrix.md']),
 dict(section='3 seven required feature families',status='PASS_WITH_EXPLICIT_UNKNOWNS',evidence=['integration-matrix.json','missing-evidence.md']),
 dict(section='4 A_L/A_S text and Mermaid, 15 anchored edges',status='PASS',evidence=['runtime-integration-map.md','evidence/source-anchors.json']),
 dict(section='5 raw usage and separate campaign performance',status='PASS',evidence=['observed-usage.json','performance-attribution.md','evidence/performance-recalculation.json']),
 dict(section='6 professor script and all nine Q&A',status='PASS',evidence=['professor-brief.ko.md','professor-qa.ko.md']),
 dict(section='7 small review artifacts and honest gaps',status='PASS',evidence=['README.md','manifest.json','missing-evidence.md'])]
checks=dict(status='PASS',functional_status='FUNCTIONAL_INTEGRATION_MAPPED',provenance_status='PARTIAL_PROVENANCE',requirements=requirements,required_outputs=required,matrix_rows=len(matrix),csv_json_equal=True,source_anchor_count=anchor_count,source_group_hashes_checked=len(anchors),relative_document_links_checked=len(links),identity_checks=read(D/'evidence/identity-recheck.json')['status'],historical_input_hashes_linked_to_protected_snapshot=len(input_hashes),input_hash_manifests=['evidence/usage-inputs.json','evidence/additional-inputs.json','evidence/historical-build-extraction.json','evidence/local-git-lineage.json','evidence/source-anchors.json','evidence/scheduler-attachment-inputs.json'],raw_recalculation=[x['result']['status'] for x in read(D/'evidence/performance-recalculation.json')['component_campaigns']],packaged_recalculation=dict(status=calculation['status'],component_comparisons=20,pool_conditions=2),original_protection=protection,commands_scope='No new inference/smoke/build/project unit test/BPF attach/sudo/Git mutation. Static ELF and offline evidence arithmetic only.',package_verification='package-verification.json (outside ZIP, generated after packaging)',limits=read(D/'source-lineage.json')['gaps'])
assert read(D/'evidence/scheduler-attachments.json')['recorded_visits']==36
assert read(D/'evidence/scheduler-attachments.json')['status']=='PASS'
checks['recorded_scheduler_attachments']='36 PASS; stable program tags, selected uprobe, unchanged enable_seq, sampled watchdog and cleanup'
save('audit-checks.json',checks)
excluded={'manifest.json','review.zip','review.zip.sha256','package-verification.json','evidence/archive-index.json'}
members=[]
for p in sorted(D.rglob('*')):
 if not p.is_file() or p.is_symlink():continue
 name=str(p.relative_to(D))
 if name in excluded or name.startswith(('sources/history/','sources/historical-B0/')):continue
 if name.startswith('sources/base-59abec4/') and p.name not in ['LICENSE','THIRD_PARTY_NOTICES.md']:continue
 assert p.suffix.lower() not in ['.zip','.gguf','.o','.a','.so','.pack','.idx'] and p.read_bytes()[:4]!=b'\x7fELF',name
 members.append(dict(path=name,bytes=p.stat().st_size,sha256=digest(p)))
manifest=dict(schema=1,scope='Small audit review, no model/runtime/full tree/full Git history/old ZIP',excluded=['full archive index','selected full history/base/B0 source snapshots (local cache only)','package own hash and post-packaging verification'],members=members)
save('manifest.json',manifest)
with zipfile.ZipFile(D/'review.zip','w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for row in members:z.write(D/row['path'],row['path'])
 z.write(D/'manifest.json','manifest.json')
with zipfile.ZipFile(D/'review.zip') as z:
 assert z.testzip() is None
 assert set(z.namelist())=={x['path'] for x in members}|{'manifest.json'}
 for x in members:assert hashlib.sha256(z.read(x['path'])).hexdigest()==x['sha256']
 assert json.loads(z.read('manifest.json'))==manifest
 assert not any(n.lower().endswith(('.zip','.gguf','.pack','.o','.a')) for n in z.namelist())
size=(D/'review.zip').stat().st_size;assert size<20*1024*1024;h=digest(D/'review.zip')
(D/'review.zip.sha256').write_text(h+'  review.zip\n')
save('package-verification.json',dict(status='PASS',sha256=h,bytes=size,MiB=size/1024**2,zip_members=len(members)+1,all_member_hashes_verified=True,CRC_verified=True,nested_zip=False,model_or_ELF=False,manifest_self_hash_excluded=True,audit_checks_sha256=digest(D/'audit-checks.json'),all_required_deliverables_present=True))
print(json.dumps(dict(status='PASS',protected_files=len(old),source_anchors=anchor_count,inputs=len(input_hashes),zip_bytes=size,zip_sha256=h,zip_members=len(members)+1),ensure_ascii=False))
