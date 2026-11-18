# Per-phase model (fitted on the instrumented runs of 16-17 Nov 2026, all 21 circuits) applied to the two EdDSA circuits.
import sys, json, glob, math
import numpy as np
S=sys.argv[1]; sys.argv=[sys.argv[0],S]
src=open(S+'/phb/phase_model.py').read()
exec(compile(src[:src.index("def run(m,bk,data):")],'pm','exec'))
NEW={'eddsa_sha256':json.load(open(S+'/eddsa/feat_sha256.json')),'eddsa_poseidon':json.load(open(S+'/eddsa/feat_poseidon.json'))}
def fx(f):
    m=f["domain"]; n=f["n_constraints"]; nnz=f["nnz_A"]+f["nnz_B"]+f["nnz_C"]; return n,nnz,3.5*m*math.log2(m),work(f)
out={}
for m in ('laptop','desktop'):
    for bk,G,dirn in (('ark',AG,'ph'),('bellman',BG,'phb')):
        data=load(glob.glob(S+'/%s/%s/phases_*/phases.csv'%(dirn,m))[0],G); ids=sorted(data)
        F=np.array([feats(i) for i in ids],float); n,nnz,Ff,W=F.T; one=np.ones(len(ids))
        comp={'front':np.c_[n,nnz],'fft':np.c_[Ff],'msm':np.c_[W],'rest':np.c_[one,n]}
        co={k:fitrel(X,np.maximum(np.array([data[i][k] for i in ids]),1e-6)) for k,X in comp.items()}
        for k,f in NEW.items():
            a,b,c,d=fx(f); parts={'front':co['front']@[a,b],'fft':co['fft'][0]*c,'msm':co['msm'][0]*d,'rest':co['rest']@[1,a]}
            out['%s/%s/%s'%(m,bk,k)]={'total_s':round(float(sum(parts.values())),4),**{p:round(float(v),4) for p,v in parts.items()}}
print(json.dumps(out,indent=1))
