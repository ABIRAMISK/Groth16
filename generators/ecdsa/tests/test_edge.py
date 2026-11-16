"""Edge-case keys and messages on the compiled full circuit (work/full1): all must be accepted (completeness),
plus a proof-level check that verification fails when a public input of a valid proof is altered."""
import sys, os, json, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import ecgen as G, ecref as E, zk

work = sys.argv[1]
random.seed(99)
n = E.n
rows = []
def attempt(label, d, z, k=None):
    Q = E.mul(d, E.G)
    k = k or random.randrange(1, n)
    r, s = E.ecdsa_sign(d, z, k)
    assert E.ecdsa_verify(Q, z, r, s), label
    try:
        src, args, R = G.build_full(Q, z, r, s)
    except G.Exceptional as e:
        rows.append((label, "BUILDER: exceptional case (" + str(e) + ")")); print(label, "-> exceptional", flush=True); return
    rc, out, t, mb = zk.witness(args, work)
    rows.append((label, "accepted" if rc == 0 else "REJECTED"))
    print(label, "->", rows[-1][1], flush=True)

for d in (1, 2, 3, n - 1, n - 2, 1 << 128, 1 << 255):
    attempt(f"key d={d if d < 10 else hex(d)[:12]}", d, random.getrandbits(256))
dk = random.randrange(2, n - 1)
for z in (0, 1, n - 1, n, (1 << 256) - 1, 1 << 255):
    attempt(f"message hash z={z if z < 10 else hex(z)[:12]}", dk, z)
# signature whose s is small / large, nonce edge values
for k in (1, 2, n - 1):
    attempt(f"nonce k={k if k < 10 else 'n-1'}", dk, random.getrandbits(256), k)
bad = [r for r in rows if r[1] != "accepted"]
print("edge cases accepted: %d/%d" % (len(rows) - len(bad), len(rows)), bad)
json.dump(rows, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "test_edge_result.json"), "w"), indent=1)

# proof-level check: alter one public input of the valid proof written by the compile run (proof.json, verification.key in work)
pj = json.load(open(os.path.join(work, "proof.json")))
ok0 = zk.run([zk.ZOK, "verify"], work)[1].strip().splitlines()[-1]
alt = json.loads(json.dumps(pj))
v = int(alt["inputs"][10][2:], 16) + 1                      # z limb 0 + 1
alt["inputs"][10] = "0x" + format(v, "064x")
os.makedirs(os.path.join(work, "alt"), exist_ok=True)
json.dump(alt, open(os.path.join(work, "alt", "proof.json"), "w"))
import shutil; shutil.copy(os.path.join(work, "verification.key"), os.path.join(work, "alt", "verification.key"))
rc, out, t, mb = zk.run([zk.ZOK, "verify"], os.path.join(work, "alt"))
print("verify original proof:", ok0, "| verify with z altered:", out.strip().splitlines()[-1] if out.strip() else rc)
