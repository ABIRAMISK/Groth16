#!/usr/bin/env python3
"""Frozen-model predictions for the two BabyJubJub EdDSA verifiers, written BEFORE either circuit was timed on the study machines.
Models M0, M1, M3 are fitted on the 21 full-pipeline circuits of the published sessions (relative-error non-negative least squares,
as in the paper) and applied to the features of the two new circuits. usage: python3 -I predict.py <base> <feat_sha256.json> <feat_poseidon.json>"""
import sys, math, json
BASE = sys.argv[1]
_src = open(BASE + "/review_check_v9.py", encoding="utf-8").read()
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(_src[:_src.index("ok = []; bad = []")], "setup", "exec"))
import numpy as np
NEW = {"eddsa_sha256": json.load(open(sys.argv[2])), "eddsa_poseidon": json.load(open(sys.argv[3]))}
def x(f, t, model):
    m = f["domain"]; n = f["n_constraints"]; nnz = f["nnz_A"] + f["nnz_B"] + f["nnz_C"]
    F = 3.5 * m * math.log2(m); W = msm_work(f)
    return {"M0": [1.0, n], "M1": [1.0, n, nnz], "M3": [1.0, n, nnz, (W + F) / PCPU[t]]}[model]
out = {"features": {k: {"n_constraints": f["n_constraints"], "nnz": f["nnz_A"] + f["nnz_B"] + f["nnz_C"], "domain": f["domain"], "msm_work": msm_work(f)} for k, f in NEW.items()},
       "training_range": {"n_constraints": [min(FEA[i]["n_constraints"] for i in FULL), max(FEA[i]["n_constraints"] for i in FULL)],
                          "nnz_per_constraint": [round(min((FEA[i]["nnz_A"]+FEA[i]["nnz_B"]+FEA[i]["nnz_C"])/FEA[i]["n_constraints"] for i in FULL), 2),
                                                 round(max((FEA[i]["nnz_A"]+FEA[i]["nnz_B"]+FEA[i]["nnz_C"])/FEA[i]["n_constraints"] for i in FULL), 2)]},
       "models": {}, "predictions_s": {}}
for t in ("lap", "desk", "colab"):
    y = np.array([T(t, i, "proof") for i in FULL])
    for mo in ("M0", "M1", "M3"):
        X = np.array([x(FEA[i], t, mo) for i in FULL], float)
        c, _ = nnls(X / y[:, None], np.ones(len(y)))
        out["models"]["%s/%s" % (t, mo)] = [float(v) for v in c]
        for k, f in NEW.items():
            out["predictions_s"]["%s/%s/%s" % (t, k, mo)] = round(float(np.array(x(f, t, mo)) @ c), 4)
print(json.dumps(out, indent=1))
