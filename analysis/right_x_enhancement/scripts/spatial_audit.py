from results import *

def main():
    rows=[]
    for dev in DEVS:
        names,_,_,_=load(W/'final'/f'normal_{dev}.bin');birth=pd.read_csv(W/'final'/f'birth_{dev}.csv');tok=(W/f'{dev}.coords').read_text().split();at=1;coords={}
        for _ in range(int(tok[0])):nid=int(tok[at]);at+=1;coords[nid]=np.asarray(tok[at:at+2*len(names)],float).reshape(-1,2);at+=2*len(names)
        for nid,uv in coords.items():
            b=birth[birth.method.eq('identity')&birth.night_id.eq(nid)].sort_values('point_index');A=b[['A1','A2','A3']].to_numpy();learn=b.learn.eq(1).to_numpy();use=b.use.eq(1).to_numpy();refs=np.array([i for i,n in enumerate(names) if n.startswith('YJ') and use[i] and b.historical_explained_energy.iloc[i]>=.8]);G=A[learn].T@A[learn]
            for model,nom in [('B0',1),('B1',2),('B2',3)]:
                kept=[];fractions=[];axis=0;reason='';r=birth[birth.method.eq(model)&birth.night_id.eq(nid)].iloc[0]
                if len(refs)<3:reason='fewer_than_3_qualified_YJ'
                elif not np.isfinite(uv).all():reason='unstable_or_missing_native_coordinate'
                else:
                    axis=int(np.ptp(uv[refs,1])>np.ptp(uv[refs,0]));raw=np.column_stack([np.ones(len(names)),uv[:,axis],uv[:,1-axis]])[:,:nom]
                    for j in range(nom):
                        projection=np.linalg.solve(G,A[learn].T@raw[learn,j]);q=np.zeros(len(names));q[use]=raw[use,j]-A[use]@projection
                        for prev in kept:q-=float(q[learn]@prev[learn])*prev
                        ratio=float(q[learn]@q[learn])/max(1e-20,float(raw[learn,j]@raw[learn,j]));fractions.append(ratio)
                        if ratio>=.05:kept.append(q/np.sqrt(q[learn]@q[learn]))
                    if not kept:reason='position_basis_already_in_modal_subspace'
                    elif len(refs)<len(kept)+2:reason='insufficient_independent_reference_redundancy'
                    elif r.B_qualified:reason='numeric_proxy_qualified_semantics_not_verified'
                    elif np.isfinite(r.B_LOPO_gain):reason='historical_leave_one_reference_gain_below_20pct'
                    else:reason='rank_or_condition_failed'
                rows.append({'device_id':dev,'night_id':nid,'model':model,'eligible_YJ':len(refs),'nominal_basis_dimension':nom,'independent_residual_dimension':len(kept),'residual_column_energy_fractions':json.dumps(fractions),'axis_for_1D':'centerY_native' if axis else 'centerX_native','historical_LOPO_energy_gain':r.B_LOPO_gain,'condition_bound':r.B_condition,'numeric_qualified':r.B_qualified,'reason':reason,'coordinate_semantics':'stable native configuration proxy; not independently confirmed image/world geometry'})
    write(pd.DataFrame(rows),'spatial_identifiability.csv');print(pd.DataFrame(rows)[['device_id','model','independent_residual_dimension','reason']].drop_duplicates().to_string(index=False))
if __name__=='__main__':main()
