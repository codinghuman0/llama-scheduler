from pathlib import Path
import hashlib,json,os,shutil
W=Path(__file__).resolve().parents[2];D=Path(__file__).resolve().parent
for name in ['README.md','tools/archive.py','tools/verify.py','tools/run.py']:
 p=D/'before'/name;p.parent.mkdir(parents=True,exist_ok=True);assert not p.exists();shutil.copy2(W/name,p)
model=W.parent/'model.gguf';target=W/'models/model.gguf';target.parent.mkdir(exist_ok=True)
assert not target.exists();os.link(model,target)
p=W/'tools/run.py';s=p.read_text();assert "default=ROOT.parent/'model.gguf'" in s;s=s.replace("default=ROOT.parent/'model.gguf'","default=ROOT/'models/model.gguf'");p.write_text(s)
p=W/'tools/verify.py';s=p.read_text();s=s.replace("p.add_argument('--model',type=Path)","p.add_argument('--model',type=Path,default=ROOT/'models/model.gguf')")
s=s.replace("sha(ROOT/'archive/legacy.zip')","sha(ROOT/m.get('archive_path','archive/legacy.zip'))")
p.write_text(s)
