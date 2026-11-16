#!/usr/bin/env python3
"""Correctness and mutation tests for the RSA ZoKrates circuit (RSA_BITS, default 2048). Usage: run_tests.py [full|mutants|all]"""
import os, sys, subprocess, hashlib, random, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rsa_common import *
import build_circuit as bc
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes

ROOT = os.path.normpath(os.path.join(HERE, ".."))
ZOK = os.environ.get("ZOKRATES_BIN", "zokrates")
ENV = dict(os.environ)          # set ZOKRATES_STDLIB if your zokrates binary does not find its standard library
WORK = os.path.join(ROOT, f"work{BITS}"); os.makedirs(WORK + "/mutants", exist_ok=True)
random.seed(20261107)

def keypair(msg):
    key = rsa.generate_private_key(public_exponent=65537, key_size=BITS)
    sig = key.sign(msg, padding.PKCS1v15(), hashes.SHA256())
    key.public_key().verify(sig, msg, padding.PKCS1v15(), hashes.SHA256())      # library accepts it
    n = key.public_key().public_numbers().n
    s = int.from_bytes(sig, "big"); h = hashlib.sha256(msg).digest()
    assert pow(s, 65537, n) == em_int(h), "my EM construction disagrees with the library"
    return key, n, s, h

def run(out, args):
    r = subprocess.run([ZOK, "compute-witness", "-i", out, "-o", out + ".wit", "-a", *args],
                       capture_output=True, text=True, env=ENV, timeout=900)
    txt = (r.stdout + r.stderr).strip().splitlines()
    return r.returncode == 0, (txt[-1] if txt else "")[:110]

def shift_limb(x_limbs, i):
    """Same integer value, but limb i is out of range (+2^W) and limb i+1 is reduced by 1."""
    y = list(x_limbs); y[i] += 1 << W; y[i + 1] -= 1; assert y[i + 1] >= 0
    return y

def flat(n, s, h, d, qs, rs, ql):
    a = limbs(n) + digest_limbs(h) + limbs(s) + limbs(d)
    for q in qs: a += limbs(q)
    for r in rs: a += limbs(r)
    return [str(v) for v in a + limbs(ql)]

def cases():
    keyA, nA, sA, hA = keypair(b"hello zero knowledge")
    keyB, nB, sB, hB = keypair(b"a different message, a different key")
    qs, rs, ql, rl = chain(nA, sA, hA)
    C = []
    C.append(("valid signature, key A", build_args(nA, sA, hA), 1))
    C.append(("valid signature, key B", build_args(nB, sB, hB), 1))
    h2 = bytes([hA[0] ^ 1]) + hA[1:]
    C.append(("digest with one bit flipped", build_args(nA, sA, h2), 0))
    C.append(("signature + 1", build_args(nA, sA + 1, hA), 0))
    C.append(("wrong modulus (n + 2)", build_args(nA + 2, sA, hA), 0))
    s4 = sA + nA                                          # congruent to s, but not < n
    qs4, rs4, ql4, rl4 = chain(nA, s4, hA)
    assert rl4 == em_int(hA)
    C.append(("s + n, d = 0 (non-canonical signature)", build_args(nA, s4, hA, d=0, qs=qs4, rs=rs4, ql=ql4), 0))
    C.append(("s + n, d = two's complement", build_args(nA, s4, hA, d=(nA - s4) % (1 << (K * W)), qs=qs4, rs=rs4, ql=ql4), 0))
    # out-of-range limbs with the integer value unchanged
    a = flat(nA, sA, hA, nA - sA, qs, rs, ql); base = len(limbs(nA)) + 3 + 2 * K
    qpos = base + 3 * K + 3                                # q[3] limb 3
    a_q = list(a); v = [int(t) for t in a_q[qpos:qpos + 2]]; a_q[qpos], a_q[qpos + 1] = [str(t) for t in shift_limb(v, 0)]
    C.append(("quotient limb out of range (value unchanged)", a_q, 0))
    rpos = base + 16 * K + 5 * K + 3                       # r[5] limb 3
    a_r = list(a); v = [int(t) for t in a_r[rpos:rpos + 2]]; a_r[rpos], a_r[rpos + 1] = [str(t) for t in shift_limb(v, 0)]
    C.append(("remainder limb out of range (value unchanged)", a_r, 0))
    qs_b = list(qs); qs_b[7] += 1
    C.append(("quotient off by one", build_args(nA, sA, hA, qs=qs_b, rs=rs, ql=ql), 0))
    # forged chain: s = 1, intermediate values arbitrary, quotients only correct modulo the BN254 prime
    ninv = pow(nA % P, -1, P); rr = [random.randrange(1, nA) for _ in range(16)]
    prev, fq = 1, []
    for j in range(16):
        fq.append(((prev * prev - rr[j]) * ninv) % P); prev = rr[j]
    fql = ((prev * 1 - em_int(hA)) * ninv) % P
    C.append(("forgery: s = 1, quotients correct only mod p", build_args(nA, 1, hA, qs=fq, rs=rr, ql=fql), 0))
    # signature on EM + 2^(W(2K-2)) mod n, last quotient adjusted so the integer identity is off by exactly 2^(W(2K-2))
    CC = 1 << (W * (2 * K - 2)); em = em_int(hA); em2 = (em + CC) % nA
    s2 = pow(em2, keyA.private_numbers().d, nA); assert pow(s2, 65537, nA) == em2
    q2, r2, l2, rl2 = chain(nA, s2, hA); assert rl2 == em2
    m, rem = divmod(CC - em2 + em, nA); assert rem == 0
    C.append(("top-coefficient forgery (identity off by 2^(W(2K-2)))", build_args(nA, s2, hA, qs=q2, rs=r2, ql=l2 - m), 0))
    return C

# which cases each mutant must (wrongly) accept, to show the test would notice the missing check
MUT_EXPECT = {
    "noadder": ["valid signature, key A", "s + n, d = 0 (non-canonical signature)"],
    "norange": ["valid signature, key A", "quotient limb out of range (value unchanged)", "remainder limb out of range (value unchanged)"],
    "nocarry": ["valid signature, key A", "forgery: s = 1, quotients correct only mod p"],
    "nofinal": ["valid signature, key A", "top-coefficient forgery (identity off by 2^(W(2K-2)))"],
}

def compile_to(path_zok, out):
    t = time.time()
    r = subprocess.run([ZOK, "compile", "-i", path_zok, "-o", out], capture_output=True, text=True, env=ENV, timeout=1800)
    line = [l for l in (r.stdout + r.stderr).splitlines() if "Number of constraints" in l]
    return (line[0].split(":")[1].strip() if line else "COMPILE FAILED: " + (r.stdout + r.stderr)[-200:]), time.time() - t

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    C = cases(); lines = []; bad = 0
    def report(tag, name, expect, ok, msg):
        global bad
        good = (ok == bool(expect)); bad += (not good)
        lines.append(f"{'PASS' if good else 'FAIL'}  [{tag}] {name:<58} expected {'accept' if expect else 'reject'}, got {'accept' if ok else 'reject'}" + ("" if ok else f"  ({msg})"))
        print(lines[-1], flush=True)
    if mode in ("full", "all"):
        full = os.path.join(WORK, f"rsa{BITS}_verify.out")
        cnt, secs = compile_to(os.path.join(ROOT, f"rsa{BITS}_verify.zok"), full)
        lines.append(f"full circuit: {cnt} constraints"); print(lines[-1], flush=True)
        for name, args, expect in C:
            ok, msg = run(full, args); report("full", name, expect, ok, msg)
    if mode in ("mutants", "all"):
        for mut, must_accept in MUT_EXPECT.items():
            z = f"{WORK}/mutants/{mut}.zok"; open(z, "w").write(bc.source(mut)); out = z.replace(".zok", ".out")
            cnt, secs = compile_to(z, out); print(f"-- mutant {mut}: {cnt} constraints ({secs:.0f}s compile)", flush=True)
            for name, args, expect in C:
                if name in must_accept:
                    ok, msg = run(out, args); report("mutant:" + mut, name, 1, ok, msg)
    open(WORK + "/test_report.txt", "w").write("\n".join(lines) + f"\n\nfailures: {bad}\n")
    print("failures:", bad)
