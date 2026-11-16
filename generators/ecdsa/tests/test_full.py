import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import ecgen as G, ecref as E, zk, make_sig

work = sys.argv[1]
phases = sys.argv[2].split(",") if len(sys.argv) > 2 else ["compile", "witness"]
os.makedirs(work, exist_ok=True)
Q, z, r, s = make_sig.make()
t0 = time.time()
src, args, R = G.build_full(Q, z, r, s)
print(f"python build: {time.time()-t0:.1f}s; source {len(src)/1024:.0f} KB; {len(args)} inputs ({len(args)-25} private witness values)", flush=True)
json.dump({"Q": Q, "z": z, "r": r, "s": s}, open(os.path.join(work, "sig.json"), "w"))
open(os.path.join(work, "args.txt"), "w").write(" ".join(str(a) for a in args))
rc, ncons, out, t, mb = zk.compile_src(src, work)
print(f"compile rc={rc} constraints={ncons} time={t:.1f}s peak RSS={mb:.0f} MB", flush=True)
if rc != 0:
    print(out[-3000:]); sys.exit(1)
if "witness" in phases:
    rc, out, t, mb = zk.witness(args, work)
    print(f"witness rc={rc} time={t:.1f}s peak RSS={mb:.0f} MB", flush=True)
    if rc != 0:
        print(out[-1500:]); sys.exit(1)
for ph, cmd in (("setup", ["setup"]), ("proof", ["generate-proof"]), ("verify", ["verify"])):
    if ph in phases:
        rc, out, t, mb = zk.run([zk.ZOK] + cmd, work)
        print(f"{ph} rc={rc} time={t:.1f}s peak RSS={mb:.0f} MB  {out.strip().splitlines()[-1][:100] if out.strip() else ''}", flush=True)
        if rc != 0:
            print(out[-1500:]); sys.exit(1)
