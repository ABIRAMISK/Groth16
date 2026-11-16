#!/usr/bin/env python3
"""Statistics of the v4 manuscript, computed from raw result files of the two machines and the structure features. Nothing typed by hand.
usage: python3 -I stats_v4.py <features2.jsonl> <configs.tsv> <out.json> <tag>=<machine folder>:<P> [<tag>=<folder>:<P> ...]
<machine folder> holds results_<ts>/ (results.csv, results_bind_control.csv, pass_log.txt ...), memory_<ts>/memory_profile.csv, machine_<label>.txt.
P = CPUs visible to the container. Replicate 0 of every circuit is the designated warm-up and is excluded from every statistic."""
import csv, sys, json, math, glob, os, re, statistics as st, collections
import numpy as np
from scipy import stats as sps
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fit_model as fm
PH = ["compile", "setup", "witness", "proof", "verify"]
FEAT, CFG, OUT = sys.argv[1:4]; SPECS = [a for a in sys.argv[4:] if not a.startswith("old=")]
OLD = [a[4:].split("=", 1) for a in sys.argv[4:] if a.startswith("old=")]   # old=<name>=<results.csv of an earlier laptop session>
cfg = collections.OrderedDict()
for ln in open(CFG):
    a = ln.rstrip("\n").split("\t"); cfg[a[0]] = dict(id=a[0], family=a[1], parameter=a[2], type=a[3], n=int(a[4]))
key2id = {(c["family"], c["parameter"]): i for i, c in cfg.items()}
FE = {}
for ln in open(FEAT):
    d = json.loads(ln)
    if "error" in d: raise SystemExit("feature error " + str(d))
    FE[d["id"]] = d["f"]
def fl(x):
    try: return float(x)
    except Exception: return None
def load(p): return list(csv.DictReader(open(p, newline="", encoding="utf-8")))
def summ(v):
    n = len(v); m = st.mean(v); s = st.stdev(v) if n > 1 else 0.0
    return dict(mean=m, sd=s, median=st.median(v), min=min(v), max=max(v), cv=s / m if m else 0.0, n=n, ci95=(sps.t.ppf(0.975, n - 1) * s / math.sqrt(n)) if n > 1 else 0.0, values=v)
# ------------------------------------------------------------------ structure table (machine independent)
S = {"circuits": [], "struct": {}}
for i, c in cfg.items():
    f = FE[i]; S["circuits"].append(dict(c, group=fm.group(c["family"]), compile_only=("msm" not in f)))
    s = dict(n=f["n_constraints"], wires=f["n_wires"], aux=f["n_aux"], domain=f["domain"], log2m=f["domain"].bit_length() - 1, nnz_A=f["nnz_A"], nnz_B=f["nnz_B"], nnz_C=f["nnz_C"],
             nnz=f["nnz_A"] + f["nnz_B"] + f["nnz_C"], nnz_per_constraint=(f["nnz_A"] + f["nnz_B"] + f["nnz_C"]) / f["n_constraints"],
             unit_share=sum(f["nnz_unit"].values()) / (f["nnz_A"] + f["nnz_B"] + f["nnz_C"]), aux_in_A=f["aux_in_A"], aux_in_B=f["aux_in_B"], n_pub=f["n_instance"] - 1)
    if "msm" in f:
        h = f["aux_bitlen_hist"]; na = f["n_aux"]
        s.update(pct_01=100 * (h["0"] + h["1"]) / na, pct_2_64=100 * (h["2-8"] + h["9-64"]) / na, pct_65_200=100 * h["65-200"] / na, pct_gt200=100 * h["201-254"] / na, mean_bits=f["aux_bitlen_mean"],
                 msm_ratio={k: f["msm"][k]["mixed"] / f["msm"][k]["full_equiv"]["mixed"] for k in "ABL"},
                 msm_c={k: f["msm"][k]["c"] for k in "ABLH"}, check=f.get("check"))
    S["struct"][i] = s
# ------------------------------------------------------------------ per machine
S["machines"] = {}
for spec in SPECS:
    tag, rest = spec.split("=", 1); folder, _, P = rest.rpartition(":"); P = int(P)
    rdir = [d for d in sorted(glob.glob(folder + "/results_*")) if not d.endswith("_quick")][-1]
    mdir = [d for d in sorted(glob.glob(folder + "/memory_*")) if not d.endswith("_quick")]
    rows = load(rdir + "/results.csv"); ok = [r for r in rows if r["status"] == "OK"]
    M = dict(P=P, n_rows=len(rows), n_ok=len(ok), statuses=dict(collections.Counter(r["status"] for r in rows)), dir=os.path.basename(rdir))
    D = collections.defaultdict(dict)
    for r in ok: D[key2id[(r["family"], r["parameter"])]][int(r["replicate"])] = r
    per = {}
    for i in cfg:
        if i not in D: continue
        per[i] = {}
        for ph in PH:
            v = [fl(D[i][k][ph + "_inner_s"]) for k in range(1, 6) if k in D[i] and fl(D[i][k].get(ph + "_inner_s")) is not None]
            if not v: continue
            per[i][ph] = dict(summ(v), warmup=fl(D[i][0][ph + "_inner_s"]) if 0 in D[i] else None, ms_per_constraint=1000 * st.median(v) / cfg[i]["n"])
        per[i]["total"] = sum(per[i][ph]["median"] for ph in PH if ph in per[i])
        phs_ = [ph for ph in PH if ph in per[i]]
        reps_ = [k for k in range(1, 6) if k in D[i] and all(fl(D[i][k].get(ph + "_inner_s")) is not None for ph in phs_)]
        tr_ = [sum(fl(D[i][k][ph + "_inner_s"]) for ph in phs_) for k in reps_]
        per[i]["total_values"] = tr_; per[i]["total_cv"] = (st.stdev(tr_) / st.mean(tr_)) if len(tr_) > 1 else 0.0
        per[i]["verify_passed"] = all(D[i][k]["verify_passed"] in ("True", "") for k in D[i])
    M["per"] = per
    cvs = {i: per[i]["total_cv"] for i in per if len(per[i].get("total_values", [])) > 1}
    M["cv_total"] = dict(median=st.median(cvs.values()), max=max(cvs.values()), argmax=max(cvs, key=cvs.get), n=len(cvs))
    if tag == "lap" and OLD:
        M["old_sessions"] = {}
        for oname, opath in OLD:
            Do = collections.defaultdict(dict)
            for r in load(opath):
                if r["status"] == "OK": Do[key2id[(r["family"], r["parameter"])]][int(r["replicate"])] = r
            rat = {}
            for i in Do:
                if i not in per: continue
                rat[i] = {}
                for ph in PH:
                    vo = [fl(Do[i][k].get(ph + "_inner_s")) for k in range(1, 6) if k in Do[i]]; vo = [x for x in vo if x is not None]
                    if vo and ph in per[i]: rat[i][ph] = st.median(vo) / per[i][ph]["median"]
                both = [ph for ph in PH if ph in rat[i]]
                if both: rat[i]["total"] = sum(st.median([fl(Do[i][k][ph + "_inner_s"]) for k in range(1, 6) if k in Do[i]]) for ph in both) / sum(per[i][ph]["median"] for ph in both)
            summ_ = {}
            for ph in PH + ["total"]:
                xs = {i: rat[i][ph] for i in rat if ph in rat[i] and (ph == "total" or per[i][ph]["median"] > 0.5)}
                if not xs: continue
                over = [i for i, x in xs.items() if x > 1.10]
                summ_[ph] = dict(n=len(xs), median=st.median(xs.values()), min=min(xs.values()), max=max(xs.values()), argmax=max(xs, key=xs.get), n_over_1p1=len(over),
                                 over_1p1=over, over_1p1_min_median=(min(per[i][ph]["median"] if ph != "total" else per[i]["total"] for i in over) if over else None))
            M["old_sessions"][oname] = dict(n_circuits=len(rat), n_rows=sum(len(v) for v in Do.values()), summary=summ_, ratio=rat)
    # drift by replicate: visit total relative to the circuit median over replicates 1-5
    def tot(r): return sum(fl(r[ph + "_inner_s"]) or 0 for ph in PH)
    dr = {}
    for rep in range(0, 6):
        xs = []
        for i in D:
            med = st.median([tot(D[i][k]) for k in range(1, 6) if k in D[i]])
            if rep in D[i] and med > 1.0: xs.append(tot(D[i][rep]) / med)
        dr[rep] = dict(median=st.median(xs), min=min(xs), max=max(xs), n=len(xs))
    M["drift"] = dr
    # visits whose total time is more than 10% above the median of the circuit (circuits with median > 1 s, replicates 1-5)
    fl_v, n_v = [], 0
    for i in D:
        ts = {k: tot(D[i][k]) for k in range(1, 6) if k in D[i]}; med = st.median(ts.values())
        if med > 1.0:
            for k, v in ts.items():
                n_v += 1
                if v / med > 1.10: fl_v.append((i, k, round(v / med, 3)))
    M["flagged"] = dict(n_visits=n_v, n_flagged=len(fl_v), visits=fl_v, by_rep={str(k): sum(1 for x in fl_v if x[1] == k) for k in range(1, 6)})
    gaps = [fl(r[ph + "_s"]) - fl(r[ph + "_inner_s"]) for r in ok for ph in PH if fl(r.get(ph + "_s")) is not None and fl(r.get(ph + "_inner_s")) is not None]
    M["host_gap"] = dict(median=st.median(gaps), max=max(gaps))
    gb = collections.defaultdict(list)
    for r in ok:
        for ph in PH:
            a_, b_ = fl(r.get(ph + "_s")), fl(r.get(ph + "_inner_s"))
            if a_ is not None and b_ is not None: gb[ph].append(a_ - b_)
    gsum = lambda v: dict(n=len(v), median=st.median(v), q1=float(np.percentile(v, 25)), q3=float(np.percentile(v, 75)), min=min(v), max=max(v))
    M["gap"] = {ph: gsum(v) for ph, v in gb.items()}; M["gap"]["all"] = gsum([x for v in gb.values() for x in v])
    M["verify_host"] = dict(median=st.median([fl(r["verify_s"]) for r in ok if fl(r.get("verify_s")) is not None]))
    # bind-mount control
    cp = rdir + "/results_bind_control.csv"
    if os.path.exists(cp):
        crow = [r for r in load(cp) if r["status"] == "OK" and int(r["replicate"]) >= 1]; C = collections.defaultdict(lambda: collections.defaultdict(list))
        for r in crow:
            for ph in PH:
                if fl(r.get(ph + "_inner_s")) is not None: C[key2id[(r["family"], r["parameter"])]][ph].append(fl(r[ph + "_inner_s"]))
        M["control"] = {i: {ph: dict(bind_mean=st.mean(v), local_mean=per[i][ph]["mean"], ratio=st.mean(v) / per[i][ph]["mean"], n=len(v)) for ph, v in d.items() if ph in per[i]} for i, d in C.items()}
        M["control_med"] = {i: {ph: dict(bind_median=st.median(v), local_median=per[i][ph]["median"], ratio=st.median(v) / per[i][ph]["median"],
                                         p=float(sps.ttest_ind(v, per[i][ph]["values"], equal_var=False).pvalue), n_bind=len(v), n_local=per[i][ph]["n"]) for ph, v in d.items() if ph in per[i]} for i, d in C.items()}
    # memory / CPU profile (one run per circuit and phase)
    if mdir:
        mem = collections.defaultdict(dict)
        for r in load(mdir[-1] + "/memory_profile.csv"):
            if r["phase"] in PH: mem[r["id"]][r["phase"]] = dict(wall=fl(r["wall_s"]), rss_mib=fl(r["peak_rss_mib"]), cpu_s=fl(r["cpu_s"]), cores=fl(r["cpu_cores"]), polls=fl(r["polls"]))
        M["mem"] = mem
        ov = []
        for i in mem:
            for ph_ in ("compile", "setup", "witness", "proof"):
                if i in per and ph_ in per[i] and ph_ in mem[i] and per[i][ph_]["median"] > 1.0 and mem[i][ph_]["wall"]: ov.append(mem[i][ph_]["wall"] / per[i][ph_]["median"])
        M["mem_overhead"] = dict(median=st.median(ov), min=min(ov), max=max(ov), n=len(ov))
    # power / pass log
    pl = rdir + "/pass_log.txt"
    if os.path.exists(pl):
        txt = open(pl).read(); M["pass_free_gb"] = [float(x) for x in re.findall(r"host_free_gb=([\d.]+)", txt)]
        import datetime as _dt
        pm = {}
        for m_ in re.finditer(r"pass (\d+) \(main\) (start|end)\s+(\S+)", txt):
            pm.setdefault(int(m_.group(1)), {})[m_.group(2)] = _dt.datetime.strptime(m_.group(3), "%Y-%m-%dT%H:%M:%SZ")
        M["clock_mhz"] = sorted(set(int(x) for x in re.findall(r"cpu_clock_mhz=(\d+)", txt)))
        M["ac_values"] = sorted(set(re.findall(r"battery_status\(2=AC\)=(\S*)", txt)))
        M["pass_minutes"] = {str(k): (v["end"] - v["start"]).total_seconds() / 60 for k, v in sorted(pm.items()) if "end" in v and "start" in v}
    # --------------------------------------------------------------- cost models
    ids = [i for i in per if "proof" in per[i] and "msm" in FE[i]]
    grp = np.array([fm.group(cfg[i]["family"]) for i in ids]); Fd = [fm.feats(FE[i], P) for i in ids]
    col = lambda k: np.array([d[k] for d in Fd], float)
    nwires = np.array([FE[i]["n_wires"] for i in ids], float)
    def models(y, specs, splits):
        out = {}
        for name, X in specs.items():
            coef = fm.fit(X, y); ins = fm.pred(coef, X); lo = np.zeros(len(y)); sp = {}
            for g in sorted(set(grp)):
                tr = grp != g; c = fm.fit(X[tr], y[tr]); lo[~tr] = fm.pred(c, X[~tr])
            ape_in = 100 * np.abs(ins / y - 1); ape_lo = 100 * np.abs(lo / y - 1)
            for sname, held in splits.items():
                te = np.isin(grp, held); c = fm.fit(X[~te], y[~te]); p = fm.pred(c, X[te]); sp[sname] = dict(mape=float(np.mean(100 * np.abs(p / y[te] - 1))), max=float(np.max(100 * np.abs(p / y[te] - 1))),
                                                                                             ratio={ids[j]: float(p[k] / y[j]) for k, j in enumerate(np.where(te)[0])})
            out[name] = dict(coef=[float(c) for c in coef], mape_in=float(ape_in.mean()), max_in=float(ape_in.max()), mape_lofo=float(ape_lo.mean()), max_lofo=float(ape_lo.max()),
                             lofo_by_group={g: float(ape_lo[grp == g].mean()) for g in sorted(set(grp))}, lofo_ratio={ids[j]: float(lo[j] / y[j]) for j in range(len(ids))},
                             in_ratio={ids[j]: float(ins[j] / y[j]) for j in range(len(ids))}, splits=sp)
        return out
    splits = {"verifiers": ["rsa_real", "ecdsa"], "synthetic": ["synth"]}
    yw = np.array([per[i]["proof"]["median"] for i in ids]); n = col("n"); nnz = col("nnz")
    M["models"] = dict(ids=ids, groups=[str(g) for g in grp])
    M["models"]["proof_wall"] = models(yw, {"n": np.c_[n], "n+nnz": np.c_[n, nnz], "n+nnz+msm_struct": np.c_[n, nnz, (col("msm_full") + col("fft")) / P],
                                              "n+nnz+msm_witness": np.c_[n, nnz, (col("msm_real") + col("fft")) / P]}, splits)
    sens = {}
    def centre(i, ph_, kind):
        v = {k: fl(D[i][k][ph_ + "_inner_s"]) for k in range(1, 6)}
        if kind == "min": return min(v.values())
        if kind == "mean": return st.mean(v.values())
        if kind == "mean_reps2to5": return st.mean(v[k] for k in range(2, 6))
        raise ValueError(kind)
    for kind in ("min", "mean", "mean_reps2to5"):
        yk = np.array([centre(i, "proof", kind) for i in ids]); ysk = np.array([centre(i, "setup", kind) for i in ids])
        mp = models(yk, {"n": np.c_[n], "n+nnz": np.c_[n, nnz], "n+nnz+msm_struct": np.c_[n, nnz, (col("msm_full") + col("fft")) / P],
                         "n+nnz+msm_witness": np.c_[n, nnz, (col("msm_real") + col("fft")) / P]}, splits)
        msk = models(ysk, {"n": np.c_[n], "n+nnz": np.c_[n, nnz]}, splits)
        sens[kind] = dict(proof_wall={k: dict(mape_lofo=v["mape_lofo"], max_lofo=v["max_lofo"]) for k, v in mp.items()}, setup_wall={k: dict(mape_lofo=v["mape_lofo"], max_lofo=v["max_lofo"]) for k, v in msk.items()})
    M["sens"] = sens
    ys = np.array([per[i]["setup"]["median"] for i in ids]); M["models"]["setup_wall"] = models(ys, {"n": np.c_[n], "n+nnz": np.c_[n, nnz]}, splits)
    if "mem" in M and all(i in M["mem"] for i in ids):
        yc = np.array([M["mem"][i]["proof"]["cpu_s"] for i in ids])
        M["models"]["proof_cpu"] = models(yc, {"n": np.c_[n], "n+nnz": np.c_[n, nnz], "n+nnz+msm_struct": np.c_[n, nnz, col("msm_full") + col("fft")],
                                                 "n+nnz+msm_witness": np.c_[n, nnz, col("msm_real") + col("fft")]}, splits)
    # matched pairs: same R1CS shape, full-width versus boolean witness
    pairs = {}
    for sz in ("100k", "300k"):
        a, b = "synth_full_" + sz, "synth_bool_" + sz
        if a in per and b in per:
            pr = dict(full_wall=per[a]["proof"]["median"], bool_wall=per[b]["proof"]["median"], wall_ratio=per[b]["proof"]["median"] / per[a]["proof"]["median"],
                      setup_ratio=per[b]["setup"]["median"] / per[a]["setup"]["median"])
            if "mem" in M and a in M["mem"]:
                pr.update(full_cpu=M["mem"][a]["proof"]["cpu_s"], bool_cpu=M["mem"][b]["proof"]["cpu_s"], cpu_ratio=M["mem"][b]["proof"]["cpu_s"] / M["mem"][a]["proof"]["cpu_s"],
                          full_cores=M["mem"][a]["proof"]["cores"], bool_cores=M["mem"][b]["proof"]["cores"])
            pr["msm_work_ratio"] = (fm.msm_units(FE[b], True)) / (fm.msm_units(FE[a], True)); pairs[sz] = pr
    M["pairs"] = pairs
    S["machines"][tag] = M
if "lap" in S["machines"] and "desk" in S["machines"]:
    cr = {}
    for ph in ("compile", "setup", "witness", "proof"):
        ids_ = [i for i in S["machines"]["lap"]["per"] if i in S["machines"]["desk"]["per"] and ph in S["machines"]["lap"]["per"][i] and ph in S["machines"]["desk"]["per"][i]
                and "msm" in FE[i]]
        a_ = [S["machines"]["lap"]["per"][i][ph]["median"] for i in ids_]; b_ = [S["machines"]["desk"]["per"][i][ph]["median"] for i in ids_]
        r_ = sps.spearmanr(a_, b_); cr["spearman_" + ph] = dict(rho=float(r_.statistic if hasattr(r_, "statistic") else r_[0]), n=len(ids_))
    S["cross"] = cr
json.dump(S, open(OUT, "w"), indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
print("wrote", OUT, {t: (m["n_ok"], m["models"]["proof_wall"]["n+nnz+msm_witness"]["mape_lofo"]) for t, m in S["machines"].items()})
