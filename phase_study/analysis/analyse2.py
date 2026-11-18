import sys, csv, json, glob, os, statistics as st
import numpy as np
S=sys.argv[1]
feat={}
for l in open(S+'/groth16_live/repo/analysis/features3.jsonl'):
    d=json.loads(l)
    if 'f' in d: feat[d['id']]=d['f']
cfg={}
for l in open(S+'/groth16_live/repo/analysis/configs.tsv'):
    p=l.rstrip('\n').split('\t')
    if len(p)>3: cfg[(p[1],p[2])]=p[0]
G={'front':['g16.synthesis','g16.finalize','wm.to_matrices'],'eval':['wm.eval_ab','wm.eval_c'],'fft':['wm.fft_ab','wm.fft_c_and_h'],
   'msm':['g16.msm_h','g16.msm_l','g16.msm_a','g16.msm_b_g1','g16.msm_b_g2'],'io':['cli.witness_read','zok.public_inputs','zok.pk_deserialize']}
LE=sum(G.values(),[])+['wm.alloc_assignment','g16.h_to_repr','g16.aux_to_repr','g16.misc_before_a']
def orig(path):
    o={}
    for r in csv.DictReader(open(path)):
        if r['status']!='OK' or int(r['replicate'])<1 or not r['proof_inner_s']: continue
        i=cfg.get((r['family'],r['parameter']))
        if i: o.setdefault(i,[]).append(float(r['proof_inner_s']))
    return {k:st.median(v) for k,v in o.items()}
out={}
for m,od in (('laptop','res_lap'),('desktop','res_desk')):
    f=glob.glob(S+'/ph/%s/phases_*/phases.csv'%m)[0]
    D={}
    for r in csv.DictReader(open(f)):
        D.setdefault(r['circuit'],{}).setdefault(r['phase'],{})[int(r['replicate'])]=float(r['seconds'])
    ops=glob.glob(S+'/groth16_live/repo/%s/**/results.csv'%od,recursive=True)
    O={}
    for p in ops: O.update(orig(p))
    rows=[]
    for c,d in D.items():
        reps=[r for r in d['inner.generate_proof'] if r>=1 and all(r in d.get(x,{}) for x in LE)]
        tot=d['inner.generate_proof']; w=st.median(tot[r] for r in reps)
        g={k:st.median(sum(d[x][r] for x in v) for r in reps) for k,v in G.items()}
        cov=st.median(sum(d[x][r] for x in LE)/tot[r] for r in reps)
        sd=st.pstdev([tot[r] for r in reps])/w*100
        ft=feat[c]; nnz=ft['nnz_A']+ft['nnz_B']+ft['nnz_C']
        rows.append(dict(id=c,n=ft['n_constraints'],nnz=nnz,reps=len(reps),wall=w,sd=sd,g=g,cov=cov,orig=O.get(c),
                         synth=st.median(d['g16.synthesis'][r] for r in reps),fin=st.median(d['g16.finalize'][r] for r in reps),tom=st.median(d['wm.to_matrices'][r] for r in reps)))
    rows.sort(key=lambda r:r['n']); out[m]=rows
    print('\n===',m,'orig files:',len(ops))
    print('circuit            n      reps proof_s  sd%  orig_s  diff% | front  eval   fft   msm    io  cov% | front_s  us/nnz eval us/nnz')
    for r in rows:
        p=lambda x:100*x/r['wall']; o=r['orig']
        print(f"{r['id']:16s} {r['n']:7d} {r['reps']:3d} {r['wall']:7.3f} {r['sd']:4.1f} {o if o else float('nan'):7.3f} {100*(r['wall']/o-1) if o else float('nan'):+6.1f} | {p(r['g']['front']):5.1f} {p(r['g']['eval']):5.1f} {p(r['g']['fft']):5.1f} {p(r['g']['msm']):5.1f} {p(r['g']['io']):5.1f} {100*r['cov']:5.1f} | {r['g']['front']:6.3f} {1e6*r['g']['front']/r['nnz']:6.3f} {1e6*r['g']['eval']/r['nnz']:6.3f}")
    big=[r for r in rows if r['n']>=10000]
    n=np.array([r['n'] for r in big],float); z=np.array([r['nnz'] for r in big],float)
    for name,key in (('front','front'),('eval','eval')):
        y=np.array([r['g'][key] for r in big])
        for lab,X in (('nnz',np.c_[z]),('n',np.c_[n]),('n+nnz',np.c_[n,z])):
            c,*_=np.linalg.lstsq(X,y,rcond=None); e=np.abs(X@c-y)/y
            print(f"  fit {name} ~ {lab}: coef(us)={np.round(c*1e6,3)} mean rel err {100*e.mean():.0f}% (17 circuits >=10k)")
    fr=[100*r['g']['front']/r['wall'] for r in rows]; ev=[100*r['g']['eval']/r['wall'] for r in rows]
    print(f"  front share: min {min(fr):.1f} median {st.median(fr):.1f} max {max(fr):.1f};  eval share: {min(ev):.1f}-{max(ev):.1f};  coverage {100*min(r['cov'] for r in rows):.1f}-{100*max(r['cov'] for r in rows):.1f}")
    d=[100*(r['wall']/r['orig']-1) for r in rows if r['orig']]
    print(f"  vs original session: n={len(d)} median diff {st.median(d):+.1f}%  range {min(d):+.1f}..{max(d):+.1f}")
json.dump(out,open(S+'/ph/phase_summary.json','w'),indent=1)
