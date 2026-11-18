import re,sys,glob,os,json,statistics as st,csv
ansi=re.compile(r'\x1b\[[0-9;]*m')
def parse(f):
    ev=[]
    for ln in open(f,encoding='utf-8',errors='replace'):
        ln=ansi.sub('',ln.rstrip('\n'))
        if '\t' not in ln: continue
        t,m=ln.split('\t',1)
        try: t=float(t)/1000
        except: continue
        ev.append((t,m))
    def first(p):
        for t,m in ev:
            if p in m: return t
    def last(p):
        r=None
        for t,m in ev:
            if p in m: r=t
        return r
    end=last('EXIT'); rw=first('Reading Wtns'); abc=first('Building ABC')
    fft0=min(x for x in [first('IFFT_A'),first('FFT_A')] if x is not None)
    mx0=first('Multiexp start'); mx1=last('Multiexp end')
    fft1=max(t for t,m in ev if 'FFT' in m and t<=mx0) if mx0 else None
    # what is between fft1 and mx0, and after mx1
    return dict(startup=rw, read=abc-rw, qap=fft0-abc, fft=fft1-fft0, gap=mx0-fft1, msm=mx1-mx0, tail=end-mx1, total=end,
                order=[m.split(':')[1].strip() if ':' in m else m for t,m in ev if 'Multiexp start' in m])
base=sys.argv[1]
rows=[]
for mach in ['laptop','desktop']:
    d=glob.glob(f'{base}/{mach}_*')[0]
    info={os.path.basename(f).replace('_r1cs_info.json',''):json.load(open(f)) for f in glob.glob(d+'/logs/*_r1cs_info.json')}
    res=list(csv.DictReader(open(d+'/results.csv')))
    by={}
    for f in sorted(glob.glob(d+'/logs/*_pass*.log')):
        c,p=re.match(r'(.*)_pass(\d+)\.log',os.path.basename(f)).groups()
        if p=='0': continue
        try: by.setdefault(c,[]).append(parse(f))
        except Exception as e: print('ERR',f,e)
    for c,L in by.items():
        r={'machine':mach,'circuit':c}
        for k in ['startup','read','qap','fft','gap','msm','tail','total']:
            r[k]=round(st.median(x[k] for x in L),3)
        r['prove_s']=round(st.median(float(x['prove_s']) for x in res if x['circuit']==c and x['pass']!='0'),3)
        rows.append(r)
    if mach=='laptop': print('multiexp order:',L[0]['order'])
    print(mach,json.dumps(info))
keys=['machine','circuit','prove_s','total','startup','read','qap','fft','gap','msm','tail']
print('\t'.join(keys))
for r in rows: print('\t'.join(str(r[k]) for k in keys))
with open('circom_phases.csv','w',newline='') as fh:
    w=csv.DictWriter(fh,fieldnames=keys); w.writeheader(); [w.writerow({k:r[k] for k in keys}) for r in rows]
