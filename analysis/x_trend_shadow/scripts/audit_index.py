from common import *
import subprocess

def main():
 data=subprocess.check_output(['git','ls-files','--stage','-z'],cwd=R);entries=[];prefix='analysis/x_trend_shadow/';excluded=['artifact_catalog.csv','git_index_validation.json']
 changed=subprocess.check_output(['git','diff','--cached','--name-only','-z'],cwd=R).decode('utf-8').split('\0');assert all(not p or p.startswith(prefix) for p in changed)
 for record in data.split(b'\0'):
  if not record:continue
  meta,p=record.split(b'\t',1);name=p.decode('utf-8');mode,oid,stage=meta.decode().split()
  if not name.startswith(prefix) or name[len(prefix):] in excluded:continue
  file=R/name;h=hashlib.sha1();size=file.stat().st_size;h.update(b'blob '+str(size).encode()+b'\0')
  with file.open('rb') as f:
   for b in iter(lambda:f.read(4194304),b''):h.update(b)
  assert h.hexdigest()==oid,(name,'Git byte conversion or stale staged file');assert stage=='0';assert '.work/' not in name and '__pycache__' not in name;entries.append(name)
 cat=pd.read_csv(O/'artifact_catalog.csv');mapping=dict(zip(cat.path,cat.SHA256))
 for path in entries:
  rel=path[len(prefix):];assert sha(R/path)==mapping[rel],rel
 save_json({'passed':True,'verified_staged_files':len(entries),'Git_blob_bytes_equal_working_copy':True,'SHA256_equal_artifact_catalog':True,'staged_paths_only':'analysis/x_trend_shadow/','excluded_self_describing_files':excluded,'reason_for_exclusions':'catalog and this certificate describe the verified payload; no self-hash cycle','production_or_DB_staged':False},'git_index_validation.json');print('INDEX PASS',len(entries))

if __name__=='__main__':main()
