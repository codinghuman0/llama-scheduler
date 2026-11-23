from pathlib import Path
import collections,datetime,fcntl,gzip,hashlib,io,json,os,shutil,subprocess,tarfile,time,zipfile
W=Path(__file__).resolve().parents[2];D=Path(__file__).resolve().parent
OLD=W/'archive/legacy.zip';NEW=W/'archive/legacy.tar.xz'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def save(n,v):(D/n).write_text(json.dumps(v,indent=2)+'\n')
def safe(p):
 return '__pycache__' in p.split('/') or p.endswith(('.pyc','.pyo','.obj','.pch')) or (p.endswith('.o') and not p.endswith('.bpf.o') and '/obj/' in p)
with (W/'state/.measurement.lock').open('rb') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 assert os.getuid()!=0 and Path('/sys/kernel/sched_ext/state').read_text().strip()=='disabled'
 assert not NEW.exists()
 before=json.loads((W/'config/package-manifest.json').read_text())
 assert sha(OLD)==before['archive_sha256']
 save('manifest-before.json',before)
 save('storage-before.json',{'available':shutil.disk_usage(W).free,'archive_bytes':OLD.stat().st_size,'lock_inode':lock.fileno() and os.fstat(lock.fileno()).st_ino})
 with zipfile.ZipFile(OLD) as z:
  m=json.loads(z.read('manifest.json'));refs=collections.defaultdict(list)
  for p,v in m['entries'].items():
   if v['type']=='file':refs[v['sha256']].append(p)
  remove={b for b,ps in refs.items() if all(safe(p) for p in ps)}
  removed={p:dict(m['entries'][p]) for b in remove for p in refs[b]}
  save('removed-build-cache.json',{'reason':'Regenerable compiler intermediates and Python bytecode only; BPF payloads, executables, DSOs, sources, raw results and Git objects retained','files':removed,'blobs':len(remove),'old_compressed_bytes':sum(z.getinfo('blobs/'+b).compress_size for b in remove)})
  for p in removed:m['entries'][p]['type']='removed_build_cache'
  m['maintenance']={'operation':'solid recompression and conservative intermediate cleanup','removed_manifest':'maintenance/self-contained-20261122/removed-build-cache.json','original_archive_sha256':before['archive_sha256']}
  manifest=json.dumps(m,separators=(',',':')).encode();kept={b:ps for b,ps in refs.items() if b not in remove}
  order=sorted(kept,key=lambda b:(Path(kept[b][0]).name,kept[b][0]))
  started=time.monotonic();last=started
  with NEW.open('xb') as dst:
   xz=subprocess.Popen(['xz','-T2','-6','--block-size=64MiB','--memlimit-compress=512MiB','-c'],stdin=subprocess.PIPE,stdout=dst,stderr=(D/'xz.stderr').open('w'),start_new_session=True)
   try:
    with tarfile.open(fileobj=xz.stdin,mode='w|',format=tarfile.PAX_FORMAT) as tar:
     info=tarfile.TarInfo('manifest.json');info.size=len(manifest);info.mode=0o644;tar.addfile(info,io.BytesIO(manifest))
     for idx,b in enumerate(order,1):
      data=z.read('blobs/'+b);assert hashlib.sha256(data).hexdigest()==b
      info=tarfile.TarInfo('blobs/'+b);info.size=len(data);info.mode=0o644;tar.addfile(info,io.BytesIO(data))
      if time.monotonic()-last>20:print('Repacked',idx,'/',len(order),'output bytes',NEW.stat().st_size,flush=True);last=time.monotonic()
    xz.stdin.close();assert xz.wait(timeout=120)==0
   except BaseException:
    xz.kill();xz.wait();raise
  print('Verifying all retained blobs...',flush=True)
  found=set()
  with tarfile.open(NEW,'r|xz') as tar:
   for member in tar:
    f=tar.extractfile(member);h=hashlib.sha256()
    for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    if member.name=='manifest.json':assert h.digest()==hashlib.sha256(manifest).digest()
    else:
     b=member.name.removeprefix('blobs/');assert b in kept and h.hexdigest()==b;found.add(b)
  assert found==set(kept)
  save('archive-verification.json',{'status':'PASS','retained_unique_blobs':len(found),'retained_file_paths':sum(len(x) for x in kept.values()),'removed_intermediate_paths':len(removed),'original_zip_still_present':True,'archive_sha256':sha(NEW),'archive_bytes':NEW.stat().st_size,'old_archive_bytes':OLD.stat().st_size,'potential_saving_bytes':OLD.stat().st_size-NEW.stat().st_size,'elapsed_s':time.monotonic()-started})
  print((D/'archive-verification.json').read_text(),flush=True)
