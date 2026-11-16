#!/usr/bin/env python3
"""Figures of the v8 manuscript (IEEE Transactions two-column layout). usage: python3 -I make_figs_v8.py <stats6.json> <outdir>
Sizes are the final printed sizes: one column = 3.45 in, two columns = 7.10 in; text is 7 pt or larger.
Colour = class of circuit (first three slots of the validated categorical palette: blue / orange / aqua);
marker shape = family, so every figure survives grayscale printing and colour-vision deficiency. Text is in ink, never in a series colour.
Writes m_scaling, m_model, m_pairs, m_phases, m_density (pdf + png) and m_density_values.json."""
import json, sys, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
S = json.load(open(sys.argv[1])); OUT = sys.argv[2]; os.makedirs(OUT, exist_ok=True)
W1, W2 = 3.45, 7.10
plt.rcParams.update({
    "font.family": "serif", "font.serif": ["STIXGeneral", "DejaVu Serif"], "mathtext.fontset": "stix",
    "font.size": 7.5, "axes.labelsize": 7.5, "axes.titlesize": 7.5, "xtick.labelsize": 7, "ytick.labelsize": 7,
    "legend.fontsize": 7, "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "xtick.major.size": 2.5, "ytick.major.size": 2.5, "pdf.fonttype": 42, "ps.fonttype": 42,
    "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": "#52514e",
    "axes.labelcolor": "#0b0b0b", "text.color": "#0b0b0b", "xtick.color": "#52514e", "ytick.color": "#52514e",
    "grid.color": "#e4e3df", "grid.linewidth": 0.5, "figure.dpi": 150, "savefig.dpi": 300})
BLUE, ORANGE, AQUA, INK, INK2 = "#2a78d6", "#eb6834", "#1baf7a", "#0b0b0b", "#52514e"
FAM = {"poseidon": (BLUE, "o", True, "Poseidon chain"), "merkle": (BLUE, "s", True, "Merkle path"),
       "rsa_acc": (ORANGE, "^", True, "Exponentiation ladder"),
       "synth_full": (ORANGE, "D", True, "Synthetic, full-width"), "synth_bool": (ORANGE, "D", False, "Synthetic, boolean"),
       "sha256": (AQUA, "v", True, "SHA-256"), "rsa_real": (AQUA, "h", True, "RSA verifier"), "ecdsa": (AQUA, "P", True, "ECDSA verifier")}
CIRC = {c["id"]: c for c in S["circuits"]}
def fam(i):
    g = CIRC[i]["group"]
    if g == "synth": return "synth_full" if "full" in i else "synth_bool"
    return g
def mk(ax, x, y, f, ms=4.6, z=3):
    col, m, filled, _ = FAM[f]
    if filled: ax.plot(x, y, ls="none", marker=m, ms=ms, mfc=col, mec="white", mew=0.6, zorder=z)
    else: ax.plot(x, y, ls="none", marker=m, ms=ms, mfc="white", mec=col, mew=1.1, zorder=z)
def handles(keys, ms=4.8):
    out = []
    for k in keys:
        col, m, filled, lab = FAM[k]
        out.append(Line2D([0], [0], ls="none", marker=m, ms=ms, mfc=col if filled else "white", mec="white" if filled else col, mew=0.5 if filled else 1.1, label=lab))
    return out
MACH = ["lap", "desk", "colab"]
SHORT = {"lap": "Laptop (i7-8665U, 8 threads)", "desk": "Desktop (i7-10700, 16 threads)", "colab": "Linux VM (Xeon, 2 threads)"}
MN = {"lap": "Laptop", "desk": "Desktop", "colab": "Linux VM"}
REF = {"lap": (5, 10, 20), "desk": (5, 10, 20), "colab": (50, 100, 200)}
YMAX = 100
run_ids = lambda M: [i for i in M["per"] if "proof" in M["per"][i]]
ALLK = ["poseidon", "merkle", "rsa_acc", "synth_full", "synth_bool", "sha256", "rsa_real", "ecdsa"]

# ---------------------------------------------------------------- Fig. 1: proving time versus constraints (two columns wide)
fig, axs = plt.subplots(1, 3, figsize=(W2, 2.45), sharey=True, squeeze=False); axs = axs[0]
for ax, t in zip(axs, MACH):
    M = S["machines"][t]
    for i in run_ids(M): mk(ax, CIRC[i]["n"], M["per"][i]["proof"]["median"], fam(i))
    xs = np.array([1e3, 1.2e6])
    for r in REF[t]:
        r_ = r * 1e-6
        ax.plot(xs, r_ * xs, color="#c9c8c2", lw=0.6, ls=(0, (4, 3)), zorder=1)
        if r_ * 1.15e6 <= 0.9 * YMAX: ax.text(1.15e6, r_ * 1.15e6, "%d" % r, fontsize=6.5, color=INK2, va="center", ha="left")
        else: ax.text(0.9 * YMAX / r_, 0.9 * YMAX, "%d" % r, fontsize=6.5, color=INK2, va="top", ha="right")
    ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlim(1e3, 1.3e6); ax.set_ylim(0.06, YMAX)
    ax.set_xlabel("R1CS constraints"); ax.set_title(SHORT[t], loc="left", fontsize=7.2, color=INK, pad=3); ax.grid(True, which="major", axis="both")
axs[0].set_ylabel("Proving time (s)")
fig.legend(handles=handles(ALLK), loc="lower center", ncol=8, frameon=False, bbox_to_anchor=(0.5, -0.045), handletextpad=0.15, columnspacing=0.8, fontsize=6.7)
fig.subplots_adjust(bottom=0.27, wspace=0.12, left=0.055, right=0.975, top=0.92)
fig.savefig(OUT + "/m_scaling.pdf", bbox_inches="tight", pad_inches=0.03); fig.savefig(OUT + "/m_scaling.png", bbox_inches="tight", pad_inches=0.03); plt.close(fig)

# ---------------------------------------------------------------- Fig. 3: held-out prediction / measurement versus constraints (two columns wide)
modsel = [("n", "M0: constraints only"), ("n+nnz+msm_witness", "M3: constraints, non-zero terms, witness")]
fig, axs = plt.subplots(len(modsel), 3, figsize=(W2, 3.05), sharex=True, sharey=True, squeeze=False)
YLO, YHI = 0.17, 6.0
for r, (mname, mlab) in enumerate(modsel):
    for c, t in enumerate(MACH):
        ax = axs[r][c]; M = S["machines"][t]; mod = M["models"]["proof_wall"][mname]
        ax.axhspan(0.8, 1.25, color="#e4e3df", lw=0, zorder=0); ax.axhline(1.0, color=INK2, lw=0.7, zorder=1)
        for i in M["models"]["ids"]:
            mk(ax, CIRC[i]["n"], mod["lofo_ratio"][i], fam(i), ms=4.2)
        ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlim(1e3, 1.3e6); ax.set_ylim(YLO, YHI); ax.grid(True, which="major")
        ax.set_yticks([0.25, 0.5, 1, 2, 4]); ax.set_yticklabels(["0.25", "0.5", "1", "2", "4"]); ax.minorticks_off()
        ax.set_title("%s, %s" % (MN[t], mname.split("+")[0] if False else ("M0" if r == 0 else "M3")), loc="left", fontsize=7.2, color=INK, pad=2)
        ax.text(0.97, 0.95, "mean %.0f%%, max %.0f%%" % (mod["mape_lofo"], mod["max_lofo"]), transform=ax.transAxes, ha="right", va="top", fontsize=6.8, color=INK)
        if r == len(modsel) - 1: ax.set_xlabel("R1CS constraints")
        if c == 0: ax.set_ylabel("Predicted / measured")
fig.legend(handles=handles(ALLK), loc="lower center", ncol=8, frameon=False, bbox_to_anchor=(0.5, -0.045), handletextpad=0.15, columnspacing=0.8, fontsize=6.7)
fig.subplots_adjust(bottom=0.2, hspace=0.3, wspace=0.08, left=0.065, right=0.985, top=0.94)
fig.savefig(OUT + "/m_model.pdf", bbox_inches="tight", pad_inches=0.03); fig.savefig(OUT + "/m_model.png", bbox_inches="tight", pad_inches=0.03); plt.close(fig)

# ---------------------------------------------------------------- Fig. 2: matched pairs (one column)
fig, ax = plt.subplots(figsize=(W1, 2.15))
x = np.arange(3); w = 0.34
cpu_m, cpu_lo, cpu_hi, wall_m, wall_lo, wall_hi = [], [], [], [], [], []
for t in MACH:
    p = S["machines"][t]["pairs"]; cv = [p[s]["cpu_ratio"] for s in ("100k", "300k")]; wv = [p[s]["wall_ratio"] for s in ("100k", "300k")]
    cpu_m.append(np.mean(cv)); cpu_lo.append(min(cv)); cpu_hi.append(max(cv)); wall_m.append(np.mean(wv)); wall_lo.append(min(wv)); wall_hi.append(max(wv))
cpu_m, cpu_lo, cpu_hi, wall_m, wall_lo, wall_hi = map(np.array, (cpu_m, cpu_lo, cpu_hi, wall_m, wall_lo, wall_hi))
b1 = ax.bar(x - w / 2 - 0.01, cpu_m, w, color=BLUE, label="CPU time", linewidth=0, zorder=3)
b2 = ax.bar(x + w / 2 + 0.01, wall_m, w, color=ORANGE, label="Wall-clock time", linewidth=0, zorder=3)
ax.errorbar(x - w / 2 - 0.01, cpu_m, yerr=[cpu_m - cpu_lo, cpu_hi - cpu_m], fmt="none", ecolor=INK, elinewidth=0.8, capsize=1.8, capthick=0.8, zorder=4)
ax.errorbar(x + w / 2 + 0.01, wall_m, yerr=[wall_m - wall_lo, wall_hi - wall_m], fmt="none", ecolor=INK, elinewidth=0.8, capsize=1.8, capthick=0.8, zorder=4)
for xi, m_, hi in list(zip(x - w / 2 - 0.01, cpu_m, cpu_hi)) + list(zip(x + w / 2 + 0.01, wall_m, wall_hi)): ax.text(xi, hi + 0.025, "%.2f" % m_, ha="center", va="bottom", fontsize=6.8, color=INK)
ax.axhline(1.0, color=INK2, lw=0.7, ls=(0, (4, 3)), zorder=2); ax.text(2.62, 1.015, "same as full-width", fontsize=6.6, color=INK2, ha="right", va="bottom")
ax.set_xticks(x); ax.set_xticklabels([MN[t] for t in MACH]); ax.set_ylim(0, 1.2); ax.set_ylabel("Boolean / full-width witness"); ax.grid(True, axis="y", zorder=0)
ax.legend(frameon=False, loc="upper left", ncol=2, bbox_to_anchor=(0.0, 1.13), handlelength=1.1, columnspacing=1.2)
fig.subplots_adjust(left=0.15, right=0.99, bottom=0.12, top=0.88)
fig.savefig(OUT + "/m_pairs.pdf", bbox_inches="tight", pad_inches=0.03); fig.savefig(OUT + "/m_pairs.png", bbox_inches="tight", pad_inches=0.03); plt.close(fig)

# ---------------------------------------------------------------- Fig. 5: share of each phase in the pipeline (two columns wide)
from matplotlib.patches import Patch
ORD = ["poseidon_64", "poseidon_256", "poseidon_512", "poseidon_1024", "merkle_8", "merkle_16", "merkle_32", "merkle_64c",
       "rsa_256_1", "rsa_256_8c", "rsa_256_64", "rsa_512_1c", "rsa_512_8c", "rsa_512_64c", "rsa_1024_1c", "rsa_1024_8c", "rsa_1024_64",
       "sha256_ecc", "sha256_rsa", "rsa1024real", "rsa2048real", "rsa3072real", "rsa4096real", "ecdsa_secp256k1",
       "synth_full_100k", "synth_bool_100k", "synth_full_300k", "synth_bool_300k"]
assert sorted(ORD) == sorted(CIRC), "circuit list changed"
def famk(i): return "P" if i.startswith("poseidon") else "M" if i.startswith("merkle") else "S" if i.startswith("rsa_") else "H" if i.startswith("sha256") else "Y" if i.startswith("synth") else "V"
def slab(i):
    n = CIRC[i]["n"]
    if i.startswith("poseidon"): return "Poseidon, $n=%s$" % i.split("_")[1]
    if i.startswith("merkle"): return "Merkle, $d=%s$" % i.split("_")[1]
    if i.startswith("rsa_"): _, b, r = i.split("_"); return "Ladder, $b=%s$, $r=%s$" % (b, r)
    if i.startswith("sha256"): return "SHA-256, %s input" % ("ECC" if i.endswith("ecc") else "RSA")
    if i.startswith("rsa") and i.endswith("real"): return "RSA-%d verifier" % int(i[3:7])
    if i.startswith("ecdsa"): return "ECDSA verifier"
    if i.startswith("synth_full"): return "Full-width, $N=%d$ k" % round((n - 1) / 1000)
    if i.startswith("synth_bool"): return "Boolean, $N=%d$ k" % round(((n - 2) // 2) / 1000)
    raise KeyError(i)
def tot_f(t): return "%.2f" % t if t < 1 else ("%.1f" % t if t < 10 else "%.0f" % t)
PHC = [("compile", "Compile", "#2a78d6"), ("setup", "Setup", "#a9c9f2"), ("witness", "Witness", "#f8c6ad"), ("proof", "Proof", "#eb6834"), ("verify", "Verify", "#a9a8a2")]
ids = [i for i in ORD if i in run_ids(S["machines"]["lap"])]
assert len(ids) == 21
ypos, y, prev = [], 0.0, None
for i in ids:
    if prev is not None and famk(i) != prev: y += 0.5
    ypos.append(y); y += 1.0; prev = famk(i)
fig, axs = plt.subplots(1, 3, figsize=(W2, 3.05), sharey=True)
for ax, t in zip(axs, MACH):
    M = S["machines"][t]
    for yy, i in zip(ypos, ids):
        ph = {k: M["per"][i][k]["median"] for k, _, _ in PHC}; tot = sum(ph.values()); left = 0.0
        for k, _, col in PHC:
            w = 100 * ph[k] / tot
            ax.barh(yy, w, left=left, height=0.80, color=col, edgecolor="white" if k != "verify" else "none", linewidth=0.35, zorder=3)
            left += w
        ax.text(102, yy, tot_f(tot), va="center", ha="left", fontsize=6.2, color=INK)
    ax.set_xlim(0, 100); ax.set_ylim(max(ypos) + 0.7, -0.7)
    ax.set_xticks([0, 25, 50, 75, 100]); ax.tick_params(axis="x", length=2.5)
    ax.set_xlabel("Share of the pipeline time (%)")
    ax.set_title(MN[t], loc="left", fontsize=7.2, color=INK, pad=11)
    ax.text(1.0, 1.0, "total (s)", transform=ax.transAxes, fontsize=6.2, ha="left", va="bottom", color=INK2)
    ax.grid(True, axis="x", zorder=0); ax.spines["left"].set_visible(False); ax.tick_params(axis="y", length=0)
axs[0].set_yticks(ypos); axs[0].set_yticklabels([slab(i) for i in ids], fontsize=6.3)
fig.legend(handles=[Patch(facecolor=c, edgecolor="none", label=l) for _, l, c in PHC], loc="lower center", ncol=5, frameon=False, bbox_to_anchor=(0.58, -0.02), handlelength=1.1, handletextpad=0.4, columnspacing=1.2, fontsize=6.8)
fig.subplots_adjust(left=0.135, right=0.99, wspace=0.30, top=0.93, bottom=0.145)
fig.savefig(OUT + "/m_phases.pdf", bbox_inches="tight", pad_inches=0.03); fig.savefig(OUT + "/m_phases.png", bbox_inches="tight", pad_inches=0.03); plt.close(fig)

# ---------------------------------------------------------------- Fig. 6: proving time per constraint against density (two columns wide)
STR = S["struct"]
DK = ["poseidon", "rsa_acc", "synth_full", "synth_bool", "rsa_real", "ecdsa"]
fig, axs = plt.subplots(1, 3, figsize=(W2, 2.05))
VAL = {}
for ax, t in zip(axs, MACH):
    M = S["machines"][t]; bigs = [i for i in run_ids(M) if CIRC[i]["n"] >= 5e4]
    rate_ = {i: 1e6 * M["per"][i]["proof"]["median"] / CIRC[i]["n"] for i in bigs}
    dens_ = {i: STR[i]["nnz_per_constraint"] for i in bigs}
    jit = {"poseidon_256": 0.955, "poseidon_512": 1.0, "poseidon_1024": 1.045, "synth_full_100k": 0.955, "synth_bool_100k": 0.955, "synth_full_300k": 1.045, "synth_bool_300k": 1.045}
    for i in bigs: mk(ax, dens_[i] * jit.get(i, 1.0), rate_[i], fam(i), ms=4.6)
    fw = np.mean([rate_[i] for i in ("synth_full_100k", "synth_full_300k")]); bo = np.mean([rate_[i] for i in ("synth_bool_100k", "synth_bool_300k")])
    po = np.mean([rate_[i] for i in bigs if i.startswith("poseidon")]); dpo = dens_["poseidon_256"]
    VAL[t] = {"wit_eff": fw / bo, "den_eff": po / fw}
    ymax = 1.12 * max(rate_.values())
    ax.plot([5.0, 0.96 * dpo], [fw, fw], color="#9a998f", lw=0.7, ls=(0, (3, 2)), zorder=1)
    xa = 6.3
    ax.annotate("", xy=(xa, fw), xytext=(xa, bo), arrowprops=dict(arrowstyle="<->", lw=0.7, color=INK2, shrinkA=0, shrinkB=0, mutation_scale=5), zorder=2)
    ax.text(xa * 1.06, (fw + bo) / 2, "%.1f$\\times$" % (fw / bo), fontsize=6.8, va="center", ha="left", color=INK)
    xb = 19.5
    ax.annotate("", xy=(xb, po), xytext=(xb, fw), arrowprops=dict(arrowstyle="<->", lw=0.7, color=INK2, shrinkA=0, shrinkB=0, mutation_scale=5), zorder=2)
    ax.text(xb * 0.94, (po + fw) / 2, "%.1f$\\times$" % (po / fw), fontsize=6.8, va="center", ha="right", color=INK)
    ax.set_xscale("log"); ax.set_xlim(3.0, 40); ax.set_ylim(0, ymax)
    ax.set_xticks([3, 5, 10, 20, 30]); ax.set_xticklabels(["3", "5", "10", "20", "30"]); ax.minorticks_off(); ax.grid(True, which="major")
    ax.set_xlabel("Non-zero terms per constraint (density)"); ax.set_title(SHORT[t], loc="left", fontsize=7.2, color=INK, pad=3)
axs[0].set_ylabel("Proving time per constraint ($\\mu$s)")
fig.legend(handles=handles(DK), loc="lower center", ncol=6, frameon=False, bbox_to_anchor=(0.5, -0.045), handletextpad=0.15, columnspacing=0.9, fontsize=6.8)
fig.subplots_adjust(bottom=0.27, wspace=0.22, left=0.06, right=0.985, top=0.9)
fig.savefig(OUT + "/m_density.pdf", bbox_inches="tight", pad_inches=0.03); fig.savefig(OUT + "/m_density.png", bbox_inches="tight", pad_inches=0.03); plt.close(fig)
json.dump(VAL, open(OUT + "/m_density_values.json", "w"))
print("figures written to", OUT)
