"""Completeness and soundness tests on the compiled full circuit (work/full1): every test only calls compute-witness."""
import sys, os, json, random, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import ecgen as G, ecref as E, zk, make_sig

work = sys.argv[1]
random.seed(20261110)
K = G.K
res = {"accept_ok": 0, "accept_total": 0, "reject_ok": 0, "reject_total": 0, "survivors": []}

def wit(args):
    rc, out, t, mb = zk.witness(args, work)
    return rc == 0, out

def expect(ok_expected, args, label):
    ok, out = wit(args)
    key = "accept" if ok_expected else "reject"
    res[key + "_total"] += 1
    if ok == ok_expected:
        res[key + "_ok"] += 1
    else:
        res["survivors" if not ok_expected else "failures"] = res.get("survivors" if not ok_expected else "failures", []) + [label]
        print("UNEXPECTED:", label, "accepted" if ok else "rejected", out[-200:].replace("\n", " "), flush=True)
    return ok

# --- baseline from the compile run
sig = json.load(open(os.path.join(work, "sig.json")))
Q, z, r, s = tuple(sig["Q"]), sig["z"], sig["r"], sig["s"]
src0, args0, R0 = G.build_full(Q, z, r, s)
marks = list(G.LAST_MARKS)
assert " ".join(str(a) for a in args0) == open(os.path.join(work, "args.txt")).read()
print("baseline:", "accepted" if expect(True, args0, "baseline") else "REJECTED", flush=True)

# --- completeness on fresh random signatures (same compiled circuit; source must be identical)
for i in range(10):
    Qi, zi, ri, si = make_sig.make()
    srci, argsi, _ = G.build_full(Qi, zi, ri, si)
    assert srci == src0
    expect(True, argsi, f"random signature {i}")
print("random valid signatures accepted: %d/%d" % (res["accept_ok"], res["accept_total"]), flush=True)
# high-s twin and z + n (same message class mod n)
srcx, argsx, _ = G.build_full(Q, z, r, E.n - s); expect(True, argsx, "high-s twin (n - s)")
if z + E.n < 2 ** 256:
    pass  # z is a 256-bit hash; z+n < 2^256 only when z < 2^256 - n (probability 2^-128) -> not exercised
# --- all public inputs tampered (witness untouched): must be rejected
names = ["qx", "qy", "z", "r", "s"]
for pi, nm in enumerate(names):
    for limb in (0, 2, K - 1):
        for delta in (1, -1):
            a = list(args0)
            v = a[pi * K + limb] + delta
            if v < 0 or (limb == K - 1 and v > 0xFFFF): continue
            a[pi * K + limb] = v
            expect(False, a, f"tamper {nm} limb {limb} {delta:+d}")
# swap r and s, replace the message
a = list(args0); a[3 * K:4 * K], a[4 * K:5 * K] = args0[4 * K:5 * K], args0[3 * K:4 * K]; expect(False, a, "swap r,s")
a = list(args0); a[2 * K:3 * K] = G.limbs(random.getrandbits(256)); expect(False, a, "random z")
print("public-input tampering rejected: %d/%d" % (res["reject_ok"], res["reject_total"]), flush=True)

# --- witness mutation: every labelled gadget family, then random positions
fam = {}
for a_, b_, lab in marks:
    fam.setdefault(lab.split(":")[0] if lab.startswith("padd") else lab, []).append((a_, b_))
pos = []
for lab, rngs in fam.items():
    for a_, b_ in random.sample(rngs, min(3, len(rngs))):
        for p_ in random.sample(range(a_, b_), min(4, b_ - a_)):
            pos.append((p_, lab))
for _ in range(60):
    p_ = random.randrange(25, len(args0))
    lab = next(l for a_, b_, l in marks if a_ <= p_ < b_)
    pos.append((p_, lab))
print("mutating %d witness positions" % len(pos), flush=True)
for p_, lab in pos:
    a = list(args0)
    a[p_] = a[p_] + random.choice([1, 2, 7]) if random.random() < 0.7 else (a[p_] ^ 1)
    expect(False, a, f"mutate witness[{p_ - 25}] in {lab}")
print(json.dumps(res), flush=True)
json.dump(res, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "test_full_sound_result.json"), "w"), indent=1)
