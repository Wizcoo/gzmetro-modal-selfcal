from common import *

def files():
 def include(p):
  rel=p.relative_to(O).as_posix()
  return not any(k in p.relative_to(O).parts for k in ['__pycache__','.work']) and not rel.startswith('full_metrics/old_') and rel not in ['key_chain_metrics_old.csv','report_facts.json']
 return sorted(p for p in O.rglob('*') if p.is_file() and include(p))

def main():
 lock=json.loads((O/'implementation_freeze.json').read_text())
 for p in files():
  if p.suffix in ['.md','.py','.cpp','.h','.json','.csv'] or p.name in ['.gitignore','.gitattributes']:
   s=p.read_text(encoding='utf-8');p.write_text(s,encoding='utf-8',newline='\n')
 for file,h in lock['algorithm_SHA256'].items():assert sha(O/'scripts'/file)==h
 for p in files():
  assert p.stat().st_size<2000000,(p.name,p.stat().st_size)
  if p.suffix=='.json':json.loads(p.read_text(encoding='utf-8'),parse_constant=lambda s:(_ for _ in ()).throw(ValueError(s)))
  if p.suffix=='.csv':assert len(pd.read_csv(p).columns)>0
  assert p.suffix not in ['.db','.bin','.exe','.dll','.pkl','.gz','.pyc']
 for f in ['validation.json','evidence_validation.json','mode_metric_validation.json']:assert json.loads((O/f).read_text())['passed']
 rows=[{'path':str(p.relative_to(O)).replace('\\','/'),'bytes':p.stat().st_size,'SHA256':sha(p)} for p in files() if p.name!='artifact_catalog.csv'];write(pd.DataFrame(rows),'artifact_catalog.csv');print('PACKAGED',len(rows)+1,'files',sum(r['bytes'] for r in rows),'bytes; max',max(r['bytes'] for r in rows),'UTF8 LF, all <2MB')

if __name__=='__main__':main()
