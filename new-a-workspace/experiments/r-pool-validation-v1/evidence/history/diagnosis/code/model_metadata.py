import hashlib,json,os,struct
from pathlib import Path
D=Path(__file__).resolve().parents[1];os.sched_setaffinity(0,{11})
f=open('/home/codinghuman/projects/model.gguf','rb')
def num(fmt):return struct.unpack('<'+fmt,f.read(struct.calcsize('<'+fmt)))[0]
def string():return f.read(num('Q')).decode('utf-8')
def value(t):
 if t==8:return string()
 if t==9:
  subtype,count=num('I'),num('Q');return [value(subtype) for _ in range(count)]
 return num({0:'B',1:'b',2:'H',3:'h',4:'I',5:'i',6:'f',7:'?',10:'Q',11:'q',12:'d'}[t])
assert f.read(4)==b'GGUF';version=num('I');tensors,kv=num('Q'),num('Q');metadata={};arrays={};tokens=None
for _ in range(kv):
 key=string();t=num('I');v=value(t)
 if isinstance(v,list):
  arrays[key]=dict(count=len(v),canonical_json_sha256=hashlib.sha256(json.dumps(v,ensure_ascii=False,separators=(',',':')).encode()).hexdigest())
  if key=='tokenizer.ggml.tokens':tokens=v
 else:metadata[key]=v
wanted={k:v for k,v in metadata.items() if k.startswith('tokenizer.') and k.endswith('_token_id')}
selected={str(v):tokens[v] for v in set(wanted.values())|{128247,151643,151646,151662,151663,151664} if isinstance(v,int) and 0<=v<len(tokens)}
out=dict(gguf_version=version,tensors=tensors,metadata=metadata,array_summaries=arrays,special_token_text=selected,scope='GGUF header/metadata only. No tensor payload read or model execution; metadata name alone does not independently prove training provenance.')
(D/'evidence/model-metadata.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(name=metadata.get('general.name'),architecture=metadata.get('general.architecture'),tokenizer_ids=wanted,template=metadata.get('tokenizer.chat_template'),special_token_text=selected),ensure_ascii=False,indent=2))
