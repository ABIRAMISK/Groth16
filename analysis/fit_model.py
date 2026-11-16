"""Cost-model validation. usage: python3 -I fit_model.py <features.jsonl> <configs.tsv> <tag>=<results.csv>[:P] ...   (P = CPUs visible to the container)
Models (all fitted per machine on relative error, non-negative least squares, validated by leaving out one circuit family at a time):
  M0  y = a + b*n_constraints
  M1  y = a + b*C(structure)   operation count if every multiexp scalar were a random full-width field element (what the R1CS shape alone predicts)
  M2  y = a + b*C(witness)     same operation count with the real witness values (zero scalars skipped, scalar one handled once, windows of small values empty)
  M3  y = a + b1*C_seq + b2*(C_fft/P + makespan of the multiexp window jobs on P workers)   (real witness)
C = field-multiplication equivalents: G1 mixed add 11, G1 add 16, G1 double 7; G2 (Fq2) 29, 43, 16; FFT 3.5*m*log2 m; synthesis nnz_other + 0.1*nnz_unit + n."""
import json, csv, sys, math, statistics as st, collections, heapq
import numpy as np
from scipy.optimize import nnls
G1 = (11, 16, 7); G2 = (29, 43, 16)
def group(fam):
    return ('merkle' if fam.startswith('Merkle') else 'poseidon' if fam.startswith('Poseidon') else 'rsa_acc' if fam == 'RSA accumulator' else
            'rsa_real' if fam.startswith('RSA-') else 'ecdsa' if fam.startswith('ECDSA') else 'sha256' if fam.startswith('SHA') else 'synth')
def units(s, w): return w[0] * s['mixed'] + w[1] * s['full'] + w[2] * s['dbl']
def msm_units(f, real=True):
    m = f['msm']; src = (lambda k: m[k]) if real else (lambda k: m[k] if k == 'H' else m[k]['full_equiv'])
    return sum(units(src(k), G1) for k in 'ABLH') + units(src('B'), G2)
def makespan(f, P, real=True):
    m = f['msm']; src = (lambda k: m[k]) if real else (lambda k: m[k] if k == 'H' else m[k]['full_equiv'])
    jobs = []
    for k, w in (('H', G1), ('L', G1), ('A', G1), ('B', G1), ('B', G2)):
        s = src(k); jobs += [w[0] * a + w[1] * b for a, b in zip(s['win_mixed'], s['win_full'])]
    h = [0.0] * P
    for c in jobs: t = heapq.heappop(h); heapq.heappush(h, t + c)
    return max(h)
def feats(f, P):
    n = f['n_constraints']; m = f['domain']; nnz = f['nnz_A'] + f['nnz_B'] + f['nnz_C']
    nno = sum(f['nnz_other'].values()); nnu = sum(f['nnz_unit'].values())
    fft = 3.5 * m * math.log2(m); syn = nno + 0.1 * nnu + n
    K = f['wires_in_A'] + 2 * f['wires_in_B'] + f['n_aux'] + (m - 1)
    return dict(n=n, fft=fft, syn=syn, K=K, nnz=nnz, msm_real=msm_units(f, True), msm_full=msm_units(f, False),
                span_real=makespan(f, P, True), span_full=makespan(f, P, False))
def fit(X, y):
    A = np.c_[np.ones(len(y)), X] / np.array(y)[:, None]; coef, _ = nnls(A, np.ones(len(y))); return coef
def pred(coef, X): return np.c_[np.ones(len(X)), X] @ coef
MODELS = {  # name -> row builder (from feats dict)
    'M0 constraints': lambda d, P: [d['n']],
    'M1 structure':   lambda d, P: [d['msm_full'] + d['fft'] + d['syn']],
    'M2 witness':     lambda d, P: [d['msm_real'] + d['fft'] + d['syn']],
    'M3 parallel':    lambda d, P: [d['syn'], d['fft'] / P + d['span_real']]}
def med_times(path, phase):
    rows = [r for r in csv.DictReader(open(path, newline='', encoding='utf-8')) if r['status'] == 'OK' and int(r['replicate']) >= 1 and r[phase + '_inner_s'] != '']
    g = collections.defaultdict(list)
    for r in rows: g[(r['family'], r['parameter'])].append(float(r[phase + '_inner_s']))
    return {k: (st.median(v), 100 * st.pstdev(v) / st.mean(v), len(v)) for k, v in g.items()}
def main(featp, cfgp, specs, phase='proof'):
    cfg = {}
    for ln in open(cfgp):
        a = ln.rstrip('\n').split('\t'); cfg[a[0]] = a
    F = {}
    for ln in open(featp):
        d = json.loads(ln)
        if 'error' not in d and 'msm' in d['f'] and 'full_equiv' in d['f']['msm']['A']: F[d['id']] = d['f']
    out = {}
    for spec in specs:
        tag, rest = spec.split('=', 1); path, _, P = rest.partition(':'); P = int(P or 8)
        T = med_times(path, phase); ids = [i for i in F if (cfg[i][1], cfg[i][2]) in T]
        y = np.array([T[(cfg[i][1], cfg[i][2])][0] for i in ids]); grp = np.array([group(cfg[i][1]) for i in ids]); D = [feats(F[i], P) for i in ids]
        print(f"\n=== {tag}  phase={phase}  P={P}  circuits={len(ids)}  groups={dict(collections.Counter(grp))}")
        res = {}
        for name, build in MODELS.items():
            X = np.array([build(d, P) for d in D]); coef = fit(X, y); ins = pred(coef, X)
            lo = np.zeros(len(y))
            for g in set(grp):
                tr = grp != g; c = fit(X[tr], y[tr]); lo[~tr] = pred(c, X[~tr])
            ape_in = 100 * np.abs(ins / y - 1); ape_lo = 100 * np.abs(lo / y - 1)
            res[name] = dict(coef=[float(v) for v in coef], pred_in=ins, pred_lo=lo)
            print(f"  {name:15s} in-sample MAPE {ape_in.mean():5.1f}%  max {ape_in.max():5.1f}% | leave-family-out MAPE {ape_lo.mean():5.1f}%  max {ape_lo.max():6.1f}%  coef {np.array2string(coef, precision=3)}")
            for g in sorted(set(grp)): print(f"      {g:9s} LOFO MAPE {ape_lo[grp == g].mean():6.1f}%", end='')
            print()
        print(f"  {'circuit':20s} {'n':>7s} {'meas':>7s} " + ' '.join(f'{k[:2]}lo' .rjust(6) for k in MODELS))
        for j, i in enumerate(ids):
            print(f"  {i:20s} {D[j]['n']:7d} {y[j]:7.2f} " + ' '.join(f"{res[k]['pred_lo'][j] / y[j]:6.2f}" for k in MODELS))
        out[tag] = dict(ids=ids, y=y.tolist(), models={k: dict(coef=v['coef'], pred_lo=v['pred_lo'].tolist(), pred_in=v['pred_in'].tolist()) for k, v in res.items()})
    return out
if __name__ == '__main__':
    ph = 'proof'; a = sys.argv[1:]
    if a and a[-1].startswith('phase='): ph = a.pop().split('=')[1]
    json.dump(main(a[0], a[1], a[2:], ph), open('/tmp/fit_out_%s.json' % ph, 'w'))
