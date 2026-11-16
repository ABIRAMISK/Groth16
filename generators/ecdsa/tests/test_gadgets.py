import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import ecgen as G, ecref as E, zk

def parse_out(txt, nvals):
    m = re.search(r'\[("[0-9]+",?\s*)+\]', txt)
    vals = [int(v) for v in re.findall(r'"([0-9]+)"', m.group(0))]
    assert len(vals) == nvals, (len(vals), nvals)
    return vals

def pt_from_limbs(v):
    K = G.K
    return (sum(v[i] << (G.W * i) for i in range(K)), sum(v[K + i] << (G.W * i) for i in range(K)))

P0 = E.mul(123456789123456789, E.G); Q0 = E.mul(987654321987654321, E.G)
base = zk.WORK
cases = [("dbl", 1), ("add", 1), ("dbl", 3), ("add", 3), ("dbl", 12)]
prev = None
for kind, cnt in cases:
    src, args, ref = G.build_chain_test(P0, Q0, kind, cnt)
    w = os.path.join(base, f"t5_{kind}{cnt}")
    rc, ncons, out, t, mb = zk.compile_src(src, w)
    if rc != 0:
        print(kind, cnt, "COMPILE FAILED\n", out[-1800:]); sys.exit(1)
    rc2, out2, t2, mb2 = zk.witness(args, w, verbose=True)
    ok = rc2 == 0
    got = pt_from_limbs(parse_out(out2, G.PT)) if ok else None
    e2 = P0
    for _ in range(cnt): e2 = E.add(e2, e2) if kind == "dbl" else E.add(e2, Q0)
    print(f"{kind} x{cnt}: constraints={ncons} (per op {int(ncons)//cnt}); compile {t:.1f}s peak {mb:.0f} MB; witness ok={ok}; output==reference: {got == e2 == ref}")
    if not ok: print(out2[-800:])
