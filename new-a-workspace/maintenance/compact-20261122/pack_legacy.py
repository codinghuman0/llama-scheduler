from pathlib import Path,PurePosixPath
import os,stat,hashlib,json,zipfile,tarfile,tempfile,fcntl,datetime,subprocess
W=Path('/home/codinghuman/projects/new-a-workspace');D=Path(__file__).resolve().parent
ROOTS=['llama.cpp-lightweight','new-a-llm-scheduler','new-a-lab','new-a-performance','new-a-runs','llama-ngram-shortcut']
ARCH=W/'archive/legacy.zip';assert not ARCH.exists()
def sha(f):
 h=hashlib.sha256()
 for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def disk():
 v=os.statvfs(W);return v.f_bavail*v.f_frsize
with (W/'new-a-runs/.measurement.lock').open('rb') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 assert Path('/sys/kernel/sched_ext/state').read_text().strip()=='disabled'
 snapshot=[];manifest={};known=set();archive_hashes={};archive_errors=[];counts={'files':0,'symlinks':0,'expanded_archives':0,'blobs':0}
 before=disk()
 for n in ROOTS+['README.md','workspace.py','llama.cpp','model.gguf']:
  base=W/n
  if base.is_symlink() or base.is_file():paths=[base]
  else:
   paths=[]
   for root,ds,fs in os.walk(base,followlinks=False):
    assert not os.path.ismount(root)
    for child in list(ds):
     p=Path(root)/child
     if p.is_symlink():paths.append(p);ds.remove(child)
    paths.extend(Path(root)/f for f in fs)
  for p in paths:
   s=p.lstat();r={'path':str(p.relative_to(W)),'mode':s.st_mode,'size':s.st_size,'mtime_ns':s.st_mtime_ns,'dev':s.st_dev,'inode':s.st_ino,'allocated':s.st_blocks*512}
   if p.is_symlink():r.update(type='symlink',target=os.readlink(p))
   else:
    assert stat.S_ISREG(s.st_mode),p
    with p.open('rb') as f:r.update(type='file',sha256=sha(f))
   snapshot.append(r)
 (D/'snapshot-before.json').write_text(json.dumps(snapshot,separators=(',',':')))
 with zipfile.ZipFile(ARCH,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
  def blob(path,digest):
   if digest in known:return
   z.write(path,'blobs/'+digest,compress_type=zipfile.ZIP_STORED if path.suffix=='.pack' else zipfile.ZIP_DEFLATED)
   known.add(digest);counts['blobs']+=1
  def stream_blob(stream,size):
   with tempfile.NamedTemporaryFile(dir=D,prefix='member-',delete=True) as tmp:
    h=hashlib.sha256();total=0
    while True:
     b=stream.read(1024*1024)
     if not b:break
     h.update(b);tmp.write(b);total+=len(b)
    assert total==size
    tmp.flush();digest=h.hexdigest();blob(Path(tmp.name),digest)
   return digest
  def member_path(outer,name):
   p=PurePosixPath(name)
   assert not p.is_absolute() and '..' not in p.parts,(outer,name)
   return outer+'!/'+str(p)
  for i,r in enumerate(snapshot):
   name=r['path'];p=W/name
   if r['type']=='symlink':manifest[name]=dict(r);counts['symlinks']+=1;continue
   # Exact outer archive bytes are redundant. Preserve every expanded member and outer identity.
   expand=p.name.endswith(('.tar.gz','.tgz','.tar.xz','.tar.zst','.zip')) and '/.git/' not in name
   if expand:
    children=[]
    try:
     if p.suffix=='.zip':
      with zipfile.ZipFile(p) as src:
       assert src.testzip() is None
       for m in src.infolist():
        if m.is_dir():continue
        key=member_path(name,m.filename);mode=(m.external_attr>>16) or 0o100644
        with src.open(m) as f:
         if stat.S_ISLNK(mode):rec={'type':'symlink','target':f.read().decode(),'mode':mode}
         else:rec={'type':'file','sha256':stream_blob(f,m.file_size),'size':m.file_size,'mode':mode}
        manifest[key]=rec;children.append(key)
     else:
      with tarfile.open(p,'r:*') as src:
       for m in src:
        if m.isdir():continue
        key=member_path(name,m.name)
        if m.issym():rec={'type':'symlink','target':m.linkname,'mode':stat.S_IFLNK|m.mode}
        elif m.islnk():rec={'type':'hardlink','target':member_path(name,m.linkname),'mode':stat.S_IFREG|m.mode}
        elif m.isfile():
         with src.extractfile(m) as f:rec={'type':'file','sha256':stream_blob(f,m.size),'size':m.size,'mode':stat.S_IFREG|m.mode}
        else:raise ValueError('Unsupported archive member '+m.name)
        manifest[key]=rec;children.append(key)
     manifest[name]={**r,'type':'expanded_archive','children':children,'note':'Original compressed container omitted; original SHA recorded, members preserved. Restore members, not byte-identical container.'};counts['expanded_archives']+=1
    except (tarfile.TarError,zipfile.BadZipFile,ValueError,AssertionError,OSError) as e:
     archive_errors.append({'path':name,'reason':str(e),'fallback':'Preserve exact outer bytes'});blob(p,r['sha256']);manifest[name]=r
   else:blob(p,r['sha256']);manifest[name]=r
   counts['files']+=1
   if i%5000==0:print(json.dumps({'progress':i,'total':len(snapshot),'counts':counts,'free':disk()}),flush=True)
  z.writestr('manifest.json',json.dumps({'version':1,'root_before':str(W),'entries':manifest,'roots':ROOTS,'counts':counts,'archive_expansion_fallbacks':archive_errors},separators=(',',':')))
 print('ARCHIVE_WRITTEN_VERIFYING',flush=True)
 with zipfile.ZipFile(ARCH) as z:
  assert z.testzip() is None
  for digest in known:
   with z.open('blobs/'+digest) as f:assert sha(f)==digest,digest
  verify=json.loads(z.read('manifest.json'));assert len(verify['entries'])==len(manifest)
  for r in snapshot:
   v=verify['entries'][r['path']]
   assert v.get('sha256')==r.get('sha256') and v['mode']==r['mode']
   if v['type']=='file':assert 'blobs/'+v['sha256'] in z.namelist()
 with ARCH.open('rb') as f:archive_sha=sha(f)
 result={'status':'PASS','archive':str(ARCH),'archive_sha256':archive_sha,'archive_bytes':ARCH.stat().st_size,'original_entries':len(snapshot),'archived_entries':len(manifest),'counts':counts,'free_before':before,'free_after_archive':disk(),'fallbacks':archive_errors,'original_roots':ROOTS,'archive_wrappers':'Expanded container SHA retained as historical metadata; all members preserved. No byte-exact outer-container claim.'}
 (D/'archive-check.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2),flush=True)
