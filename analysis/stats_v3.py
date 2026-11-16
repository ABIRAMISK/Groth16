#!/usr/bin/env python3
"""All statistics of the v3 manuscript, computed from the raw result CSV files. Nothing is typed by hand.

usage: python3 -I stats_v3.py <root> <out.json>
<root> = the data folder that contains res_full/, zips/res9nov/, zips/ecdsa_bat|ecdsa_ac|ecdsa_perf/.
Primary dataset: res_full/results_20261111_144909 (all 19 circuits, one session, AC power, Windows Power mode "Best performance").
Timing used everywhere unless stated: "inner" = measured inside the container around the ZoKrates command.
Replicate 0 of every circuit is the designated warm-up and is excluded from every statistic (it is reported separately).
"""
import csv, sys, json, math, re, glob, os, datetime, statistics as st, collections
from scipy import stats as sps

ROOT, OUT = sys.argv[1], sys.argv[2]
PH = ["compile", "setup", "witness", "proof", "verify"]
FULLDIR = glob.glob(ROOT + "/res_full/results_20261111_144909")[0]
N9DIR = glob.glob(ROOT + "/zips/res9nov/results_20261109_003857")[0]
BATDIR = ROOT + "/zips/ecdsa_bat/results_20261111_071616_ecdsa"
ACDIR = ROOT + "/zips/ecdsa_ac/results_20261111_090549_ecdsa"
PERFDIR = ROOT + "/zips/ecdsa_perf/results_20261111_132242_ecdsa"


def fl(x):
    try:
        return float(x)
    except Exception:
        return None


def load(p):
    return list(csv.DictReader(open(p, newline="")))


def org(rows):
    d = collections.OrderedDict()
    for r in rows:
        if r.get("status", "OK") != "OK":
            continue
        d.setdefault((r["family"], r["parameter"]), {})[int(r["replicate"])] = r
    return d


def vals(D, k, ph, kind="inner", reps=range(1, 6)):
    col = ph + ("_inner_s" if kind == "inner" else "_s")
    out = []
    for rep in reps:
        r = D.get(k, {}).get(rep)
        if r is not None and fl(r.get(col)) is not None:
            out.append(fl(r[col]))
    return out


def msd(v):
    return (st.mean(v), st.stdev(v)) if len(v) > 1 else ((v[0], 0.0) if v else (float("nan"), 0.0))


def ols(pts):
    """pts = [(constraints, seconds)]; returns slope (ms/constraint), intercept (s), R2, 95% CI half-width of slope (ms/constraint), n."""
    n = len(pts)
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in pts)
    b = sxy / sxx; a = my - b * mx
    sse = sum((y - (a + b * x)) ** 2 for x, y in pts); sst = sum((y - my) ** 2 for y in ys)
    df = n - 2
    ci = float(sps.t.ppf(0.975, df)) * math.sqrt(sse / df / sxx)
    return {"slope_ms": b * 1000, "intercept_s": a, "r2": 1 - sse / sst, "ci_ms": ci * 1000, "n": n}


S = {}
new = org(load(FULLDIR + "/results.csv"))
ctl = org(load(FULLDIR + "/results_bind_control.csv"))
n9 = org(load(N9DIR + "/results.csv"))

# ---------------------------------------------------------------- naming of circuits
def cid(k):
    fam, par = k
    if fam == "Poseidon chain": return "P" + par.split("=")[1]
    if fam == "Merkle path": return "M" + par.split("=")[1]
    if fam == "RSA accumulator":
        m = re.match(r"b=(\d+),r=(\d+)", par); return "S%s_%s" % (m[1], m[2])
    if fam.startswith("RSA-2048"): return "RSA2048"
    if fam.startswith("ECDSA"): return "ECDSA"
    raise ValueError(k)


order = list(new.keys())
K = {cid(k): k for k in order}
cons = {cid(k): int(new[k][1]["constraints"]) for k in order}
pipeline = [c for c in K if fl(new[K[c]][1]["proof_inner_s"]) is not None]
compile_only = [c for c in K if c not in pipeline]
S["circuits"] = {"all": list(K), "pipeline": pipeline, "compile_only": compile_only, "constraints": cons,
                 "family": {c: K[c][0] for c in K}, "parameter": {c: K[c][1] for c in K}}
S["n_rows"] = {"main": sum(len(v) for v in new.values()), "control": sum(len(v) for v in ctl.values()),
               "ninenov": sum(len(v) for v in n9.values())}

# ---------------------------------------------------------------- per-circuit statistics (inner, replicates 1-5)
per = {}
for c, k in K.items():
    per[c] = {}
    for ph in PH:
        v = vals(new, k, ph)
        if not v: continue
        m, s = msd(v)
        per[c][ph] = {"mean": m, "sd": s, "median": st.median(v), "min": min(v), "max": max(v), "cv": s / m, "n": len(v),
                      "values": v, "warmup": fl(new[k][0][ph + "_inner_s"]),
                      "ms_per_constraint": 1000 * m / cons[c]}
    per[c]["total_pipeline_mean"] = sum(per[c][ph]["mean"] for ph in PH if ph in per[c])
S["per"] = per

# ---------------------------------------------------------------- fits
GROUPS = {
    "native7": ["M8", "M16", "M32", "P64", "P256", "P512", "P1024"],
    "native6": ["M8", "M16", "M32", "P64", "P256", "P512"],          # held-out: Poseidon n=1024 left out
    "poseidon4": ["P64", "P256", "P512", "P1024"],
    "merkle3": ["M8", "M16", "M32"],
    "sur3": ["S256_1", "S256_64", "S1024_64"],
    "sur9": [c for c in K if c.startswith("S")],
}


def pts(group, ph, kind="inner"):
    return [(cons[c], v) for c in GROUPS[group] for v in vals(new, K[c], ph, kind)]


fits = {}
for g in GROUPS:
    fits[g] = {}
    for ph in ("compile", "setup", "witness", "proof"):
        p = pts(g, ph)
        if len(p) > 2:
            fits[g][ph] = ols(p)
S["fits"] = fits
S["fits_host"] = {g: {ph: ols(pts(g, ph, "host")) for ph in ("compile", "setup", "witness", "proof") if len(pts(g, ph, "host")) > 2} for g in ("native7", "sur3")}
S["slope_ratio"] = {ph: fits["native7"][ph]["slope_ms"] / fits["sur3"][ph]["slope_ms"] for ph in ("setup", "witness", "proof")}
S["slope_ratio_ci"] = {}
for ph in ("setup", "witness", "proof"):   # delta-method 95% interval for the ratio of two independent slopes
    a, b = fits["native7"][ph], fits["sur3"][ph]
    sa, sb = a["ci_ms"] / sps.t.ppf(0.975, a["n"] - 2), b["ci_ms"] / sps.t.ppf(0.975, b["n"] - 2)
    r = a["slope_ms"] / b["slope_ms"]
    se = r * math.sqrt((sa / a["slope_ms"]) ** 2 + (sb / b["slope_ms"]) ** 2)
    S["slope_ratio_ci"][ph] = 1.96 * se

# held-out predictions
def predict(g, ph, c):
    f = fits[g][ph]
    return f["intercept_s"] + f["slope_ms"] * cons[c] / 1000


pred = {}
pred["P1024_from_native6"] = {ph: {"pred": predict("native6", ph, "P1024"), "obs": per["P1024"][ph]["mean"]} for ph in ("compile", "setup", "witness", "proof")}
for c in ("RSA2048", "ECDSA"):
    pred[c] = {}
    for ph in ("compile", "setup", "witness", "proof"):
        ps_, pn_ = predict("sur3", ph, c), predict("native7", ph, c)
        o = per[c][ph]["mean"]
        pred[c][ph] = {"obs": o, "pred_sur": ps_, "pred_nat": pn_, "ratio_sur": o / ps_, "ratio_nat": o / pn_}
S["pred"] = pred
# surrogate b=1024 r=64 - held-out check as well: fit sur on the other two points is too thin; skip.

# per-constraint spread by family (proof / setup / compile), ms per constraint, mean over circuits
fam_groups = {"poseidon": ["P64", "P256", "P512", "P1024"], "merkle": ["M8", "M16", "M32", "M64"],
              "surrogate": [c for c in K if c.startswith("S")], "rsa2048": ["RSA2048"], "ecdsa": ["ECDSA"]}
rng = {}
for fam, cs in fam_groups.items():
    rng[fam] = {}
    for ph in ("compile", "setup", "witness", "proof"):
        v = [per[c][ph]["ms_per_constraint"] for c in cs if ph in per[c]]
        if v: rng[fam][ph] = {"min": min(v), "max": max(v), "n": len(v)}
S["per_constraint_range"] = rng

# matched-size contrasts (proof, inner means)
def ratio_of(a, b, ph="proof", kind="inner"):
    x, y = vals(new, K[a], ph, kind), vals(new, K[b], ph, kind)
    return {"mean": st.mean(x) / st.mean(y), "median": st.median(x) / st.median(y)}


S["matched"] = {"P256_over_S256_64": ratio_of("P256", "S256_64"), "P1024_over_S1024_64": ratio_of("P1024", "S1024_64"),
                "P256_over_RSA2048": ratio_of("P256", "RSA2048"), "RSA2048_over_S1024_64": ratio_of("RSA2048", "S1024_64"),
                "M32_over_S256_64": None}
S["matched"]["M32_over_S256_64"] = None

# ---------------------------------------------------------------- docker exec overhead (host - inner), every timed call (incl. warm-up)
ov = {}
allv = []
for ph in PH:
    v = []
    for k, reps in new.items():
        for r in reps.values():
            h, i = fl(r.get(ph + "_s")), fl(r.get(ph + "_inner_s"))
            if h is not None and i is not None: v.append(h - i)
    if v:
        q = st.quantiles(v, n=4)
        ov[ph] = {"n": len(v), "median": st.median(v), "q1": q[0], "q3": q[2], "min": min(v), "max": max(v)}
        allv += v
q = st.quantiles(allv, n=4)
ov["all"] = {"n": len(allv), "median": st.median(allv), "q1": q[0], "q3": q[2], "min": min(allv), "max": max(allv)}
S["docker_exec"] = ov
vin = [fl(r["verify_inner_s"]) for k in new for r in new[k].values() if fl(r.get("verify_inner_s")) is not None]
vho = [fl(r["verify_s"]) for k in new for r in new[k].values() if fl(r.get("verify_s")) is not None]
S["verify"] = {"inner_mean": st.mean(vin), "inner_min": min(vin), "inner_max": max(vin), "inner_n": len(vin),
               "host_mean": st.mean(vho), "host_min": min(vho), "host_max": max(vho),
               "inner_mean_by_circuit": {c: per[c]["verify"]["mean"] for c in pipeline},
               "all_passed": all(r["verify_passed"] == "True" for k in new for r in new[k].values() if r.get("verify_passed") not in ("", None))}
S["verify"]["n_verify_calls_passed"] = sum(1 for k in new for r in new[k].values() if r.get("verify_passed") == "True")

# ---------------------------------------------------------------- warm-up, drift
tot = lambda k, rep: sum(fl(new[k][rep][ph + "_inner_s"]) for ph in PH[:4])
rat, cvs = {}, {}
for c in pipeline:
    k = K[c]
    rat[c] = tot(k, 0) / st.mean([tot(k, r) for r in range(1, 6)])
    v = [tot(k, r) for r in range(1, 6)]
    cvs[c] = st.stdev(v) / st.mean(v)
S["warmup"] = {"ratio_by_circuit": rat, "median_ratio": st.median(rat.values()), "min_ratio": min(rat.values()), "max_ratio": max(rat.values()),
               "argmax": max(rat, key=rat.get), "argmin": min(rat, key=rat.get)}
S["cv_total"] = {"by_circuit": cvs, "median": st.median(cvs.values()), "max": max(cvs.values()), "argmax": max(cvs, key=cvs.get)}
# compile-only circuits: warm-up ratio on compile
rat_c = {c: per[c]["compile"]["warmup"] / per[c]["compile"]["mean"] for c in K}
S["warmup"]["compile_ratio_median"] = st.median(rat_c.values())
S["warmup"]["compile_ratio_max"] = max(rat_c.values())
dev = collections.defaultdict(list)
for c in pipeline:
    k = K[c]; m = st.mean([tot(k, r) for r in range(1, 6)])
    for r in range(6): dev[r].append(tot(k, r) / m - 1)
S["pass_deviation_pct"] = {r: 100 * st.mean(dev[r]) for r in range(6)}
pl = open(FULLDIR + "/pass_log.txt").read().split("\n")
dur = {}
for line in pl:
    m = re.match(r"pass (\d+) \((main|control)\) (start|end)\s+(\S+)", line)
    if m: dur.setdefault((m[2], int(m[1])), {})[m[3]] = datetime.datetime.strptime(m[4], "%Y-%m-%dT%H:%M:%SZ")
S["pass_minutes"] = [(v["end"] - v["start"]).total_seconds() / 60 for (s, i), v in sorted(dur.items()) if s == "main"]
S["power_records"] = {"records": len([l for l in pl if "battery_status" in l]), "all_ac": all("battery_status(2=AC)=2" in l for l in pl if "battery_status" in l)}
span = [datetime.datetime.strptime(re.search(r"start (\S+)", l)[1], "%Y-%m-%dT%H:%M:%SZ") for l in pl if "(main) start" in l]
spanE = [datetime.datetime.strptime(re.search(r"end\s+(\S+)", l)[1], "%Y-%m-%dT%H:%M:%SZ") for l in pl if "(main) end" in l]
S["main_total_minutes"] = (max(spanE) - min(span)).total_seconds() / 60

# ---------------------------------------------------------------- bind-mount control
ctr = {}
for k in ctl:
    c = cid(k); ctr[c] = {}
    for kind in ("inner", "host"):
        ctr[c][kind] = {}
        for ph in PH:
            a, b = vals(new, k, ph, kind), vals(ctl, k, ph, kind)
            ctr[c][kind][ph] = {"local": st.mean(a), "bind": st.mean(b), "ratio": st.mean(b) / st.mean(a),
                                "p": float(sps.ttest_ind(b, a, equal_var=False).pvalue),
                                "local_sd": st.stdev(a), "bind_sd": st.stdev(b)}
S["control"] = ctr
allr = [ctr[c]["inner"][ph]["ratio"] for c in ctr for ph in PH[:4]]
S["control_range"] = {ph: (min(ctr[c]["inner"][ph]["ratio"] for c in ctr), max(ctr[c]["inner"][ph]["ratio"] for c in ctr)) for ph in PH}
S["control_maxp"] = max(ctr[c]["inner"][ph]["p"] for c in ctr for ph in PH[:4])

# ---------------------------------------------------------------- session reproducibility: 9 Nov vs 11 Nov (inner means, replicates 1-5)
common = [c for c in K if K[c] in n9]
rr = {}
for c in common:
    rr[c] = {}
    for ph in PH:
        a, b = vals(n9, K[c], ph), vals(new, K[c], ph)
        if a and b and ph != "verify": rr[c][ph] = st.mean(a) / st.mean(b)
    ta = sum(st.mean(vals(n9, K[c], ph)) for ph in PH[:4] if vals(n9, K[c], ph))
    tb = sum(st.mean(vals(new, K[c], ph)) for ph in PH[:4] if vals(new, K[c], ph))
    rr[c]["total"] = ta / tb
S["session"] = {"ratio": rr, "n_circuits": len(common),
                "median": {ph: st.median(rr[c][ph] for c in common if ph in rr[c]) for ph in ("compile", "setup", "witness", "proof", "total")},
                "min": {ph: min(rr[c][ph] for c in common if ph in rr[c]) for ph in ("compile", "setup", "witness", "proof", "total")},
                "max": {ph: max(rr[c][ph] for c in common if ph in rr[c]) for ph in ("compile", "setup", "witness", "proof", "total")}}
# fits for the 9 Nov session (same groups) -> slopes
def pts9(group, ph):
    return [(cons[c], v) for c in GROUPS[group] if K[c] in n9 for v in vals(n9, K[c], ph)]


S["fits_9nov"] = {g: {ph: ols(pts9(g, ph)) for ph in ("compile", "setup", "witness", "proof") if len(pts9(g, ph)) > 2} for g in ("native7", "sur3")}
S["ninenov_has_ecdsa"] = ("ECDSA secp256k1 verify (real)", "5 limbs of 60 bits, 2-bit Strauss-Shamir") in n9

# ---------------------------------------------------------------- ECDSA power-state runs
def ecdsa_stats(d):
    D = org(load(d + "/results.csv"))
    k = [x for x in D if x[0].startswith("ECDSA")][0]
    out = {}
    for ph in PH:
        v = vals(D, k, ph)
        m, s = msd(v)
        out[ph] = {"mean": m, "sd": s, "min": min(v), "max": max(v), "values": v, "median": st.median(v)}
    out["total"] = sum(out[ph]["mean"] for ph in PH[:4])
    out["rep_total"] = [sum(fl(D[k][r][ph + "_inner_s"]) for ph in PH[:4]) for r in range(0, 6)]
    env = open(d + "/env.txt").read()
    out["windows"] = re.search(r"Windows \[Version ([\d.]+)\]", env)[1]
    out["battery_status"] = int(re.search(r"battery_status\(2=AC,1=battery\)=(\d)", env)[1])
    return out


S["ecdsa_states"] = {"battery": ecdsa_stats(BATDIR), "ac_efficiency": ecdsa_stats(ACDIR), "best_performance": ecdsa_stats(PERFDIR)}
S["ecdsa_states"]["full_run"] = {ph: {"mean": per["ECDSA"][ph]["mean"], "sd": per["ECDSA"][ph]["sd"], "values": per["ECDSA"][ph]["values"]} for ph in PH}
S["ecdsa_states"]["full_run"]["total"] = sum(per["ECDSA"][ph]["mean"] for ph in PH[:4])
ref = S["ecdsa_states"]["best_performance"]
for key in ("battery", "ac_efficiency", "full_run"):
    e = S["ecdsa_states"][key]
    e["ratio_to_perf_dedicated"] = {ph: e[ph]["mean"] / ref[ph]["mean"] for ph in PH[:4]}
    e["ratio_to_perf_dedicated"]["total"] = e["total"] / ref["total"]
    for ph in PH[:4]:
        a, b = e[ph]["values"], ref[ph]["values"]
        e["ratio_to_perf_dedicated"][ph + "_p"] = float(sps.ttest_ind(a, b, equal_var=False).pvalue)

# ---------------------------------------------------------------- environment facts
env = open(FULLDIR + "/env.txt").read()
def g(pat, default=None, flags=0):
    m = re.search(pat, env, flags)
    return m.group(1).strip() if m else default


S["env"] = {
    "started_utc": g(r"started (\S+) \(host clock\)"),
    "windows": g(r"Windows \[Version ([\d.]+)\]"),
    "wsl": g(r"WSL version: (\S+)"), "wsl_kernel": g(r"Kernel version: (\S+)"),
    "docker_desktop": g(r"Server: Docker Desktop (\S+)"), "docker_engine": g(r"Docker version (\S+),"),
    "vm_cpus": g(r"CPUs: (\d+)"), "vm_mem_gib": g(r"Total Memory: ([\d.]+)GiB"),
    "image": g(r"image (sha256:[0-9a-f]+)"), "zokrates": g(r"ZoKrates (\S+)"),
    "cpu": g(r"model name\s*:\s*(.+)"), "container_kernel": g(r"\n(6\.[\d.]+-microsoft-standard-WSL2)"),
    "cpu_clock_reported_mhz": g(r"cpu_clock_mhz=(\d+)"),
    "overlay_plugged_in": g(r"plugged_in=([0-9a-f-]+)"),
    "power_scheme": g(r"Power Scheme GUID: \S+\s+\((\w+)\)"),
}
json.dump(S, open(OUT, "w"), indent=1, default=float)
print("wrote", OUT)
