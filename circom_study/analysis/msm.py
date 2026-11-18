import re,glob,os,statistics as st,csv,sys
ansi=re.compile(r'\x1b\[[0-9;]*m'); base=sys.argv[1]; rows=[]
for mach in ['laptop','desktop']:
  d=glob.glob(f'{base}/{mach}_*')[0]; by={}
  for f in glob.glob(d+'/logs/*_pass*.log'):
    c,p=re.match(r'(.*)_pass(\d+)\.log',os.path.basename(f)).groups()
    if p=='0': continue
    s={};e={}
    for ln in open(f,errors='replace'):
      ln=ansi.sub('',ln)
      m=re.match(r'([\d.]+)\t.*Multiexp (start|end): multiexp (\w+): 0/',ln)
      if m: (s if m.group(2)=='start' else e)[m.group(3)]=float(m.group(1))/1000
    by.setdefault(c,[]).append({k:e[k]-s[k] for k in s})
  for c,L in sorted(by.items()):
    r={'machine':mach,'circuit':c}
    for k in ['A','B1','B2','C','H']: r[k]=round(st.median(x[k] for x in L),3)
    r['wire_msm']=round(r['A']+r['B1']+r['B2']+r['C'],3); rows.append(r)
keys=['machine','circuit','A','B1','B2','C','H','wire_msm']
w=csv.DictWriter(open('circom_msm_split.csv','w',newline=''),fieldnames=keys); w.writeheader()
for r in rows: w.writerow(r); print('\t'.join(str(r[k]) for k in keys))
