from common import *

def main():
 validation=json.loads((O/'validation.json').read_text());assert validation['passed'];rows=[]
 for p in sorted(O.rglob('*')):
  if not p.is_file() or '.work' in p.parts or '__pycache__' in p.parts or p.name=='artifact_catalog.csv':continue
  assert p.suffix.lower() not in ['.exe','.dll','.pkl','.bin','.db','.sqlite'],p
  assert p.stat().st_size<2000000,(p,p.stat().st_size)
  if p.suffix.lower()!='.png':p.read_text(encoding='utf-8')
  rows.append(dict(path=p.relative_to(O).as_posix(),bytes=p.stat().st_size,SHA256=sha(p)))
 save(rows,'artifact_catalog.csv');print('ARTIFACTS',len(rows),'BYTES',sum(r['bytes'] for r in rows),'MAX',max(r['bytes'] for r in rows))

if __name__=='__main__':main()
