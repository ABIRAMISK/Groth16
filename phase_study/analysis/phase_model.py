# Per-phase model on the instrumented runs: front = a*n + b*nnz ; fft = c*F ; msm = d*W ; rest = constant + e*n.
# Leave-one-family-out; compared with M0, M1, M3 fitted on the totals of the same runs. Relative-error NNLS as in the paper.
import sys, csv, json, glob, math, statistics as st
import numpy as np
from scipy.optimize import nnls
S=sys.argv[1]
FEA={}
for l in open(S+'/groth16_live/repo/analysis/features3.jsonl'):
    d=json.loads(l)
    if 'f' in d: FEA[d['id']]=d['f']
FAM={"poseidon":"Poseidon","merkle":"Merkle","rsa_":"Ladder","sha256":"SHA-256","rsa1024real":"RSAv","rsa2048real":"RSAv","rsa3072real":"RSAv","rsa4096real":"RSAv","ecdsa":"ECDSA","synth":"Synthetic"}
def fam(i):
    for k,v in FAM.items():
        if i.startswith(k): return v
W1=(11,16,7); W2=(29,43,16); PCPU={'laptop':8,'desktop':16}
def work(f):
    tot=0.0
    for k in "ABLH":
        e=f["msm"][k]; tot+=W1[0]*e["mixed"]+W1[1]*e["full"]+W1[2]*e["dbl"]
        if k=="B": tot+=W2[0]*e["mixed"]+W2[1]*e["full"]+W2[2]*e["dbl"]
    return tot
def feats(i):
    f=FEA[i]; m=f["domain"]; n=f["n_constraints"]; nnz=f["nnz_A"]+f["nnz_B"]+f["nnz_C"]
    return n,nnz,3.5*m*math.log2(m),work(f)
AG={'front':['g16.synthesis','g16.finalize','wm.to_matrices'],'fft':['wm.fft_ab','wm.fft_c_and_h'],'msm':['g16.msm_h','g16.msm_l','g16.msm_a','g16.msm_b_g1','g16.msm_b_g2']}
BG={'front':['bm.synthesis'],'fft':['bm.fft'],'msm':['bm.msm_all']}
def load(f,G):
    D={}
    for r in csv.DictReader(open(f)):
        D.setdefault(r['circuit'],{}).setdefault(r['phase'],{})[int(r['replicate'])]=float(r['seconds'])
    out={}
    for c,d in D.items():
        tot=d['inner.generate_proof']; reps=[r for r in tot if r>=1]
        o={'wall':st.median(tot[r] for r in reps)}
        for g,v in G.items(): o[g]=st.median(sum(d[x][r] for x in v) for r in reps)
        o['rest']=st.median(tot[r]-sum(d[x][r] for v in G.values() for x in v) for r in reps)
        out[c]=o
    return out
def fitrel(X,y):
    c,_=nnls(X/y[:,None],np.ones(len(y))); return c
def run(m,bk,data):
    ids=sorted(data); g=np.array([fam(i) for i in ids]); F=np.array([feats(i) for i in ids],float); n,nnz,Ff,W=F.T; P=PCPU[m]
    y=np.array([data[i]['wall'] for i in ids]); one=np.ones(len(ids))
    designs={'M0':np.c_[one,n],'M1':np.c_[one,n,nnz],'M3':np.c_[one,n,nnz,(W+Ff)/P]}
    comp={'front':np.c_[n,nnz],'fft':np.c_[Ff],'msm':np.c_[one*0+1e-9,W],'rest':np.c_[one,n]}
    comp['msm']=np.c_[W]
    res={}
    for name,X in designs.items():
        e=np.zeros(len(ids))
        for u in set(g):
            te=g==u; c=fitrel(X[~te],y[~te]); e[te]=np.abs(X[te]@c-y[te])/y[te]
        res[name]=e
    e=np.zeros(len(ids)); pe={k:np.zeros(len(ids)) for k in comp}
    for u in set(g):
        te=g==u; pred=np.zeros(te.sum())
        for k,X in comp.items():
            yk=np.array([data[i][k] for i in ids]); c=fitrel(X[~te],np.maximum(yk[~te],1e-6)); pk=X[te]@c; pred+=pk
            pe[k][te]=np.abs(pk-yk[te])/np.maximum(yk[te],1e-6)
        e[te]=np.abs(pred-y[te])/y[te]
    res['phase']=e
    big=np.array([FEA[i]['n_constraints']>=10000 for i in ids])
    print(f"{m:8s} {bk:8s} LOFO mean(max)%: "+"  ".join(f"{k} {100*v.mean():5.1f} ({100*v.max():4.0f})" for k,v in res.items())+
          "  | per-phase LOFO mean%, circuits>=10k: "+" ".join(f"{k} {100*v[big].mean():.0f}" for k,v in pe.items()))
    full={k:fitrel(X,np.maximum(np.array([data[i][k] for i in ids]),1e-6)) for k,X in comp.items()}
    print("           full-data coefficients: front %.2f us/constraint + %.3f us/nnz; fft %.1f ns/unit; msm %.1f ns/unit; rest %.3f s + %.2f us/constraint"%(1e6*full['front'][0],1e6*full['front'][1],1e9*full['fft'][0],1e9*full['msm'][0],full['rest'][0],1e6*full['rest'][1]))
    worst=np.argsort(-res['phase'])[:3]; print("           worst phase-model predictions:",[(ids[k],round(100*res['phase'][k])) for k in worst])
for m in ('laptop','desktop'):
    run(m,'ark',load(glob.glob(S+'/ph/%s/phases_*/phases.csv'%m)[0],AG))
    run(m,'bellman',load(glob.glob(S+'/phb/%s/phases_*/phases.csv'%m)[0],BG))
