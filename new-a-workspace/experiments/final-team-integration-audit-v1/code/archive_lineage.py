"""Read selected Git objects in memory; never extract a full history or run code."""
import hashlib,json,struct,tarfile,zlib,subprocess
from pathlib import Path
D=Path(__file__).resolve().parents[1]; W=D.parents[1]
index=json.loads((D/'evidence/archive-index.json').read_text())['entries']
prefix='llama.cpp-lightweight/.git/objects/pack/pack-010af88d0b8162944926efe4fbef420ed37261cb'
needed={index[prefix+s]['sha256']:s for s in ['.idx','.pack']}
data={}
with tarfile.open(W/'archive/legacy.tar.xz','r|xz') as tar:
 for member in tar:
  digest=member.name.removeprefix('blobs/')
  if digest not in needed:continue
  value=tar.extractfile(member).read();assert hashlib.sha256(value).hexdigest()==digest
  data[needed[digest]]=value
  if len(data)==2:break
idx=data['.idx'];pack=data['.pack'];assert idx[:8]==b'\xfftOc\x00\x00\x00\x02'
n=struct.unpack_from('>I',idx,8+255*4)[0]; sha_start=8+1024; off_start=sha_start+n*24
offsets={}; reverse={}
for i in range(n):
 sha=idx[sha_start+i*20:sha_start+(i+1)*20].hex();off=struct.unpack_from('>I',idx,off_start+i*4)[0]
 if off&0x80000000:off=struct.unpack_from('>Q',idx,off_start+n*4+(off&0x7fffffff)*8)[0]
 offsets[sha]=off;reverse[off]=sha
cache={}; types={1:'commit',2:'tree',3:'blob',4:'tag'}
def varint(buf,pos):
 value=0;shift=0
 while True:
  c=buf[pos];pos+=1;value|=(c&127)<<shift;shift+=7
  if not c&128:return value,pos
def delta(base,ops):
 source,p=varint(ops,0);size,p=varint(ops,p);assert source==len(base);out=bytearray()
 while p<len(ops):
  cmd=ops[p];p+=1
  if cmd&128:
   off=0;length=0
   for bit in range(4):
    if cmd&(1<<bit):off|=ops[p]<<(8*bit);p+=1
   for bit in range(3):
    if cmd&(1<<(4+bit)):length|=ops[p]<<(8*bit);p+=1
   length=length or 65536;assert off+length<=len(base);out.extend(base[off:off+length])
  else:assert cmd;out.extend(ops[p:p+cmd]);p+=cmd
 assert len(out)==size;return bytes(out)
def obj(sha):
 if sha in cache:return cache[sha]
 off=offsets[sha];p=off;c=pack[p];p+=1;typ=(c>>4)&7;size=c&15;shift=4
 while c&128:c=pack[p];p+=1;size|=(c&127)<<shift;shift+=7
 base=None
 if typ==6:
  c=pack[p];p+=1;back=c&127
  while c&128:c=pack[p];p+=1;back=((back+1)<<7)+(c&127)
  base=reverse[off-back]
 elif typ==7:base=pack[p:p+20].hex();p+=20
 inflater=zlib.decompressobj();chunks=[]
 while not inflater.eof:
  chunk=memoryview(pack)[p:p+65536];assert chunk;chunks.append(inflater.decompress(chunk));p+=len(chunk)
 body=b''.join(chunks);assert len(body)==size
 if base:typ,b=obj(base);body=delta(b,body)
 assert hashlib.sha1((types[typ]+' '+str(len(body))+'\0').encode()+body).hexdigest()==sha
 cache[sha]=(typ,body);return typ,body
def tree(sha):
 typ,b=obj(sha);assert typ==2;rows={};p=0
 while p<len(b):
  end=b.index(b'\0',p);mode,name=b[p:end].split(b' ',1);oid=b[end+1:end+21].hex();rows[name.decode()]=(mode.decode(),oid);p=end+21
 return rows
def metadata(sha):
 typ,body=obj(sha);assert typ==1;headers,message=body.decode().split('\n\n',1)
 values={}
 for line in headers.splitlines():
  key,_,value=line.partition(' ');values.setdefault(key,[]).append(value)
 return dict(sha=sha,headers=values,message=message)
def file_at(commit,path):
 oid=metadata(commit)['headers']['tree'][0]
 for name in path.split('/'):oid=tree(oid)[name][1]
 typ,body=obj(oid);assert typ==3;return oid,body
head='59abec45fe0919de20550ce7cdcf363d9f7bbe5a'; history=[];sha=head
for _ in range(32):
 if sha not in offsets:break
 row=metadata(sha);history.append(row)
 parents=row['headers'].get('parent',[])
 if not parents:break
 sha=parents[0]
 if sha=='7a2db1a0cf38e5f4eb278a58c3903d295258d0ea':history.append(metadata(sha));break
paths=['include/llama.h','src/llama-context.cpp','src/llama-context.h','src/llama-compute-profile.h','tools/server/server-context.cpp','tools/server/server-common.h','tools/server/server-scx.h','tools/server/CMakeLists.txt','ggml/src/ggml-cpu/ggml-cpu.c','ggml/src/ggml-cpu/ggml-cpu.cpp']
files=[]
for path in paths:
 try:oid,body=file_at(head,path)
 except KeyError:continue
 dest=D/'sources/base-59abec4'/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(body)
 files.append(dict(commit=head,path=path,git_blob=oid,sha256=hashlib.sha256(body).hexdigest(),output=str(dest.relative_to(D))))
changes=[]
for row in history[:-1]:
 parents=row['headers'].get('parent',[])
 if not parents or parents[0] not in offsets:continue
 for path in paths:
  try:a,b=file_at(row['sha'],path)
  except KeyError:continue
  try:old,_=file_at(parents[0],path)
  except KeyError:old=None
  if a!=old:
   rec=dict(commit=row['sha'],parent=parents[0],path=path,blob=a,parent_blob=old);changes.append(rec)
   dest=D/'sources/history'/row['sha'][:12]/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(b)
out=dict(archive_sha256='6beabfdf3924774d3dae560662d2c63c342706ae387715283d65936b43ec7bc6',pack_sha256=index[prefix+'.pack']['sha256'],idx_sha256=index[prefix+'.idx']['sha256'],objects_in_pack=n,objects_decoded_and_SHA1_verified=len(cache),scope='bounded first-parent 32 commits or historical B0, selected files only; full pack read only in memory',history=history,files=files,changes=changes)
(D/'evidence/local-git-lineage.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(commits=[dict(sha=x['sha'],subject=x['message'].splitlines()[0]) for x in history],changed_files=changes,verified_objects=len(cache)),ensure_ascii=False))
