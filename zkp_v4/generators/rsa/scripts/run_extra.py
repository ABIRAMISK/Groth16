#!/usr/bin/env python3
"""Extra completeness test for one key size (RSA_BITS): N fresh random keys/messages, all must be accepted by the compiled
circuit; also reports the largest honest carry seen in the carry chains against the range-check limit 2^(CB-1).
Usage: run_extra.py <N>     (needs work<BITS>/rsa<BITS>_verify.out from run_tests.py full)"""
import os, sys, subprocess, hashlib
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from rsa_common import *
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes
ZOK = os.environ.get("ZOKRATES_BIN", "zokrates")
out = os.path.join(HERE, "..", f"work{BITS}", f"rsa{BITS}_verify.out")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 5

def max_carry(a, b, q, r, n):
    A, B, Q, R, Nn = limbs(a), limbs(b), limbs(q), limbs(r), limbs(n)
    c = [0] * (2 * K - 1)
    for i in range(K):
        for j in range(K): c[i + j] += A[i] * B[j] - Q[i] * Nn[j]
        c[i] -= R[i]
    carry, m = 0, 0
    for i in range(2 * K - 2):
        t = c[i] + carry; assert t % (1 << W) == 0; carry = t >> W; m = max(m, abs(carry))
    assert c[2 * K - 2] + carry == 0
    return m

worst, bad = 0, 0
for t in range(N):
    msg = os.urandom(24)
    key = rsa.generate_private_key(public_exponent=65537, key_size=BITS)
    sig = key.sign(msg, padding.PKCS1v15(), hashes.SHA256())
    n = key.public_key().public_numbers().n; s = int.from_bytes(sig, "big"); h = hashlib.sha256(msg).digest()
    assert pow(s, 65537, n) == em_int(h)
    qs, rs, ql, rl = chain(n, s, h)
    xs = [s] + rs
    m = max([max_carry(xs[j], xs[j], qs[j], rs[j], n) for j in range(16)] + [max_carry(xs[16], s, ql, rl, n)])
    worst = max(worst, m)
    r = subprocess.run([ZOK, "compute-witness", "-i", out, "-o", out + ".x.wit", "-a", *build_args(n, s, h)], capture_output=True, text=True)
    ok = r.returncode == 0; bad += (not ok)
    print(f"key {t+1}/{N}: {'accepted' if ok else 'REJECTED ' + (r.stdout+r.stderr)[-120:]}; largest carry 2^{m.bit_length()-1:.0f}.. (limit 2^{CB-1})", flush=True)
print(f"RSA-{BITS}: {N-bad}/{N} random valid signatures accepted; largest honest |carry| = 2^{__import__('math').log2(worst):.2f}; limit 2^{CB-1}; analytic bound K*2^W+2 = 2^{__import__('math').log2(K*(1<<W)+2):.2f}")
