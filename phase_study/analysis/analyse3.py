import sys, csv, json, glob, statistics as st
import numpy as np
S=sys.argv[1]
feat={}
for l in open(S+'/groth16_live/repo/analysis/features3.jsonl'):
    d=json.loads(l)
    if 'f' in d: feat[d['id']]=d['f']
AG={'front':['g16.synthesis','g16.finalize','wm.to_matrices'],'eval':['wm.eval_ab','wm.eval_c'],'fft':['wm.fft_ab','wm.fft_c_and_h'],'msm':['g16.msm_h','g16.msm_l','g16.msm_a','g16.msm_b_g1','g16.msm_b_g2']}
BG={'front':['bm.synthesis'],'eval':[],'fft':['bm.fft'],'msm':['bm.msm_all']}
def load(f,G):
    D={}
    for r in csv.DictReader(open(f)):
        D.setdefault(r['circuit'],{}).setdefault(r['phase'],{})[int(r['replicate'])]=float(r['seconds'])
    out={}
    for c,d in D.items():
        tot=d['inner.generate_proof']; reps=[r for r in tot if r>=1]
        o={'wall':st.median(tot[r] for r in reps),'sd':100*st.pstdev([tot[r] for r in reps])/st.median(tot[r] for r in reps),'reps':len(reps)}
        for g,v in G.items(): o[g]=st.median(sum(d[x][r] for x in v) for r in reps) if v else 0.0
        leaves=[k for k in d if k not in('inner.generate_proof','g16.create_proof_total','g16.witness_map_total','bm.create_proof_total','cli.backend_generate_proof')]
        o['cov']=st.median(sum(d[x][r] for x in leaves)/tot[r] for r in reps)
        out[c]=o
    return out
res={}
for m in ('laptop','desktop'):
    a=load(glob.glob(S+'/ph/%s/phases_*/phases.csv'%m)[0],AG); b=load(glob.glob(S+'/phb/%s/phases_*/phases.csv'%m)[0],BG)
    res[m]={'ark':a,'bellman':b}
    ids=sorted(a,key=lambda c:feat[c]['n_constraints'])
    print('\n===',m)
    print('circuit            n      | ark_s  bel_s  bel/ark | ark front%  bel front% | ark front_s bel front_s ratio | bel fft% msm% cov% sd%')
    for c in ids:
        x,y=a[c],b[c]
        print(f"{c:16s} {feat[c]['n_constraints']:7d} | {x['wall']:6.3f} {y['wall']:6.3f} {y['wall']/x['wall']:6.2f} | {100*x['front']/x['wall']:8.1f} {100*y['front']/y['wall']:10.1f}   | {x['front']:8.3f} {y['front']:9.3f} {y['front']/x['front']:6.2f} | {100*y['fft']/y['wall']:6.1f} {100*y['msm']/y['wall']:5.1f} {100*y['cov']:5.1f} {y['sd']:4.1f}")
    big=[c for c in ids if feat[c]['n_constraints']>=10000]
    n=np.array([feat[c]['n_constraints'] for c in big],float); z=np.array([feat[c]['nnz_A']+feat[c]['nnz_B']+feat[c]['nnz_C'] for c in big],float)
    for bk,T in (('ark',a),('bellman',b)):
        y=np.array([T[c]['front'] for c in big])
        for lab,X in (('nnz',np.c_[z]),('n+nnz',np.c_[n,z])):
            co,*_=np.linalg.lstsq(X,y,rcond=None); e=np.abs(X@co-y)/y
            print(f"  {bk} front ~ {lab}: coef us {np.round(co*1e6,3)} mean err {100*e.mean():.0f}%")
    fa=[100*a[c]['front']/a[c]['wall'] for c in ids]; fb=[100*b[c]['front']/b[c]['wall'] for c in ids]
    r=[b[c]['wall']/a[c]['wall'] for c in ids]; fr=[b[c]['front']/a[c]['front'] for c in big]
    print(f"  front share ark min/med/max {min(fa):.0f}/{st.median(fa):.0f}/{max(fa):.0f}; bellman {min(fb):.0f}/{st.median(fb):.0f}/{max(fb):.0f}")
    print(f"  bellman/ark total: median {st.median(r):.2f} range {min(r):.2f}-{max(r):.2f}; front-end seconds ratio (>=10k) median {st.median(fr):.2f} range {min(fr):.2f}-{max(fr):.2f}; bellman coverage {100*min(b[c]['cov'] for c in ids):.1f}-{100*max(b[c]['cov'] for c in ids):.1f}")
    for p in (('synth_full_100k','synth_bool_100k'),('synth_full_300k','synth_bool_300k')):
        print('  pair',p,'bool/full wall: ark %.2f bellman %.2f'%(a[p[1]]['wall']/a[p[0]]['wall'], b[p[1]]['wall']/b[p[0]]['wall']))
json.dump(res,open(S+'/phb/ark_vs_bellman.json','w'),indent=1)
