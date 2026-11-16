"""Component-level adversarial tests: bounds at extreme values, exceptional addition with/without the x1 != x2 check,
non-canonical aliasing, range gadgets (canon, rng_n, final_cmp), curve membership."""
import sys, os, re, random, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import ecgen as G, ecref as E, zk

random.seed(7)
K, W, P, N = G.K, G.W, G.P, G.N
base = zk.WORK
summary = []

def rec(name, ok, detail=""):
    summary.append((name, ok, detail)); print(("PASS " if ok else "FAIL ") + name + (" -- " + detail if detail else ""), flush=True)

def compile_run(tag, src, args=None):
    w = os.path.join(base, tag)
    rc, ncons, out, t, mb = zk.compile_src(src, w)
    assert rc == 0, out[-1500:]
    return w, ncons

def run_w(w, args):
    rc, out, t, mb = zk.witness(args, w)
    return rc == 0

# ---------------------------------------------------------------- 1. bounds at extreme values (Python only)
ext = [0, 1, 2, G.MASK, 1 << 60, P - 1, P, P + 1, (1 << 256) - 1, (1 << 255), (1 << 128) - 1, G.N - 1]
n_ok = 0
for _ in range(3000):
    x1, y1, x2, y2 = (random.choice(ext + [random.getrandbits(256)]) for _ in range(4))
    if x1 % P == x2 % P or x1 == x2: continue
    try:
        G.wit_padd((x1, y1), (x2, y2)); n_ok += 1
    except G.Exceptional:
        pass
n_dbl = 0
for _ in range(3000):
    x1, y1 = random.choice(ext + [random.getrandbits(256)]), random.choice(ext + [random.getrandbits(256)])
    if y1 % P == 0: continue
    try:
        G.wit_pdbl((x1, y1)); n_dbl += 1
    except G.Exceptional:
        pass
rec("identity bounds hold for extreme 256-bit inputs (add/double, incl. non-canonical)", True, f"{n_ok} additions, {n_dbl} doublings, no bound violated")
nm = 0
for _ in range(1500):
    a, w_ = random.choice(ext + [random.getrandbits(256)]), random.choice(ext + [random.getrandbits(256)])
    G.wit_modn_u(a, w_); nm += 1
    sv = random.choice([x for x in ext if 1 <= x < N] + [random.randrange(1, N)])
    G.wit_modn_inv(sv)
rec("mod-n identities hold for extreme 256-bit inputs", True, f"{nm} cases")

# ---------------------------------------------------------------- 2. exceptional addition: the x1 != x2 check
def padd_forced(P1, P2, lam):
    (x1, y1), (x2, y2) = P1, P2
    x3 = (lam * lam - x1 - x2) % P
    y3 = (lam * (x1 - x3) - y1) % P
    env = {}
    env.update(G.env_pt("p1", P1)); env.update(G.env_pt("p2", P2))
    env.update(G.env_fe("lam", lam)); env.update(G.env_fe("x3", x3)); env.update(G.env_fe("y3", y3))
    wv = G.limbs(lam) + G.limbs(x3) + G.limbs(y3)
    for idn in G.ADD_IDS: wv += idn.eval(env)
    wv += [G._canon_inv(x3)] + [1] + [0] * (K - 1) + [1]
    return wv, (x3, y3)

def src_padd(nocheck):
    G.RCSET.clear()
    body = G.zok_padd()
    if nocheck:
        i = body.index("    // x1 != x2")
        j = body.index("    return [")
        body = body[:i] + body[j:]
    hdr = [G.PREAMBLE_IMPORTS, G.zok_consts(), ""]
    rcs = "\n".join(G.zok_rc(L) + "\n" for L in sorted(G.RCSET))
    if nocheck:   # keep the unused witness slots 'constrained' by returning them (ZoKrates refuses unconstrained inputs)
        extra = G.NW_ADD - (6 * G.K + 1)
        main = (f"def main(field[{G.PT}] p, field[{G.PT}] q, private field[{G.NW_ADD}] wit) -> field[{G.PT + extra}] {{\n"
                f"    return [...padd(p, q, wit), ...wit[{6 * G.K + 1}..{G.NW_ADD}]];\n}}\n")
    else:
        main = f"def main(field[{G.PT}] p, field[{G.PT}] q, private field[{G.NW_ADD}] wit) -> field[{G.PT}] {{\n    return padd(p, q, wit);\n}}\n"
    return "\n".join(hdr + [rcs, body, "", main])

P0 = E.mul(123456789123456789, E.G)
lam_forged = random.getrandbits(250)
wv, forged = padd_forced(P0, P0, lam_forged)           # P1 == P2: any slope satisfies the slope identity
args = G.ptlimbs(P0) + G.ptlimbs(P0) + wv
w_chk, n1 = compile_run("padd_check", src_padd(False))
w_non, n2 = compile_run("padd_nocheck", src_padd(True))
rec("forgery with P1 == P2 and arbitrary slope is REJECTED by the circuit with the x1 != x2 check", not run_w(w_chk, args), f"{n1} constraints")
rec("same forgery is ACCEPTED when the check is removed (so the check is what blocks it)", run_w(w_non, args), f"{n2} constraints, forged x3 != 2P.x: {forged[0] != E.add(P0, P0)[0]}")
negP0 = E.neg(P0)
ok_neg = False                                           # P1 == -P2: slope identity forces y1 = y2, impossible unless y = 0
try:
    for lam_try in (lam_forged, 0, 1, P - 1, random.getrandbits(255)):
        padd_forced(P0, negP0, lam_try); ok_neg = True
except AssertionError:
    ok_neg = False
rec("P1 == -P2: the slope identity has no solution (honest witness impossible)", not ok_neg)
# non-canonical aliasing: x2 = x1 + p has different limbs, so the limb check alone would pass
xs = 5
P1a, P2a = (xs, 11), (xs + P, 11)
wv3, f3 = padd_forced(P1a, P2a, lam_forged)
wv3[6 * K + 1:6 * K + 1 + K] = [0] * K; wv3[6 * K + 1 + 0 * 1] = 1
wv3[-1] = pow((G.limbs(xs)[0] - G.limbs(xs + P)[0]) % G.RBN, -1, G.RBN)
# one-hot on a limb where they differ
dl = [a - b for a, b in zip(G.limbs(xs), G.limbs(xs + P))]
i0 = next(i for i in range(K) if dl[i] != 0)
wv3[6 * K + 1:6 * K + 1 + K] = [1 if i == i0 else 0 for i in range(K)]
wv3[-1] = pow(dl[i0] % G.RBN, -1, G.RBN)
args3 = G.ptlimbs(P1a) + G.ptlimbs(P2a) + wv3 if False else G.limbs(xs) + G.limbs(11) + G.limbs(xs + P) + G.limbs(11) + wv3
rec("non-canonical alias x2 = x1 + p slips past the limb check (so inputs must be canonical: enforced in the full circuit)", run_w(w_chk, args3), "precondition of padd")

# ---------------------------------------------------------------- 3. canon / rng_n / final_cmp / oncurve gadgets
def small(tag, fn_src, main_src):
    G.RCSET.clear()
    body = fn_src()
    hdr = [G.PREAMBLE_IMPORTS, G.zok_consts(), ""]
    rcs = "\n".join(G.zok_rc(L) + "\n" for L in sorted(G.RCSET))
    return compile_run(tag, "\n".join(hdr + [rcs, body, "", main_src]))

# canon
w_c, _ = small("t_canon", G.zok_misc, f"def main(field[{K}] v, private field[1] w) {{\n    assert(canon(v, w));\n}}\n")
def canon_args(x):
    l = G.limbs(x)
    u = sum(G.LIM_MAX[i] - l[i] for i in range(1, K))
    return l + [pow(u, -1, G.RBN) if u else 1]
good = [0, 1, P - 1 - (1 << 60), (1 << 256) - (1 << 60) - 1, random.getrandbits(255)]
bad = [(1 << 256) - 1, (1 << 256) - (1 << 60), P, P + 5, (1 << 256) - 12345]
rec("canon accepts x < 2^256 - 2^60", all(run_w(w_c, canon_args(x)) for x in good))
rec("canon rejects x >= 2^256 - 2^60 (all values >= p)", not any(run_w(w_c, canon_args(x)) for x in bad))
# rng_n
w_r, _ = small("t_rngn", G.zok_misc, f"def main(field[{K}] v, private field[{G.NW_RNGN}] w) {{\n    assert(rng_n(v, w));\n}}\n")
def rn_args(v):
    d = max(0, N - 1 - v) if v < (1 << 256) else 0
    sm = sum(G.limbs(v)) % G.RBN
    return G.limbs(v) + G.limbs(d % (1 << 256)) + [pow(sm, -1, G.RBN) if sm else 1]
good = [1, 2, N - 1, N // 2, random.randrange(1, N)]
bad = [0, N, N + 1, (1 << 256) - 1, N + random.getrandbits(100)]
rec("rng_n accepts 1 <= v <= n-1", all(run_w(w_r, rn_args(v)) for v in good))
rec("rng_n rejects 0, n, n+1, 2^256-1", not any(run_w(w_r, rn_args(v)) for v in bad))
# final_cmp
w_f, _ = small("t_final", G.zok_misc, f"def main(field[{K}] xr, field[{K}] r, private field[1] w) {{\n    assert(final_cmp(xr, r, w));\n}}\n")
r0 = random.randrange(1, 1 << 100)
cases = [(r0, r0, 0, True), (r0 + N, r0, 1, True), (r0, r0, 1, False), (r0 + N, r0, 0, False), (r0 + 1, r0, 0, False),
         (r0 + N + 1, r0, 1, False), (r0 - 1, r0, 0, False), (r0, r0, 2, False), (N - 1, N - 1, 0, True)]
okf = all(run_w(w_f, G.limbs(x) + G.limbs(r) + [b]) == exp for x, r, b, exp in cases)
rec("final_cmp: x == r (b=0) or x == r + n (b=1), nothing else", okf, f"{len(cases)} cases")
# oncurve
w_o, _ = small("t_oncurve", G.zok_oncurve, f"def main(field[{G.PT}] q, private field[{G.NW_OC}] w) {{\n    assert(oncurve(q, w));\n}}\n")
Qg = E.mul(31337, E.G)
wv = G.wit_oncurve(Qg)
rec("oncurve accepts a point on secp256k1", run_w(w_o, G.ptlimbs(Qg) + wv))
Qb = (Qg[0], (Qg[1] + 1) % P)
rec("oncurve rejects (x, y+1) with the honest-for-(x,y) witness", not run_w(w_o, G.ptlimbs(Qb) + wv))
Qc = (Qg[0], Qg[1] + P if Qg[1] + P < (1 << 256) else Qg[1])
rec("oncurve is mod p (accepts y + p when it fits in 256 bits)", run_w(w_o, G.ptlimbs(Qc) + wv) if Qg[1] + P < (1 << 256) else True, "y non-canonical is harmless: same point")
# off-curve forgery attempt: a witness for the wrong square
wv_bad = G.limbs((Qb[0] * Qb[0] + 1) % P) + wv[K:]          # the point (x, y+1) with a different 's' and the old quotients
rec("oncurve rejects an off-curve point even when the square s is changed", not run_w(w_o, G.ptlimbs(Qb) + wv_bad))

bad = [n for n, ok, d in summary if not ok]
print("components:", len(summary) - len(bad), "of", len(summary), "pass", "FAILED: " + str(bad) if bad else "")
json.dump([(n, ok, d) for n, ok, d in summary], open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "test_components_result.json"), "w"), indent=1)
