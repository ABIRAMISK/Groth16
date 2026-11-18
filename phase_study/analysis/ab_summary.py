import sys, glob, os, statistics as st
d=sys.argv[1]
F=['g16.synthesis','g16.finalize','wm.to_matrices']
print('circuit          A_wall  B_wall  B/A   | A_synth B_synth  A_final B_final  A_tomat B_tomat | A_front B_front  front B/A')
for f in sorted(glob.glob(d+'/*.ab')):
    X={}
    for l in open(f):
        p=l.split()
        cid,rep,v,lab,val=p[0],int(p[1]),p[2],p[3],p[4]
        if rep==0: continue
        X.setdefault(v,{}).setdefault(lab,[]).append(float(val))
    m=lambda v,k: st.median(X[v][k])
    fa=sum(m('A',k) for k in F); fb=sum(m('B',k) for k in F)
    print(f"{os.path.basename(f)[:-3]:16s} {m('A','wall'):6.3f} {m('B','wall'):6.3f} {m('B','wall')/m('A','wall'):5.2f} | {m('A','g16.synthesis'):7.3f} {m('B','g16.synthesis'):7.3f}  {m('A','g16.finalize'):7.3f} {m('B','g16.finalize'):7.3f}  {m('A','wm.to_matrices'):7.3f} {m('B','wm.to_matrices'):7.3f} | {fa:7.3f} {fb:7.3f}  {fb/fa:5.2f}")
