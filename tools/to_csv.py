"""Convert one exported table's parts to a single CSV without loading it all."""
import argparse,csv,gzip,json
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('parts',nargs='+',type=Path);p.add_argument('--output',type=Path,required=True)
a=p.parse_args();a.output.parent.mkdir(parents=True,exist_ok=True)
writer=None;columns=None
with a.output.open('w',encoding='utf-8-sig',newline='') as out:
    for part in sorted(a.parts):
        with gzip.open(part,'rt',encoding='utf-8') as f:
            for line in f:
                row=json.loads(line)
                if writer is None:
                    columns=list(row);writer=csv.DictWriter(out,fieldnames=columns);writer.writeheader()
                if list(row)!=columns:raise ValueError('Combine only parts of the same schema/table')
                writer.writerow({k:'\\N' if v is None else json.dumps(v,ensure_ascii=False) if isinstance(v,dict) else v for k,v in row.items()})
print(a.output)
