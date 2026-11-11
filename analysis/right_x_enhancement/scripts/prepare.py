from common import *
import subprocess,ast

def main():
    # Read prior text and tabular evidence, verify their catalog identity, and
    # record exact lineage rather than copying prior raw files into this PR.
    prior=[]
    for folder in ['right_x','right_x_yj_yxj']:
        base=R/'analysis'/folder;count=0;rows=0
        cat=base/'file_catalog.csv'
        if cat.exists():
            catalog=pd.read_csv(cat)
            pathcol='path' if 'path' in catalog else 'relative_path'
            for _,row in catalog.iterrows():
                p=base/row[pathcol]
                assert sha(p)==row.sha256,str(p)
        for p in base.rglob('*'):
            if not p.is_file() or any(x in p.parts for x in ['.cache','.work','__pycache__']):continue
            if p.suffix in ['.md','.py','.cpp','.h','.json']:text=p.read_text(encoding='utf-8');count+=1
            if p.suffix=='.py':ast.parse(text)
            if p.suffix=='.csv':rows+=len(pd.read_csv(p))
        prior.append({'analysis':folder,'text_files_read':count,'CSV_rows_read':rows,'catalog_verified':cat.exists()})
    write(pd.DataFrame(prior),'prior_evidence_review.csv')
    audit=[];geometry=[]
    for dev in DEVS:
        d=pd.read_pickle(C/f'Marker_{dev}.pkl');assert not d.ambiguous_business_key.any()
        names=sorted(d.markerName.unique());piv=d.pivot(index='timestamp',columns='markerName',values=['x','y','RoiCalState']);t=piv.index.to_numpy();x=piv.x.reindex(columns=names).to_numpy(float,copy=True);y=piv.y.reindex(columns=names).to_numpy(float,copy=True);ok=piv.RoiCalState.reindex(columns=names).to_numpy()==1;x[~ok]=np.nan;y[~ok]=np.nan
        p=W/f'{dev}.bin'
        with p.open('wb') as f:
            f.write(struct.pack('<I',len(names)))
            for n in names:b=n.encode();f.write(struct.pack('<I',len(b)));f.write(b)
            f.write(struct.pack('<I',len(t)))
            for j,ts in enumerate(t):f.write(struct.pack('<q',ts));f.write(x[j].astype('<f8').tobytes());f.write(y[j].astype('<f8').tobytes())
        audit.append({'device_id':dev,'frames':len(t),'points':len(names),'input_sha256':sha(p),'start_beijing':iso(t[0]),'end_beijing':iso(t[-1]),'validity':'RoiCalState==1 and finite; no ambiguous keys','name_order':'lexicographic; names embedded in binary'})
        with (W/f'{dev}.coords').open('w',encoding='utf-8',newline='\n') as f:
            f.write('2\n')
            for night in ['2026-11-05','2026-11-06']:
                st=epoch(night+' 22:00');g=d[d.timestamp.ge(st)&d.timestamp.lt(st+3600000)&d.RoiCalState.eq(1)];uv=[]
                for n in names:
                    z=g[g.markerName.eq(n)];stable=len(z)>=10 and z.centerX.nunique()==1 and z.centerY.nunique()==1;uv.append([z.centerX.iloc[0],z.centerY.iloc[0]] if stable else [np.nan,np.nan])
                    if n.startswith(('YJ','YXJ')):geometry.append({'device_id':dev,'night':night,'marker':n,'baseline_centerX_native':z.centerX.iloc[0] if len(z) else np.nan,'baseline_centerY_native':z.centerY.iloc[0] if len(z) else np.nan,'baseline_coordinate_stable':stable,'count':len(z),'unit':'native_unverified_not_world','semantic_limit':'stable recorded observation-coordinate proxy; DB writer and camera geometry unavailable'})
                uv=np.asarray(uv,float);center=np.nanmean(uv,axis=0);span=np.nanstd(uv,axis=0);uv=(uv-center)/np.maximum(span,1)
                nid=int(pd.Timestamp(night).timestamp()/86400);f.write(str(nid)+'\n');f.write(' '.join('nan' if not np.isfinite(v) else format(v,'.17g') for v in uv.ravel())+'\n')
    write(pd.DataFrame(audit),'input_identity.csv');write(pd.DataFrame(geometry),'coordinate_qualification.csv')
    original=(R/'versions/V51/ModalSelfCal.cpp').read_text(encoding='utf-8');header=(R/'versions/V51/ModalSelfCal.h').read_text(encoding='utf-8')
    expected='1b9cfdd45f673852fceb388fd20c436af21226db17f0178a949492d764d54217';assert sha(R/'versions/V51/ModalSelfCal.cpp')==expected
    # Only a generated namespace-isolated research translation unit changes.
    # No generated copy is committed; the source hash and strict anchors bind it.
    repl={'gzmetro_msc':'rx_msc','ModalSelfCalConfig':'RXConfig','ModalSelfCalFrameInfo':'RXFrameInfo','ModalSelfCalResumeInfo':'RXResumeInfo','ModalSelfCalResult':'RXResult','ModalSelfCalState':'RXState','ModalSelfCalAxis':'RXAxis'}
    for a,b in repl.items():original=original.replace(a,b);header=header.replace(a,b)
    original=original.replace('#include "ModalSelfCal.h"','#include "RX.h"')
    def patch(old,new):
        nonlocal original
        assert original.count(old)==1,(old,original.count(old));original=original.replace(old,new)
    patch('    std::vector<char> use, learn;','    std::vector<char> use, learn;\n    mutable std::vector<char> research_active;')
    patch('        if (nvalid) *nvalid = last_valid_cnt;','        research_active = active;\n        if (nvalid) *nvalid = last_valid_cnt;')
    patch('    info.n_frame_learn_valid = nvalid;\n    for (int kk', '    info.n_frame_learn_valid = nvalid;\n    std::vector<double> research_extra(s.p,0.0);\n    if(rx::current && rx::axis_x) rx::current->apply(s,z,valid,v,research_extra,ts_ms);\n    for (int kk')
    patch('        out[i] = values[i] - g * corr;','        corr += research_extra[i];\n        out[i] = values[i] - g * corr;')
    patch('try{r.x=p.x->Ingest(ts,x);r.y=p.y->Ingest(ts,y);}', 'try{rx::axis_x=true;r.x=p.x->Ingest(ts,x);rx::axis_x=false;r.y=p.y->Ingest(ts,y);}')
    # Read-only introspection at the exact existing solve/output boundary.
    patch('    void SetEnabled(bool enabled);','    Impl* research_impl() { return impl_; }\n    void SetEnabled(bool enabled);') if False else None
    # Impl is declared lower in this private implementation class.
    patch('    struct Impl;                    // 内部实现（对调用方不可见）','    struct Impl;\n    Impl* research_impl() { return impl_; }')
    patch('    bool initialized=false,valid=false,processed=false,processing_ready=false;','    bool initialized=false,valid=false,processed=false,processing_ready=false;') if False else None
    # Access facade x state only inside the generated research class.
    header=header.replace('    struct Impl;\n    std::unique_ptr<Impl> impl_;','public:\n    struct Impl;\n    std::unique_ptr<Impl> impl_;')
    (W/'RX.h').write_text(header,encoding='utf-8',newline='\n');(W/'RX.cpp').write_text(original,encoding='utf-8',newline='\n')
    print('Prepared six full original input sequences and isolated generated research source')
if __name__=='__main__':main()
