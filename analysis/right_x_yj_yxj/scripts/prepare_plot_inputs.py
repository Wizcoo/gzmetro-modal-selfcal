from relations import *
for source,target in [('refs.pkl','plot_refs.csv'),('candidate_traces.pkl','plot_candidates.csv')]:
    pd.read_pickle(W/source).to_csv(W/target,index=False)
